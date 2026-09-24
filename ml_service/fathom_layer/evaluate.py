"""
evaluate.py — Fathom Layer test-set evaluation.
CLI: python -m evaluate
Loads saved models, runs on held-out test.csv, writes reports + plots to evaluation/.
"""

from __future__ import annotations
import sys
import logging
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    f1_score, mean_absolute_error, mean_squared_error, roc_auc_score,
)

# Fix for relative imports when running as a script
if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).parent.parent))
    from fathom_layer.config import CFG
else:
    from .config import CFG

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

plt.style.use("seaborn-v0_8-whitegrid") # Using a clean white grid style
_PALETTE = ["#00a65a", "#f39c12", "#0073b7", "#d81b60", "#605ca8"] # Darker colors for readability on white


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


class Evaluator:
    def __init__(self) -> None:
        CFG.EVAL_DIR.mkdir(parents=True, exist_ok=True)
        self._load_artifacts()

    # ─────────────────────────────────────────────────────────────────────────
    def _load_artifacts(self) -> None:
        required = ["yield_model.joblib", "margin_model.joblib",
                    "suitability_model.joblib", "label_encoders.joblib",
                    "scaler.joblib", "feature_lists.joblib"]
        missing = [f for f in required if not (CFG.MODELS_DIR / f).exists()]
        if missing:
            raise RuntimeError(
                f"Missing model files: {missing}\n"
                "Run: python -m train"
            )

        self.yield_model  = joblib.load(CFG.MODELS_DIR / "yield_model.joblib")
        self.margin_model = joblib.load(CFG.MODELS_DIR / "margin_model.joblib")
        self.suit_model   = joblib.load(CFG.MODELS_DIR / "suitability_model.joblib")
        self.encoders     = joblib.load(CFG.MODELS_DIR / "label_encoders.joblib")
        self.scaler       = joblib.load(CFG.MODELS_DIR / "scaler.joblib")
        self.feat_lists   = joblib.load(CFG.MODELS_DIR / "feature_lists.joblib")

        test_path = CFG.PROCESSED_DIR / "test.csv"
        if not test_path.exists():
            raise FileNotFoundError(
                "test.csv not found. Run: python -m data_pipeline"
            )
        self.test = pd.read_csv(test_path)
        if "temperature" not in self.test.columns:
            self.test["temperature"] = 25.0
        log.info("Test rows: %d", len(self.test))

    # ─────────────────────────────────────────────────────────────────────────
    def run(self) -> None:
        print("\n📊  Fathom Layer — Evaluation on Test Set\n" + "═" * 50)
        df = self.test.copy()

        # ── Yield predictions ─────────────────────────────────────────────────
        y_feats = self.feat_lists["yield_features_used"]
        y_true_yield  = df["yield_qtl_per_acre"].values
        y_pred_yield  = self.yield_model.predict(df[y_feats].values)

        # ── Margin predictions ────────────────────────────────────────────────
        df["predicted_yield"] = y_pred_yield
        m_feats = self.feat_lists["margin_features_used"]
        y_true_margin = df["margin_pct"].values
        y_pred_margin = self.margin_model.predict(df[m_feats].values)

        # ── Suitability predictions ───────────────────────────────────────────
        df["predicted_margin"] = y_pred_margin
        df["budget_per_acre"]  = self.feat_lists["median_budget_per_acre"]
        s_feats = self.feat_lists["suit_features_used"]
        y_true_suit = df["is_suitable"].astype(int).values
        y_pred_suit = self.suit_model.predict(df[s_feats].values)
        y_prob_suit = self.suit_model.predict_proba(df[s_feats].values)[:, 1]

        # ── Reports ──────────────────────────────────────────────────────────
        self._write_reg_report("yield_model_report.txt", "Yield Model",
                               y_true_yield, y_pred_yield, df)
        self._write_reg_report("margin_model_report.txt", "Margin Model",
                               y_true_margin, y_pred_margin, df)
        self._write_suit_report("suitability_report.txt",
                                y_true_suit, y_pred_suit, y_prob_suit, df)

        # ── Plots ─────────────────────────────────────────────────────────────
        self._plot_feature_importance()
        self._plot_pred_vs_actual(
            y_true_yield, y_pred_yield, y_true_margin, y_pred_margin
        )
        self._plot_confusion_matrix(y_true_suit, y_pred_suit)

        print("\n✅  Evaluation complete — outputs in evaluation/")

    # ─────────────────────────────────────────────────────────────────────────
    def _write_reg_report(
        self, filename: str, title: str,
        y_true: np.ndarray, y_pred: np.ndarray, df: pd.DataFrame
    ) -> None:
        mae  = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2   = _r2(y_true, y_pred)

        lines = [
            f"{'=' * 52}",
            f"  {title} — Test Set Report",
            f"{'=' * 52}",
            f"  Overall MAE  : {mae:.4f}",
            f"  Overall RMSE : {rmse:.4f}",
            f"  Overall R²   : {r2:.4f}",
            "",
        ]

        if "crop" in df.columns:
            lines += ["  Per-Crop Breakdown:", "-" * 40]
            for crop, grp in df.groupby("crop"):
                idx = grp.index
                m = mean_absolute_error(y_true[idx], y_pred[idx])
                r = _r2(y_true[idx], y_pred[idx])
                lines.append(f"  {crop:15s}  MAE={m:.3f}  R²={r:.3f}  n={len(grp)}")

        if "soil_type" in df.columns:
            lines += ["", "  Per-Soil-Type Breakdown:", "-" * 40]
            for st, grp in df.groupby("soil_type"):
                idx = grp.index
                m = mean_absolute_error(y_true[idx], y_pred[idx])
                r = _r2(y_true[idx], y_pred[idx])
                lines.append(f"  {st:20s}  MAE={m:.3f}  R²={r:.3f}  n={len(grp)}")

        path = CFG.EVAL_DIR / filename
        path.write_text("\n".join(lines))
        print(f"  📄 Saved → {path}")

    # ─────────────────────────────────────────────────────────────────────────
    def _write_suit_report(
        self, filename: str,
        y_true: np.ndarray, y_pred: np.ndarray,
        y_prob: np.ndarray, df: pd.DataFrame
    ) -> None:
        roc = roc_auc_score(y_true, y_prob)
        report = classification_report(y_true, y_pred, target_names=["Not Suitable", "Suitable"])

        lines = [
            "=" * 52,
            "  Suitability Model — Test Set Report",
            "=" * 52,
            f"  ROC-AUC : {roc:.4f}",
            "",
            report,
        ]

        if "crop" in df.columns:
            lines += ["  Per-Crop Precision / Recall / F1:", "-" * 40]
            for crop, grp in df.groupby("crop"):
                idx = grp.index
                yt = y_true[idx]; yp = y_pred[idx]
                if len(np.unique(yt)) < 2:
                    continue
                f1 = f1_score(yt, yp, zero_division=0)
                acc = accuracy_score(yt, yp)
                lines.append(f"  {crop:15s}  acc={acc:.3f}  f1={f1:.3f}  n={len(grp)}")

        path = CFG.EVAL_DIR / filename
        path.write_text("\n".join(lines))
        print(f"  📄 Saved → {path}")

    # ─────────────────────────────────────────────────────────────────────────
    def _plot_feature_importance(self) -> None:
        # Changed facecolor to white and title color to black
        fig, axes = plt.subplots(1, 3, figsize=(18, 7),
                                 facecolor="white", tight_layout=True)
        fig.suptitle("Feature Importance — Top 10 per Model",
                     color="black", fontsize=14, fontweight="bold", y=1.01)

        models_info = [
            (self.yield_model,  self.feat_lists["yield_features_used"],  "Yield Model (RF)",   _PALETTE[0]),
            (self.margin_model, self.feat_lists["margin_features_used"], "Margin Model (XGB)", _PALETTE[1]),
            (self.suit_model,   self.feat_lists["suit_features_used"],   "Suit. Model (XGB)",  _PALETTE[2]),
        ]

        for ax, (model, feats, title, color) in zip(axes, models_info):
            ax.set_facecolor("#f9f9f9") # Light grey for the plot area
            try:
                imp = model.feature_importances_
            except AttributeError:
                ax.text(0.5, 0.5, "N/A", ha="center", va="center", color="black")
                continue
            top_n = min(10, len(feats))
            idx   = np.argsort(imp)[-top_n:]
            ax.barh([feats[i] for i in idx], imp[idx], color=color, alpha=0.85)
            ax.set_title(title, color="black", fontsize=11, pad=8)
            ax.tick_params(colors="black", labelsize=8)
            ax.spines[:].set_color("#cccccc") # Subtle grey borders

        path = CFG.EVAL_DIR / "feature_importance.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  📊 Saved → {path}")

    # ─────────────────────────────────────────────────────────────────────────
    def _plot_pred_vs_actual(
        self, y_true_y, y_pred_y, y_true_m, y_pred_m
    ) -> None:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6),
                                 facecolor="white", tight_layout=True)
        fig.suptitle("Predicted vs Actual", color="black", fontsize=14, fontweight="bold")

        for ax, (yt, yp, label, color) in zip(
            axes,
            [
                (y_true_y, y_pred_y, "Yield (qtl/acre)", _PALETTE[0]),
                (y_true_m, y_pred_m, "Margin (%)",       _PALETTE[1]),
            ],
        ):
            ax.set_facecolor("#f9f9f9")
            ax.scatter(yt, yp, s=12, alpha=0.5, color=color)
            lim = (min(yt.min(), yp.min()) * 0.95, max(yt.max(), yp.max()) * 1.05)
            ax.plot(lim, lim, "--", color="grey", linewidth=0.8, alpha=0.5)
            r2 = _r2(yt, yp)
            ax.set_xlabel("Actual", color="black", fontsize=10)
            ax.set_ylabel("Predicted", color="black", fontsize=10)
            ax.set_title(f"{label}  R²={r2:.3f}", color="black", fontsize=11)
            ax.tick_params(colors="black", labelsize=8)
            ax.spines[:].set_color("#cccccc")

        path = CFG.EVAL_DIR / "prediction_vs_actual.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  📊 Saved → {path}")

    # ─────────────────────────────────────────────────────────────────────────
    def _plot_confusion_matrix(self, y_true: np.ndarray, y_pred: np.ndarray) -> None:
        cm = confusion_matrix(y_true, y_pred)
        fig, ax = plt.subplots(figsize=(6, 5), facecolor="white")
        ax.set_facecolor("white")
        
        # Switched cmap to "YlGn" (Yellow-Green) which often looks better on light themes
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="YlGn",
            xticklabels=["Not Suitable", "Suitable"],
            yticklabels=["Not Suitable", "Suitable"],
            ax=ax, linewidths=0.5,
            annot_kws={"color": "black"}, # Text inside boxes is now black
        )
        ax.set_title("Suitability Model — Confusion Matrix", color="black",
                     fontsize=12, pad=12)
        ax.set_xlabel("Predicted", color="black"); ax.set_ylabel("Actual", color="black")
        ax.tick_params(colors="black")
        
        path = CFG.EVAL_DIR / "confusion_matrix.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  📊 Saved → {path}")


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    Evaluator().run()
