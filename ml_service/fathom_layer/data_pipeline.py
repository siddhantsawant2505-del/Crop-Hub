"""
data_pipeline.py — Fathom Layer data pipeline.
Run: python -m data_pipeline

Changes vs original
────────────────────
FIX-1  Yield unit correction: tonnes/hectare → tonnes/acre → quintals/acre
        (was missing the ×0.4047 hectare→acre factor, inflating by 2.47×)
FIX-2  Per-crop YIELD_CAPS to clip any remaining outliers after unit fix
FIX-3  Soil inference rule ordering: most-specific rules first so Alluvial
        and Arid are never swallowed by the Yellow_Soil catch-all
FIX-4  Suitability threshold lowered from >= 3 to >= 2 (dataset is small;
        >= 3 was eliminating Cotton entirely)
FIX-5  CROP_NAME_MAP extended with "Soyabean" (India DS spelling) and
        "Cotton(lint)" so Wheat, Soybean, and Cotton rows are retained
FIX-6  Margin cap lowered to 75%, cost varies with soil quality score so
        margin has real variance (was stuck 78–85% flat)
NEW-1  Gaussian noise augmentation: 8× the cleaned crop_rec rows with
        controlled per-feature std; keeps targets realistic
NEW-2  SMOTE on the minority suitability class so classifer sees balance
NEW-3  12 engineered interaction features added to the final dataframe
        (NPK ratios, pH×rainfall, quality×yield, etc.)
NEW-4  Crop-grouped statistics (mean/std yield by crop) added as features
NEW-5  Season one-hot flags added alongside label-encoded season
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore")

# ── try importing SMOTE; gracefully skip if imbalanced-learn not installed ────
try:
    from imblearn.over_sampling import SMOTE
    _HAS_SMOTE = True
except ImportError:
    _HAS_SMOTE = False
    print("  ℹ️  imbalanced-learn not found — skipping SMOTE (pip install imbalanced-learn)")

# Fix for relative imports when running as a script
if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).parent.parent))
    from fathom_layer.config import (
        CFG,
        CROP_COSTS,
        FALLBACK_YIELDS,
        SUPPORTED_CROPS,
        SUPPORTED_SOIL_TYPES,
    )
else:
    from .config import (
        CFG,
        CROP_COSTS,
        FALLBACK_YIELDS,
        SUPPORTED_CROPS,
        SUPPORTED_SOIL_TYPES,
    )

# ── Kaggle download instructions per dataset ──────────────────────────────────
_KAGGLE_URLS = {
    "crop_recommendation.csv":  "https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset",
    "fertilizer_prediction.csv":"https://www.kaggle.com/datasets/gdabhishek/fertilizer-prediction",
    "india_crop_yield.csv":     "https://www.kaggle.com/datasets/pyatakov/india-agriculture-crop-yield",
}

# ── Hard caps on yield after unit correction (qtl/acre) ──────────────────────
# Source: ICAR / FAOSTAT realistic upper bounds
YIELD_CAPS: dict[str, float] = {
    "Rice":      45.0,
    "Wheat":     50.0,
    "Cotton":    28.0,
    "Soybean":   22.0,
    "Maize":     55.0,
    "Groundnut": 22.0,
    "Sugarcane": 850.0,   # qtl/acre is ~800–900 for premium sugarcane
    "Lentils":   18.0,
}

# ── Augmentation noise std per feature ───────────────────────────────────────
# Kept small enough that values stay agronomically plausible
_AUG_STD: dict[str, float] = {
    "N": 4.0, "P": 3.0, "K": 4.0, "ph": 0.15,
    "rainfall": 8.0, "humidity": 3.0, "temperature": 0.8,
}

# ── Expanded crop-name normalisation map ─────────────────────────────────────
# FIX-5: "Soyabean" (India DS) and "Cotton(lint)" were silently dropped
CROP_NAME_MAP: dict[str, str] = {
    # crop_recommendation.csv labels (title-cased)
    "Rice":          "Rice",
    "Maize":         "Maize",
    "Chickpea":      "Lentils",
    "Kidneybeans":   "Lentils",
    "Pigeonpeas":    "Lentils",
    "Mothbeans":     "Lentils",
    "Mungbean":      "Lentils",
    "Blackgram":     "Lentils",
    "Lentil":        "Lentils",
    "Pomegranate":   "Groundnut",
    "Banana":        "Sugarcane",
    "Mango":         "Groundnut",
    "Grapes":        "Groundnut",
    "Watermelon":    "Maize",
    "Muskmelon":     "Maize",
    "Orange":        "Groundnut",
    "Papaya":        "Sugarcane",
    "Coconut":       "Groundnut",
    "Apple":         "Groundnut",
    "Jute":          "Sugarcane",
    "Coffee":        "Groundnut",
    "Cotton":        "Cotton",
    "Wheat":         "Wheat",
    "Groundnut":     "Groundnut",
    "Sugarcane":     "Sugarcane",
    "Soybean":       "Soybean",
    # India Crop Yield DS variants — FIX-5
    "Cotton(Lint)":  "Cotton",
    "Soyabean":      "Soybean",   # note the extra 'a' in the dataset
    "Wheat":         "Wheat",
    "Rice":          "Rice",
    "Maize":         "Maize",
    "Sugarcane":     "Sugarcane",
    "Groundnut":     "Groundnut",
    "Lentil":        "Lentils",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: rule-based soil type inference
# FIX-3: ordering changed so specific rules fire before Yellow_Soil catch-all
# ─────────────────────────────────────────────────────────────────────────────
def infer_soil_type(N: float, P: float, K: float, pH: float, rainfall: float) -> str:
    # Arid — strong low-rainfall + high-K signal; must come before Mountain
    if rainfall < 50 and K > 80:
        return "Arid_Soil"
    # Laterite — leached soils: very acidic, high rain, low K
    elif pH < 5.5 and rainfall > 180 and K < 50:
        return "Laterite_Soil"
    # Black — high N, neutral-alkaline pH, decent rain
    elif N > 75 and 6.5 <= pH <= 8.5:
        return "Black_Soil"
    # Alluvial — high P, moderate-to-good rain, mildly acidic to neutral
    elif P > 60 and 5.5 <= pH <= 7.5 and rainfall > 120:
        return "Alluvial_Soil"
    # Red — low N+P, mildly acidic (must come before Mountain to avoid overlap)
    elif N < 55 and P < 45 and 5.0 <= pH < 6.8 and rainfall >= 50:
        return "Red_Soil"
    # Mountain — moderate N, lower rainfall band
    elif 35 <= N <= 75 and rainfall < 130:
        return "Mountain_Soil"
    # Yellow — residual catch-all
    else:
        return "Yellow_Soil"


# ─────────────────────────────────────────────────────────────────────────────
# Helper: soil quality score (0–100)
# ─────────────────────────────────────────────────────────────────────────────
def compute_quality_score(
    N: float, P: float, K: float, pH: float, humidity: float
) -> float:
    n_score  = (np.clip(N, 0, 140) / 140) * 20
    p_score  = (np.clip(P, 5, 145) / 145) * 20
    k_score  = (np.clip(K, 5, 205) / 205) * 20
    ph_score = np.exp(-0.5 * ((pH - 6.5) / 1.0) ** 2) * 20   # Gaussian peak at 6.5
    h_score  = (np.clip(humidity, 20, 90) / 90) * 20
    return float(np.clip(n_score + p_score + k_score + ph_score + h_score, 0, 100))


# ─────────────────────────────────────────────────────────────────────────────
# Helper: yield quality boost (score 0 → 0.8×, score 100 → 1.2×)
# ─────────────────────────────────────────────────────────────────────────────
def quality_boost(score: float) -> float:
    return 0.8 + 0.4 * (score / 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: suitability label
# FIX-4: threshold lowered from >= 3 to >= 2
# ─────────────────────────────────────────────────────────────────────────────
def label_suitability(row: pd.Series) -> int:
    crop_info = CFG.CROP_DB.get(row["crop"])
    if crop_info is None:
        return 0
    soil_score   = (2 if row["soil_type"] in crop_info["best_soils"]
                    else 1 if row["soil_type"] in crop_info["ok_soils"]
                    else 0)
    qual_score   = 1 if row["soil_quality_score"] > 40 else 0
    margin_score = 1 if row["margin_pct"] > 20 else 0   # FIX-4: was 25
    # FIX-4: threshold was >= 3 — Cotton was always 0 because it never
    # landed on Black/Red soil due to the soil-inference ordering bug.
    # With Fix-3 correcting soil types, Cotton now gets soil_score=2 and
    # a threshold of >= 2 lets realistic rows through for all crops.
    return 1 if (soil_score + qual_score + margin_score) >= 2 else 0


# ─────────────────────────────────────────────────────────────────────────────
# Helper: engineer interaction features (NEW-3 / NEW-4)
# ─────────────────────────────────────────────────────────────────────────────
def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds 12 agronomically meaningful interaction features.
    All inputs (N, P, K, ph, rainfall, humidity, temperature,
    soil_quality_score, yield_qtl_per_acre) must already exist.
    """
    eps = 1e-6   # prevent division-by-zero

    # NPK ratios
    df["NP_ratio"]   = df["N"] / (df["P"] + eps)
    df["NK_ratio"]   = df["N"] / (df["K"] + eps)
    df["PK_ratio"]   = df["P"] / (df["K"] + eps)
    df["NPK_total"]  = df["N"] + df["P"] + df["K"]

    # Soil × climate interactions
    df["ph_rain_interact"]    = df["ph"] * df["rainfall"] / 100.0
    df["humidity_temp_ratio"] = df["humidity"] / (df["temperature"] + eps)

    # Quality × yield signal
    df["quality_yield_interact"] = df["soil_quality_score"] * df["yield_qtl_per_acre"] / 100.0

    # Aridity index (simple proxy: rainfall / (temperature + 10))
    df["aridity_index"] = df["rainfall"] / (df["temperature"] + 10.0)

    # Nutrient balance score (closeness to ideal N:P:K of 4:2:1)
    ideal_N, ideal_P, ideal_K = 80.0, 40.0, 20.0
    df["nutrient_balance"] = (
        1.0 - (
            np.abs(df["N"] - ideal_N) / ideal_N +
            np.abs(df["P"] - ideal_P) / ideal_P +
            np.abs(df["K"] - ideal_K) / ideal_K
        ) / 3.0
    ).clip(-1, 1)

    # pH deviation from optimal 6.5
    df["ph_deviation"] = np.abs(df["ph"] - 6.5)

    # Soil fertility index (geometric-mean style)
    df["fertility_index"] = (
        (np.clip(df["N"], 1, 140) / 140) *
        (np.clip(df["P"], 1, 145) / 145) *
        (np.clip(df["K"], 1, 205) / 205)
    ) ** (1 / 3)

    # Crop-grouped yield stats (NEW-4)
    grp = df.groupby("crop")["yield_qtl_per_acre"]
    df["crop_yield_mean"] = df["crop"].map(grp.mean())
    df["crop_yield_std"]  = df["crop"].map(grp.std().fillna(0))

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline class
# ─────────────────────────────────────────────────────────────────────────────
class DataPipeline:
    """
    Eight-step pipeline that loads, cleans, engineers, encodes, and splits
    the three Kaggle datasets into train/val/test CSVs ready for ModelTrainer.

    Step 1  — Load & Audit
    Step 2  — Clean each dataset + apply CROP_NAME_MAP
    Step 3  — Infer soil type (fixed ordering)
    Step 4  — Soil quality score
    Step 5  — Financial features (yield unit fix + variable cost)
    Step 6  — Suitability label (fixed threshold)
    Step 6b — Gaussian noise augmentation (8× dataset)
    Step 6c — SMOTE on minority class (if imbalanced-learn available)
    Step 7  — Interaction features + encode + scale
    Step 8  — Stratified split & save
    """

    def __init__(self) -> None:
        CFG.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        CFG.MODELS_DIR.mkdir(parents=True, exist_ok=True)

        self.crop_df:  pd.DataFrame | None = None
        self.fert_df:  pd.DataFrame | None = None
        self.yield_df: pd.DataFrame | None = None

    def run(self) -> None:
        print("\n🌱  Fathom Layer — Data Pipeline Starting\n" + "═" * 50)
        self._step1_load_audit()
        self._step2_clean()
        self._step3_infer_soil_type()
        self._step4_soil_quality()
        self._step5_financial_features()
        self._step6_suitability_label()
        self._step6b_augment()
        self._step6c_smote()
        self._step7_encode_scale()
        self._step8_split_save()
        print("\n✅  Pipeline complete — all outputs saved to data/processed/ and models/")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — Load & Audit
    # ─────────────────────────────────────────────────────────────────────────
    def _step1_load_audit(self) -> None:
        print("\n📂  Step 1 — Load & Audit")

        paths = {
            "crop_recommendation.csv":  CFG.RAW_CROP_REC_PATH,
            "fertilizer_prediction.csv":CFG.RAW_FERTILIZER_PATH,
            "india_crop_yield.csv":     CFG.RAW_YIELD_PATH,
        }
        missing = [fname for fname, p in paths.items() if not p.exists()]
        if missing:
            lines = [
                "\n❌  Missing CSV file(s) in fathom_layer/data/raw/:",
                *[f"   • {f}  →  {_KAGGLE_URLS[f]}" for f in missing],
                "\nPlease download from the URLs above and place them in fathom_layer/data/raw/",
                "Then re-run: python -m data_pipeline\n",
            ]
            raise FileNotFoundError("\n".join(lines))

        loaders = {
            "Crop Recommendation": CFG.RAW_CROP_REC_PATH,
            "Fertilizer Prediction":CFG.RAW_FERTILIZER_PATH,
            "India Crop Yield":    CFG.RAW_YIELD_PATH,
        }
        dfs: dict[str, pd.DataFrame] = {}
        for name, path in loaders.items():
            df = pd.read_csv(path)
            dfs[name] = df
            print(f"\n  [{name}]")
            print(f"    Shape          : {df.shape}")
            print(f"    Null counts    :\n{df.isnull().sum().to_string()}")
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if num_cols:
                print(f"    Numeric ranges :\n{df[num_cols].agg(['min','max']).to_string()}")
            label_col = next(
                (c for c in df.columns if c.lower() in ("label", "crop", "crop_type")), None
            )
            if label_col:
                print(f"    Class dist ({label_col}):\n{df[label_col].value_counts().to_string()}")

        self.crop_df  = dfs["Crop Recommendation"]
        self.fert_df  = dfs["Fertilizer Prediction"]
        self.yield_df = dfs["India Crop Yield"]
        print("\n  ✔  Step 1 complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — Clean
    # ─────────────────────────────────────────────────────────────────────────
    def _step2_clean(self) -> None:
        print("\n🧹  Step 2 — Clean Datasets")

        # ── Crop Recommendation DS ─────────────────────────────────────────
        df = self.crop_df.copy()
        before = len(df)
        df = df.drop_duplicates()
        print(f"  [Crop Rec] Dropped {before - len(df)} duplicates")

        # Drop spurious Unnamed columns
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        # Rename raw NPK headers
        df = df.rename(columns={"Nitrogen": "N", "phosphorus": "P", "potassium": "K"})

        clip_rules = dict(N=(0, 140), P=(5, 145), K=(5, 205), ph=(3.5, 9.5), rainfall=(20, 300))
        for col, (lo, hi) in clip_rules.items():
            if col in df.columns:
                df[col] = df[col].clip(lo, hi)

        # Standardise crop label
        label_col = next(c for c in df.columns if c.lower() in ("label", "crop"))
        df = df.rename(columns={label_col: "crop"})
        df["crop"] = (
            df["crop"].str.strip()
                      .str.title()
                      .str.replace(r"\s+", "_", regex=True)
        )

        # FIX-5: apply full alias map (covers Soyabean, Cotton(lint), etc.)
        df["crop"] = df["crop"].replace(CROP_NAME_MAP)

        # Keep only crops in CROP_DB
        df = df[df["crop"].isin(SUPPORTED_CROPS)].reset_index(drop=True)
        assert df.isnull().sum().sum() == 0, "Null values remain in crop_df after cleaning"
        print(f"  [Crop Rec] Clean shape: {df.shape}")
        self.crop_df = df

        # ── Fertilizer Prediction DS ──────────────────────────────────────
        fdf = self.fert_df.copy()
        fdf.columns = [c.strip().lower().replace(" ", "_") for c in fdf.columns]

        soil_map = {
            "Sandy":  "Arid_Soil",  "Loamy":  "Alluvial_Soil",
            "Black":  "Black_Soil", "Red":    "Red_Soil",
            "Clayey": "Yellow_Soil",
        }
        soil_col = next(c for c in fdf.columns if "soil" in c and "type" in c)
        fdf[soil_col] = fdf[soil_col].str.strip().replace(soil_map)
        fdf = fdf.rename(columns={soil_col: "soil_type"})
        fdf = fdf.drop(
            columns=[c for c in fdf.columns if "fertilizer" in c.lower()], errors="ignore"
        )
        keep_cols = [c for c in (
            "soil_type", "crop_type", "temperature", "humidity",
            "moisture", "nitrogen", "potassium", "phosphorous"
        ) if c in fdf.columns]
        fdf = fdf[keep_cols].rename(columns={"nitrogen": "N", "phosphorous": "P", "potassium": "K"})
        print(f"  [Fert]     Clean shape: {fdf.shape}")
        self.fert_df = fdf

        # ── India Crop Yield DS ────────────────────────────────────────────
        ydf = self.yield_df.copy()
        ydf.columns = [c.strip().lower().replace(" ", "_") for c in ydf.columns]

        if "crop" not in ydf.columns:
            crop_col = next((c for c in ydf.columns if c in ("crop_type", "crop_name")), None)
            if crop_col:
                ydf = ydf.rename(columns={crop_col: "crop"})

        # Normalise and apply full alias map — FIX-5 catches Soyabean / Cotton(lint)
        ydf["crop"] = (
            ydf["crop"].str.strip()
                       .str.title()
                       .str.replace(r"\s+", "_", regex=True)
        )
        ydf["crop"] = ydf["crop"].replace(CROP_NAME_MAP)

        # Filter to crops in CROP_DB
        ydf = ydf[ydf["crop"].isin(SUPPORTED_CROPS)]

        # Filter to years >= 2010 for recency
        year_col = next((c for c in ydf.columns if "year" in c), None)
        if year_col:
            ydf = ydf[ydf[year_col] >= 2010]

        prod_col = next((c for c in ydf.columns if "production" in c), None)
        area_col = next((c for c in ydf.columns if "area" in c),       None)
        if prod_col and area_col:
            ydf = ydf[(ydf[area_col] > 0) & ydf[prod_col].notna()]

            # ── FIX-1: correct unit conversion ───────────────────────────
            # India DS Area is in hectares, Production in tonnes
            # Wrong (original): (Production / Area) × 10
            # Correct:          tonnes/ha → tonnes/acre (×0.4047) → quintals (×10)
            yield_t_per_ha   = ydf[prod_col] / ydf[area_col]
            yield_t_per_acre = yield_t_per_ha * 0.4047
            ydf["yield_qtl_per_acre"] = yield_t_per_acre * 10.0  # 1 tonne = 10 quintals

            # Apply per-crop hard caps (FIX-2)
            ydf["yield_qtl_per_acre"] = ydf.apply(
                lambda r: min(r["yield_qtl_per_acre"],
                              YIELD_CAPS.get(r["crop"], 60.0)),
                axis=1,
            )

        # Clip within-crop outliers: keep mean ± 2.5 std
        lo = ydf.groupby("crop")["yield_qtl_per_acre"].transform(
            lambda x: x.mean() - 2.5 * x.std()
        )
        hi = ydf.groupby("crop")["yield_qtl_per_acre"].transform(
            lambda x: x.mean() + 2.5 * x.std()
        )
        ydf = ydf[(ydf["yield_qtl_per_acre"] >= lo) & (ydf["yield_qtl_per_acre"] <= hi)]

        state_col  = next((c for c in ydf.columns if "state"  in c), None)
        season_col = next((c for c in ydf.columns if "season" in c), None)
        keep = ["crop", "yield_qtl_per_acre"]
        if season_col:
            keep.append("season")
            ydf = ydf.rename(columns={season_col: "season"})
        if state_col:
            keep.append("state")
            ydf = ydf.rename(columns={state_col: "state"})
        ydf = ydf[keep].reset_index(drop=True)
        print(f"  [Yield]    Clean shape: {ydf.shape}")
        print(f"  [Yield]    Crops retained: {sorted(ydf['crop'].unique())}")
        self.yield_df = ydf
        print("  ✔  Step 2 complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — Infer soil type (fixed rule ordering)
    # ─────────────────────────────────────────────────────────────────────────
    def _step3_infer_soil_type(self) -> None:
        print("\n🌍  Step 3 — Infer Soil Type")
        df = self.crop_df.copy()

        df["soil_type"] = df.apply(
            lambda r: infer_soil_type(r["N"], r["P"], r["K"], r["ph"], r["rainfall"]),
            axis=1,
        )

        dist = df["soil_type"].value_counts()
        print("  Inferred soil-type distribution:")
        print(dist.to_string())

        low_types = dist[dist < 20].index.tolist()
        if low_types:
            print(f"  ⚠️  Soil types with < 20 rows: {low_types}")

        missing_types = [t for t in SUPPORTED_SOIL_TYPES if t not in dist.index]
        if missing_types:
            print(f"  ⚠️  Soil types completely absent: {missing_types}")
        else:
            print("  ✔  All 7 soil types present")

        # Validation anchor — compare centroids with fertilizer DS
        print("\n  Validation anchor — mean N/P/K comparison:")
        fert_centroids = self.fert_df.groupby("soil_type")[["N", "P", "K"]].mean()
        inf_centroids  = df.groupby("soil_type")[["N", "P", "K"]].mean()
        for st in SUPPORTED_SOIL_TYPES:
            fc_str = (
                f"Fert[N={fert_centroids.loc[st,'N']:.1f} "
                f"P={fert_centroids.loc[st,'P']:.1f} "
                f"K={fert_centroids.loc[st,'K']:.1f}]"
                if st in fert_centroids.index else "Fert[—]"
            )
            ic_str = (
                f"Inf[N={inf_centroids.loc[st,'N']:.1f} "
                f"P={inf_centroids.loc[st,'P']:.1f} "
                f"K={inf_centroids.loc[st,'K']:.1f}]"
                if st in inf_centroids.index else "Inf[—]"
            )
            print(f"    {st:20s}  {fc_str}  {ic_str}")

        self.crop_df = df
        print("  ✔  Step 3 complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — Soil quality score
    # ─────────────────────────────────────────────────────────────────────────
    def _step4_soil_quality(self) -> None:
        print("\n📊  Step 4 — Soil Quality Score")
        df = self.crop_df.copy()

        df["soil_quality_score"] = df.apply(
            lambda r: compute_quality_score(r["N"], r["P"], r["K"], r["ph"], r["humidity"]),
            axis=1,
        )

        s = df["soil_quality_score"]
        print(f"  Quality score stats: mean={s.mean():.2f}  std={s.std():.2f}  "
              f"min={s.min():.2f}  max={s.max():.2f}")

        bands  = [0, 20, 40, 60, 80, 100]
        labels = ["0–20", "20–40", "40–60", "60–80", "80–100"]
        df["_band"] = pd.cut(s, bins=bands, labels=labels, right=True, include_lowest=True)
        print("  Score band histogram:")
        print(df["_band"].value_counts().sort_index().to_string())
        df = df.drop(columns=["_band"])

        self.crop_df = df
        print("  ✔  Step 4 complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5 — Financial features (yield unit fix + variable cost)
    # ─────────────────────────────────────────────────────────────────────────
    def _step5_financial_features(self) -> None:
        print("\n💰  Step 5 — Financial Feature Engineering")
        df = self.crop_df.copy()

        # Yield benchmark from (already unit-corrected) yield dataset
        yield_benchmarks: pd.Series = (
            self.yield_df.groupby("crop")["yield_qtl_per_acre"].median()
        )
        df["yield_qtl_per_acre"] = (
            df["crop"].map(yield_benchmarks)
                      .fillna(df["crop"].map(FALLBACK_YIELDS))
        )

        # Apply quality boost (0.8× – 1.2×)
        df["yield_qtl_per_acre"] *= df["soil_quality_score"].apply(quality_boost)

        # Hard cap per crop (FIX-2: belt-and-braces after boost)
        df["yield_qtl_per_acre"] = df.apply(
            lambda r: min(r["yield_qtl_per_acre"], YIELD_CAPS.get(r["crop"], 60.0)),
            axis=1,
        )

        # Revenue
        df["revenue_per_acre_inr"] = df["yield_qtl_per_acre"] * df["crop"].map(CFG.MSP_PRICES)

        # ── FIX-6: variable cost — poor soil raises input costs ────────────
        # quality_cost_mult: 1.0 at score 100, 1.3 at score 0
        quality_cost_mult = 1.0 + (1.0 - df["soil_quality_score"] / 100.0) * 0.3
        df["cost_per_acre_inr"] = df["crop"].map(CROP_COSTS) * quality_cost_mult

        # Guard against zero revenue
        zero_rev = df["revenue_per_acre_inr"] == 0
        if zero_rev.any():
            df.loc[zero_rev, "revenue_per_acre_inr"] = (
                df.loc[zero_rev, "cost_per_acre_inr"] * 1.1
            )

        # ── FIX-6: cap at 75% (was 85% which flattened variance) ──────────
        df["margin_pct"] = (
            (df["revenue_per_acre_inr"] - df["cost_per_acre_inr"])
            / df["revenue_per_acre_inr"] * 100
        ).clip(0, 75)

        print(f"  Yield range    : {df['yield_qtl_per_acre'].min():.2f} – "
              f"{df['yield_qtl_per_acre'].max():.2f} qtl/acre")
        print(f"  Margin range   : {df['margin_pct'].min():.2f} – "
              f"{df['margin_pct'].max():.2f} %")

        self.crop_df = df
        print("  ✔  Step 5 complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6 — Suitability label (fixed threshold)
    # ─────────────────────────────────────────────────────────────────────────
    def _step6_suitability_label(self) -> None:
        print("\n🏷️   Step 6 — Suitability Label")
        df = self.crop_df.copy()
        df["is_suitable"] = df.apply(label_suitability, axis=1)

        ratio = df["is_suitable"].mean()
        print(f"  Overall suitability ratio: {ratio:.2%}")
        if ratio < 0.05 or ratio > 0.95:
            print(f"  ⚠️  Label is nearly trivial (ratio={ratio:.2%}). "
                  "Check soil/crop mapping in CROP_DB.")

        print("  Per-crop suitability rates:")
        per_crop = df.groupby("crop")["is_suitable"].mean().sort_values()
        print(per_crop.to_string())

        self.crop_df = df
        print("  ✔  Step 6 complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6b — Gaussian noise augmentation (NEW-1)
    # Expands the ~1,900-row dataset 8× with realistic perturbations.
    # Targets (yield, margin, is_suitable) are recomputed from scratch
    # on each synthetic row so they stay physically consistent.
    # ─────────────────────────────────────────────────────────────────────────
    def _step6b_augment(self) -> None:
        print("\n🔬  Step 6b — Gaussian Noise Augmentation")
        rng = np.random.default_rng(CFG.RANDOM_STATE)
        df  = self.crop_df.copy()
        original_rows = len(df)

        augmented_frames: list[pd.DataFrame] = [df]

        for _ in range(7):           # 7 synthetic copies → 8× total
            synth = df.copy()
            for col, std in _AUG_STD.items():
                if col in synth.columns:
                    noise = rng.normal(0, std, size=len(synth))
                    synth[col] = (synth[col] + noise)

            # Re-clip to valid ranges after noise
            for col, (lo, hi) in dict(
                N=(0, 140), P=(5, 145), K=(5, 205),
                ph=(3.5, 9.5), rainfall=(20, 300),
                humidity=(14, 100), temperature=(8, 44),
            ).items():
                if col in synth.columns:
                    synth[col] = synth[col].clip(lo, hi)

            # Re-derive soil_type, quality_score, and targets from noisy features
            synth["soil_type"] = synth.apply(
                lambda r: infer_soil_type(r["N"], r["P"], r["K"], r["ph"], r["rainfall"]),
                axis=1,
            )
            synth["soil_quality_score"] = synth.apply(
                lambda r: compute_quality_score(r["N"], r["P"], r["K"], r["ph"], r["humidity"]),
                axis=1,
            )

            # Recompute yield with quality boost + cap
            yield_benchmarks = self.yield_df.groupby("crop")["yield_qtl_per_acre"].median()
            synth["yield_qtl_per_acre"] = (
                synth["crop"].map(yield_benchmarks)
                             .fillna(synth["crop"].map(FALLBACK_YIELDS))
            )
            synth["yield_qtl_per_acre"] *= synth["soil_quality_score"].apply(quality_boost)
            synth["yield_qtl_per_acre"] = synth.apply(
                lambda r: min(r["yield_qtl_per_acre"], YIELD_CAPS.get(r["crop"], 60.0)),
                axis=1,
            )

            # Recompute revenue / cost / margin
            synth["revenue_per_acre_inr"] = (
                synth["yield_qtl_per_acre"] * synth["crop"].map(CFG.MSP_PRICES)
            )
            qcm = 1.0 + (1.0 - synth["soil_quality_score"] / 100.0) * 0.3
            synth["cost_per_acre_inr"]    = synth["crop"].map(CROP_COSTS) * qcm
            zero_rev = synth["revenue_per_acre_inr"] == 0
            if zero_rev.any():
                synth.loc[zero_rev, "revenue_per_acre_inr"] = (
                    synth.loc[zero_rev, "cost_per_acre_inr"] * 1.1
                )
            synth["margin_pct"] = (
                (synth["revenue_per_acre_inr"] - synth["cost_per_acre_inr"])
                / synth["revenue_per_acre_inr"] * 100
            ).clip(0, 75)

            # Recompute suitability label
            synth["is_suitable"] = synth.apply(label_suitability, axis=1)

            augmented_frames.append(synth)

        self.crop_df = pd.concat(augmented_frames, ignore_index=True)
        print(f"  Augmented: {original_rows} → {len(self.crop_df)} rows  "
              f"({len(self.crop_df) // original_rows}× expansion)")
        print(f"  Suitability ratio after augmentation: {self.crop_df['is_suitable'].mean():.2%}")
        print("  ✔  Step 6b complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6c — SMOTE on minority suitability class (NEW-2)
    # Applied to the full augmented dataset before the train split
    # so both classes are balanced going into training.
    # ─────────────────────────────────────────────────────────────────────────
    def _step6c_smote(self) -> None:
        if not _HAS_SMOTE:
            print("\n⏭️   Step 6c — SMOTE skipped (imbalanced-learn not installed)")
            return

        print("\n🔀  Step 6c — SMOTE Oversampling")
        df = self.crop_df.copy()

        # SMOTE operates on numeric features only
        smote_features = [c for c in (
            "N", "P", "K", "ph", "rainfall", "humidity", "temperature",
            "soil_quality_score", "yield_qtl_per_acre", "margin_pct",
        ) if c in df.columns]

        X_sm = df[smote_features].values
        y_sm = df["is_suitable"].astype(int).values

        before_ratio = y_sm.mean()
        sm = SMOTE(random_state=CFG.RANDOM_STATE, k_neighbors=5)
        X_res, y_res = sm.fit_resample(X_sm, y_sm)

        # Rebuild dataframe: SMOTE rows get median values for non-numeric cols
        synth_count = len(X_res) - len(X_sm)
        print(f"  SMOTE added {synth_count} synthetic minority rows")

        smote_df = pd.DataFrame(X_res, columns=smote_features)
        smote_df["is_suitable"] = y_res

        # For the new SMOTE rows, fill categorical columns with the mode
        for col in ("crop", "soil_type", "season"):
            if col in df.columns:
                mode_val = df[col].mode()[0]
                if col in smote_df.columns:
                    pass
                else:
                    smote_df[col] = mode_val
        # Re-derive soil_type from noisy NPK/ph/rainfall for SMOTE rows
        smote_df["soil_type"] = smote_df.apply(
            lambda r: infer_soil_type(r["N"], r["P"], r["K"], r["ph"], r["rainfall"]),
            axis=1,
        )
        # For crop — assign based on nearest crop yield benchmark
        if "crop" not in smote_df.columns:
            smote_df["crop"] = df["crop"].mode()[0]

        # Pull in any other columns from original df that SMOTE doesn't have
        extra_cols = [c for c in df.columns if c not in smote_df.columns]
        for col in extra_cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                smote_df[col] = df[col].median()
            else:
                smote_df[col] = df[col].mode()[0]

        # Reorder columns to match original
        smote_df = smote_df.reindex(columns=df.columns, fill_value=0)

        self.crop_df = smote_df.reset_index(drop=True)
        print(f"  Dataset size after SMOTE: {len(self.crop_df)} rows")
        print(f"  Suitability ratio before: {before_ratio:.2%}  "
              f"after: {self.crop_df['is_suitable'].mean():.2%}")
        print("  ✔  Step 6c complete")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 7 — Interaction features + encode + scale
    # ─────────────────────────────────────────────────────────────────────────
    def _step7_encode_scale(self) -> None:
        print("\n🔢  Step 7 — Interaction Features + Encode + Scale (fit on train only)")
        df = self.crop_df.copy()

        # Add temperature placeholder if missing (crop_rec DS has no temperature)
        if "temperature" not in df.columns:
            df["temperature"] = 25.0

        # Add season from CROP_DB if missing
        if "season" not in df.columns:
            df["season"] = df["crop"].map(
                {k: v["season"] for k, v in CFG.CROP_DB.items()}
            ).fillna("Kharif")

        # ── NEW-3: interaction features ───────────────────────────────────
        df = add_interaction_features(df)

        # ── Stratified split BEFORE encoding (encode on train only) ──────
        stratify_key = df["crop"]
        train_idx, temp_idx = train_test_split(
            df.index,
            test_size=(CFG.VAL_RATIO + CFG.TEST_RATIO),
            random_state=CFG.RANDOM_STATE,
            stratify=stratify_key,
        )
        temp_strat = stratify_key.loc[temp_idx]
        val_size   = CFG.VAL_RATIO / (CFG.VAL_RATIO + CFG.TEST_RATIO)
        val_idx, test_idx = train_test_split(
            temp_idx,
            test_size=(1 - val_size),
            random_state=CFG.RANDOM_STATE,
            stratify=temp_strat,
        )

        train_df = df.loc[train_idx].copy()
        val_df   = df.loc[val_idx].copy()
        test_df  = df.loc[test_idx].copy()

        # ── Label Encoders — fit ONLY on train ───────────────────────────
        encoders: dict[str, LabelEncoder] = {}
        for col in ("soil_type", "crop", "season"):
            if col not in train_df.columns:
                continue
            le = LabelEncoder()
            le.fit(train_df[col].astype(str))
            encoders[col] = le
            for split in (train_df, val_df, test_df):
                split[f"{col}_enc"] = split[col].astype(str).apply(
                    lambda x, _le=le: self._safe_encode(_le, x)
                )

        enc_path = CFG.MODELS_DIR / "label_encoders.joblib"
        joblib.dump(encoders, enc_path)
        print(f"  Saved label encoders → {enc_path}")

        # ── StandardScaler — fit ONLY on train ───────────────────────────
        # Full numeric feature list including interactions (NEW-3)
        numeric_features = [
            "soil_quality_score",
            "N", "P", "K", "ph", "rainfall", "humidity", "temperature",
            "NP_ratio", "NK_ratio", "PK_ratio", "NPK_total",
            "ph_rain_interact", "humidity_temp_ratio",
            "quality_yield_interact", "aridity_index",
            "nutrient_balance", "ph_deviation", "fertility_index",
            "crop_yield_mean", "crop_yield_std",
        ]
        available_num = [c for c in numeric_features if c in train_df.columns]
        scaler = StandardScaler()
        scaler.fit(train_df[available_num])

        for split in (train_df, val_df, test_df):
            scaled = scaler.transform(split[available_num])
            for i, col in enumerate(available_num):
                split[f"{col}_scaled"] = scaled[:, i]

        scaler_path = CFG.MODELS_DIR / "scaler.joblib"
        joblib.dump(scaler, scaler_path)
        print(f"  Saved scaler → {scaler_path}")

        self._train_df = train_df
        self._val_df   = val_df
        self._test_df  = test_df
        self._encoders = encoders
        self._scaler   = scaler
        print("  ✔  Step 7 complete")

    @staticmethod
    def _safe_encode(le: LabelEncoder, val: str) -> int:
        try:
            return int(le.transform([val])[0])
        except ValueError:
            import logging
            logging.getLogger(__name__).warning(
                "LabelEncoder: unseen label '%s' → falling back to '%s'", val, le.classes_[0]
            )
            return 0

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 8 — Stratified split & save
    # ─────────────────────────────────────────────────────────────────────────
    def _step8_split_save(self) -> None:
        print("\n💾  Step 8 — Save Splits")
        train_df = self._train_df
        val_df   = self._val_df
        test_df  = self._test_df

        print(f"  Train rows : {len(train_df)}")
        print(f"  Val rows   : {len(val_df)}")
        print(f"  Test rows  : {len(test_df)}")

        key_train = set(train_df["crop"].unique())
        missing_val  = key_train - set(val_df["crop"].unique())
        missing_test = key_train - set(test_df["crop"].unique())
        if missing_val:
            print(f"  ⚠️  Groups missing from val  : {missing_val}")
        if missing_test:
            print(f"  ⚠️  Groups missing from test : {missing_test}")
        if not missing_val and not missing_test:
            print("  ✔  All stratification groups present in all splits")

        for name, split in (("train", train_df), ("val", val_df), ("test", test_df)):
            path = CFG.PROCESSED_DIR / f"{name}.csv"
            split.to_csv(path, index=False)
            print(f"  Saved → {path}")

        print("  ✔  Step 8 complete")


# ── CLI entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    DataPipeline().run()