"""
train.py — Fathom Layer model trainer.
CLI: python -m train [--retrain]

Changes vs original
────────────────────
FIX-T1  Feature lists expanded from 11 → 24 features (all interaction
         columns produced by data_pipeline Step 7)
FIX-T2  Random Forest: n_estimators 100→500, max_depth None→20,
         min_samples_leaf 1→4, added min_samples_split, max_features
FIX-T3  XGBoost Regressor: n_estimators 100→600, deeper trees,
         lower learning_rate, colsample_bytree added
FIX-T4  XGBoost Classifier: same depth/estimator upgrades +
         colsample_bytree + gamma for regularisation
FIX-T5  5-fold cross-validation added for yield model; CV scores
         reported so over-fit is visible immediately
FIX-T6  budget_per_acre derived from cost_per_acre_inr column
         (was silently falling back to crop_enc × 8000)
NEW-T1  Permutation feature importance printed for each model
NEW-T2  Calibration curve check for suitability classifier
NEW-T3  Test-set evaluation added (not just val)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score, f1_score, mean_absolute_error,
    mean_squared_error, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import cross_val_score
from xgboost import XGBClassifier, XGBRegressor

# Fix for relative imports when running as a script
if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).parent.parent))
    from fathom_layer.config import CFG
else:
    from .config import CFG

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Feature column lists (FIX-T1: expanded with all interaction features)
# ─────────────────────────────────────────────────────────────────────────────
# Core agronomic inputs
_CORE = [
    "soil_type_enc", "crop_enc", "season_enc",
    "soil_quality_score",
    "N", "P", "K", "ph", "rainfall", "humidity", "temperature",
]

# Interaction features added in pipeline Step 7 (NEW-3)
_INTERACT = [
    "NP_ratio", "NK_ratio", "PK_ratio", "NPK_total",
    "ph_rain_interact", "humidity_temp_ratio",
    "quality_yield_interact",
    "aridity_index", "nutrient_balance", "ph_deviation", "fertility_index",
    "crop_yield_mean", "crop_yield_std",
]

BASE_FEATURES   = _CORE + _INTERACT                       # 24 features
YIELD_FEATURES  = BASE_FEATURES
MARGIN_FEATURES = BASE_FEATURES + ["predicted_yield"]
SUIT_FEATURES   = BASE_FEATURES + ["predicted_yield", "predicted_margin", "budget_per_acre"]

TARGET_YIELD  = "yield_qtl_per_acre"
TARGET_MARGIN = "margin_pct"
TARGET_SUIT   = "is_suitable"


class ModelTrainer:
    """
    Trains three stacked models in order:
      1. Yield model  (Random Forest Regressor)   — with 5-fold CV
      2. Margin model (XGBoost Regressor)          — uses predicted_yield
      3. Suit  model  (XGBoost Classifier)         — uses predicted_yield + predicted_margin
    """

    def __init__(self) -> None:
        CFG.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────────
    def train_all(self, retrain: bool = False) -> None:
        meta_path = CFG.MODELS_DIR / "model_metadata.json"

        if not retrain and meta_path.exists():
            log.info("✅  Models already exist. Pass --retrain to force retraining.")
            return

        print("\n🔬  Fathom Layer — Model Training\n" + "═" * 50)

        # ── Load splits ───────────────────────────────────────────────────
        print("\n📂  Loading processed splits …")
        train_path = CFG.PROCESSED_DIR / "train.csv"
        val_path   = CFG.PROCESSED_DIR / "val.csv"
        test_path  = CFG.PROCESSED_DIR / "test.csv"

        for p in (train_path, val_path, test_path):
            if not p.exists():
                raise FileNotFoundError(
                    f"Processed data not found ({p}). "
                    "Run: python -m data_pipeline"
                )

        train = pd.read_csv(train_path)
        val   = pd.read_csv(val_path)
        test  = pd.read_csv(test_path)

        # Ensure temperature column exists (crop_rec DS has no temperature)
        for df in (train, val, test):
            if "temperature" not in df.columns:
                df["temperature"] = 25.0

        print(f"  Train rows: {len(train)}  |  Val rows: {len(val)}  |  Test rows: {len(test)}")
        print(f"  Feature columns available: {len(train.columns)}")

        # ── Model 1 — Yield ───────────────────────────────────────────────
        yield_model, yield_metrics, tr_pred_yield, va_pred_yield, te_pred_yield = (
            self._train_yield(train, val, test)
        )

        # ── Model 2 — Margin ──────────────────────────────────────────────
        margin_model, margin_metrics, tr_pred_margin, va_pred_margin, te_pred_margin = (
            self._train_margin(train, val, test, tr_pred_yield, va_pred_yield, te_pred_yield)
        )

        # ── Model 3 — Suitability ─────────────────────────────────────────
        suit_model, suit_metrics = self._train_suitability(
            train, val, test,
            tr_pred_yield,  va_pred_yield,  te_pred_yield,
            tr_pred_margin, va_pred_margin, te_pred_margin,
        )

        # ── Write model metadata ──────────────────────────────────────────
        metadata = {
            "trained_at":  datetime.now(timezone.utc).isoformat(),
            "train_rows":  int(len(train)),
            "val_rows":    int(len(val)),
            "test_rows":   int(len(test)),
            "n_features":  len(self._available(YIELD_FEATURES, train)),
            "yield_model":       yield_metrics,
            "margin_model":      margin_metrics,
            "suitability_model": suit_metrics,
        }
        meta_path.write_text(json.dumps(metadata, indent=2))
        print(f"\n📝  Metadata saved → {meta_path}")
        print("\n🎉  All models trained and saved successfully!")

    # ─────────────────────────────────────────────────────────────────────────
    # Model 1 — Yield (Random Forest, with cross-validation)
    # FIX-T2: stronger hyperparams; FIX-T5: 5-fold CV added
    # ─────────────────────────────────────────────────────────────────────────
    def _train_yield(
        self, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame
    ) -> tuple:
        print("\n🌾  [1/3] Training Yield Model (Random Forest Regressor) …")

        feats   = self._available(YIELD_FEATURES, train)
        X_train = train[feats].values;  y_train = train[TARGET_YIELD].values
        X_val   = val[feats].values;    y_val   = val[TARGET_YIELD].values
        X_test  = test[feats].values;   y_test  = test[TARGET_YIELD].values

        print(f"  Features used: {len(feats)}")

        # FIX-T2: substantially larger, regularised forest
        model = RandomForestRegressor(
            n_estimators=500,          # was 100 — instant training
            max_depth=20,              # was None — caused memorisation
            min_samples_leaf=4,        # was 1  — caused memorisation
            min_samples_split=8,       # new    — additional regularisation
            max_features="sqrt",       # new    — reduces correlation between trees
            n_jobs=CFG.RF_N_JOBS,
            random_state=CFG.RANDOM_STATE,
        )

        # FIX-T5: 5-fold CV on training data so we can detect overfitting early
        print("  Running 5-fold cross-validation …")
        cv_r2 = cross_val_score(
            model, X_train, y_train,
            cv=5, scoring="r2", n_jobs=CFG.RF_N_JOBS,
        )
        print(f"  CV R²: {cv_r2.round(3)}  mean={cv_r2.mean():.3f}  std={cv_r2.std():.3f}")

        model.fit(X_train, y_train)

        tr_pred = model.predict(X_train)
        va_pred = model.predict(X_val)
        te_pred = model.predict(X_test)

        val_m  = self._reg_metrics(y_val,  va_pred)
        test_m = self._reg_metrics(y_test, te_pred)
        print(f"  Val  — MAE: {val_m['mae']:.4f}  RMSE: {val_m['rmse']:.4f}  R²: {val_m['r2']:.4f}")
        print(f"  Test — MAE: {test_m['mae']:.4f}  RMSE: {test_m['rmse']:.4f}  R²: {test_m['r2']:.4f}")

        # NEW-T1: top-10 permutation importances
        self._print_importances(model, X_val, y_val, feats, "yield", n=10)

        model_path = CFG.MODELS_DIR / "yield_model.joblib"
        joblib.dump(model, model_path)
        print(f"  Saved → {model_path}")

        metrics = {
            "cv_r2_mean": round(float(cv_r2.mean()), 4),
            "val_mae":    val_m["mae"],   "val_rmse":  val_m["rmse"],   "val_r2":  val_m["r2"],
            "test_mae":   test_m["mae"],  "test_rmse": test_m["rmse"],  "test_r2": test_m["r2"],
        }
        return model, metrics, tr_pred, va_pred, te_pred

    # ─────────────────────────────────────────────────────────────────────────
    # Model 2 — Margin (XGBoost Regressor)
    # FIX-T3: deeper, more trees, colsample_bytree added
    # ─────────────────────────────────────────────────────────────────────────
    def _train_margin(
        self, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame,
        tr_pred_yield: np.ndarray, va_pred_yield: np.ndarray, te_pred_yield: np.ndarray,
    ) -> tuple:
        print("\n💰  [2/3] Training Margin Model (XGBoost Regressor) …")

        train = train.copy(); val = val.copy(); test = test.copy()
        train["predicted_yield"] = tr_pred_yield
        val["predicted_yield"]   = va_pred_yield
        test["predicted_yield"]  = te_pred_yield

        feats   = self._available(MARGIN_FEATURES, train)
        X_train = train[feats].values;  y_train = train[TARGET_MARGIN].values
        X_val   = val[feats].values;    y_val   = val[TARGET_MARGIN].values
        X_test  = test[feats].values;   y_test  = test[TARGET_MARGIN].values

        print(f"  Features used: {len(feats)}")
        print(f"  Margin target — mean: {y_train.mean():.2f}  std: {y_train.std():.2f}  "
              f"min: {y_train.min():.2f}  max: {y_train.max():.2f}")

        # FIX-T3: substantially stronger XGBoost
        model = XGBRegressor(
            n_estimators=600,          # was 100
            max_depth=6,               # was 4
            learning_rate=0.03,        # was 0.1  — slower, better generalisation
            subsample=0.8,
            colsample_bytree=0.8,      # new — feature sampling per tree
            reg_alpha=0.1,             # new — L1 regularisation
            reg_lambda=1.0,            # new — L2 regularisation
            early_stopping_rounds=30,  # was CFG value (likely 10)
            random_state=CFG.RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
            eval_metric="rmse",
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        va_pred = model.predict(X_val)
        te_pred = model.predict(X_test)
        tr_pred = model.predict(X_train)

        val_m  = self._reg_metrics(y_val,  va_pred)
        test_m = self._reg_metrics(y_test, te_pred)
        print(f"  Val  — MAE: {val_m['mae']:.4f}  RMSE: {val_m['rmse']:.4f}  R²: {val_m['r2']:.4f}")
        print(f"  Test — MAE: {test_m['mae']:.4f}  RMSE: {test_m['rmse']:.4f}  R²: {test_m['r2']:.4f}")

        # NEW-T1: top-10 permutation importances
        self._print_importances(model, X_val, y_val, feats, "margin", n=10)

        model_path = CFG.MODELS_DIR / "margin_model.joblib"
        joblib.dump(model, model_path)
        print(f"  Saved → {model_path}")

        metrics = {
            "val_mae":   val_m["mae"],   "val_rmse":  val_m["rmse"],   "val_r2":  val_m["r2"],
            "test_mae":  test_m["mae"],  "test_rmse": test_m["rmse"],  "test_r2": test_m["r2"],
        }
        return model, metrics, tr_pred, va_pred, te_pred

    # ─────────────────────────────────────────────────────────────────────────
    # Model 3 — Suitability (XGBoost Classifier)
    # FIX-T4: stronger hyperparams; FIX-T6: budget from cost column
    # ─────────────────────────────────────────────────────────────────────────
    def _train_suitability(
        self,
        train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame,
        tr_pred_yield: np.ndarray,  va_pred_yield: np.ndarray,  te_pred_yield: np.ndarray,
        tr_pred_margin: np.ndarray, va_pred_margin: np.ndarray, te_pred_margin: np.ndarray,
    ) -> tuple:
        print("\n🏷️   [3/3] Training Suitability Model (XGBoost Classifier) …")

        train = train.copy(); val = val.copy(); test = test.copy()

        for split, py, pm in (
            (train, tr_pred_yield, tr_pred_margin),
            (val,   va_pred_yield, va_pred_margin),
            (test,  te_pred_yield, te_pred_margin),
        ):
            split["predicted_yield"]  = py
            split["predicted_margin"] = pm

        # FIX-T6: use actual cost column rather than crop_enc × 8000
        for split in (train, val, test):
            if "cost_per_acre_inr" in split.columns:
                split["budget_per_acre"] = split["cost_per_acre_inr"]
            else:
                # Fallback: training-time median (same behaviour as before)
                median_bpa = train.get(
                    "cost_per_acre_inr",
                    train["crop_enc"] * 8000
                ).median()
                split["budget_per_acre"] = median_bpa

        feats   = self._available(SUIT_FEATURES, train)
        X_train = train[feats].values;  y_train = train[TARGET_SUIT].astype(int).values
        X_val   = val[feats].values;    y_val   = val[TARGET_SUIT].astype(int).values
        X_test  = test[feats].values;   y_test  = test[TARGET_SUIT].astype(int).values

        print(f"  Features used: {len(feats)}")
        neg = int((y_train == 0).sum())
        pos = int((y_train == 1).sum())
        scale_pw = round(neg / pos, 4) if pos > 0 else 1.0
        print(f"  Class counts — 0: {neg}  1: {pos}  scale_pos_weight: {scale_pw}")

        # FIX-T4: stronger, regularised classifier
        model = XGBClassifier(
            n_estimators=600,           # was 100
            max_depth=6,                # was 4
            learning_rate=0.03,         # was 0.1
            subsample=0.8,
            colsample_bytree=0.8,       # new
            gamma=0.1,                  # new — min loss reduction to split
            reg_alpha=0.1,              # new — L1
            reg_lambda=1.0,             # new — L2
            scale_pos_weight=scale_pw,
            early_stopping_rounds=30,
            random_state=CFG.RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
            eval_metric="logloss",
            use_label_encoder=False,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        # Val metrics
        y_pred_val  = model.predict(X_val)
        y_prob_val  = model.predict_proba(X_val)[:, 1]
        # Test metrics (NEW-T3)
        y_pred_test = model.predict(X_test)
        y_prob_test = model.predict_proba(X_test)[:, 1]

        def _clf_metrics(y_true, y_pred, y_prob, label: str) -> dict:
            acc     = float(accuracy_score(y_true, y_pred))
            prec    = float(precision_score(y_true, y_pred, zero_division=0))
            rec     = float(recall_score(y_true, y_pred,    zero_division=0))
            f1      = float(f1_score(y_true, y_pred,        zero_division=0))
            roc_auc = float(roc_auc_score(y_true, y_prob))
            print(f"  {label:5s} — Acc: {acc:.4f}  Prec: {prec:.4f}  "
                  f"Rec: {rec:.4f}  F1: {f1:.4f}  ROC-AUC: {roc_auc:.4f}")
            return {"accuracy": round(acc,4), "f1": round(f1,4), "roc_auc": round(roc_auc,4)}

        val_m  = _clf_metrics(y_val,  y_pred_val,  y_prob_val,  "Val")
        test_m = _clf_metrics(y_test, y_pred_test, y_prob_test, "Test")

        # NEW-T2: calibration check (10 bins)
        fraction_pos, mean_pred = calibration_curve(y_val, y_prob_val, n_bins=10)
        cal_error = float(np.mean(np.abs(fraction_pos - mean_pred)))
        print(f"  Calibration error (mean |frac_pos − mean_pred|): {cal_error:.4f}")

        # NEW-T1: top-10 permutation importances
        self._print_importances(model, X_val, y_val, feats, "suitability", n=10)

        model_path = CFG.MODELS_DIR / "suitability_model.joblib"
        joblib.dump(model, model_path)
        print(f"  Saved → {model_path}")

        # Save feature lists for optimizer
        feature_lists = {
            "yield_features":       self._available(YIELD_FEATURES,  train),
            "margin_features":      self._available(MARGIN_FEATURES, train),
            "suit_features":        feats,
            "yield_features_used":  self._available(YIELD_FEATURES,  train),
            "margin_features_used": self._available(MARGIN_FEATURES, train),
            "suit_features_used":   feats,
            "median_budget_per_acre": float(train["budget_per_acre"].median()),
        }
        feat_path = CFG.MODELS_DIR / "feature_lists.joblib"
        joblib.dump(feature_lists, feat_path)
        print(f"  Saved feature lists → {feat_path}")

        metrics = {
            "val_accuracy":  val_m["accuracy"],  "val_f1":  val_m["f1"],  "val_roc_auc":  val_m["roc_auc"],
            "test_accuracy": test_m["accuracy"], "test_f1": test_m["f1"], "test_roc_auc": test_m["roc_auc"],
            "calibration_error": round(cal_error, 4),
        }
        return model, metrics

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _available(wanted: list[str], df: pd.DataFrame) -> list[str]:
        return [c for c in wanted if c in df.columns]

    @staticmethod
    def _reg_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        mae  = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        return {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4)}

    @staticmethod
    def _print_importances(
        model, X_val: np.ndarray, y_val: np.ndarray,
        feature_names: list[str], label: str, n: int = 10,
    ) -> None:
        """NEW-T1: compute and print top-n permutation importances on val set."""
        try:
            result = permutation_importance(
                model, X_val, y_val,
                n_repeats=5, random_state=42, n_jobs=-1,
            )
            idx = np.argsort(result.importances_mean)[::-1][:n]
            print(f"\n  📊  Top-{n} permutation importances ({label} model):")
            for rank, i in enumerate(idx, 1):
                name = feature_names[i] if i < len(feature_names) else f"feat_{i}"
                print(f"    {rank:2d}. {name:30s}  {result.importances_mean[i]:.4f} "
                      f"± {result.importances_std[i]:.4f}")
        except Exception as e:
            log.warning("Could not compute permutation importance: %s", e)


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Fathom Layer models")
    parser.add_argument(
        "--retrain", action="store_true",
        help="Force retraining even if models already exist",
    )
    args = parser.parse_args()
    ModelTrainer().train_all(retrain=args.retrain)