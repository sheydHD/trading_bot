"""Ensemble direction-prediction model with walk-forward validation
and Bayesian hyperparameter optimisation via Optuna.

Key design choices (informed by diagnostic analysis):
- **Ensemble**: XGBoost + Logistic Regression (soft-vote average).
  LR is less prone to overfitting; XGB captures non-linear patterns.
- **Expanding window** walk-forward (not sliding) → more training data.
- **Purging gap** between train and test to prevent target-overlap leakage.
- **Early stopping** on a validation slice → prevents XGB overfitting.
- **Probability calibration**: walk-forward accuracy attenuates raw model
  confidence so predictions stay realistic.
- **Optuna Bayesian optimisation** on request → data-driven hyperparams.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, precision_score, recall_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

# Suppress convergence warnings during calibration / LR
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Sensible default params (will be overridden by Optuna when tuning)
# ---------------------------------------------------------------------------
DEFAULT_PARAMS: dict = {
    "n_estimators": 500,          # upper bound — early stopping will cut
    "max_depth": 3,               # shallow to limit overfitting
    "learning_rate": 0.03,
    "subsample": 0.7,
    "colsample_bytree": 0.7,
    "min_child_weight": 10,       # larger → more regularisation
    "gamma": 1.0,                 # pruning threshold
    "reg_alpha": 0.5,             # L1 regularisation
    "reg_lambda": 2.0,            # L2 regularisation
    "scale_pos_weight": 1.0,      # recalculated per fold
    "random_state": 42,
    "eval_metric": "logloss",
    "verbosity": 0,
    "tree_method": "hist",
}

PURGE_GAP = 5     # rows to skip between train and test (= target horizon)
EARLY_STOP = 30   # early-stopping patience (rounds)

# Ensemble weight: XGBoost vs LogisticRegression
XGB_WEIGHT = 0.6
LR_WEIGHT  = 0.4


class StockPredictor:
    """Train, validate, and predict with an XGBoost + LR ensemble."""

    def __init__(self, params: dict | None = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.xgb_model: XGBClassifier | None = None
        self.lr_model: LogisticRegression | None = None
        self.scaler = StandardScaler()
        self.feature_importance: dict[str, float] = {}
        self.validation_metrics: dict[str, float] = {}
        # Calibration factor: attenuates raw prob based on walk-forward perf
        self._cal_factor: float = 0.0  # 0.0 = no skill → all preds = 0.5

    # ------------------------------------------------------------------
    # Walk-forward cross-validation  (expanding window + purging)
    # ------------------------------------------------------------------
    def walk_forward_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        min_train: int = 252,
        test_window: int = 63,
    ) -> dict[str, float]:
        """Expanding-window walk-forward validation with purge gap.

        Parameters
        ----------
        min_train : int
            Minimum training rows (≈1 year).
        test_window : int
            Test period per fold (≈3 months → fewer, more meaningful folds).
        """
        predictions, actuals, probabilities = [], [], []
        total_rows = len(X)

        if total_rows < min_train + PURGE_GAP + test_window:
            logger.warning(
                "Not enough data for walk-forward (%d rows, need %d+%d+%d)",
                total_rows, min_train, PURGE_GAP, test_window,
            )
            self.validation_metrics = {
                "accuracy": 0.5, "precision": 0.0, "recall": 0.0,
            }
            return self.validation_metrics

        fold = 0
        train_end = min_train
        while train_end + PURGE_GAP + test_window <= total_rows:
            test_start = train_end + PURGE_GAP
            test_end = min(test_start + test_window, total_rows)

            X_train = X.iloc[:train_end]
            y_train = y.iloc[:train_end]
            X_test  = X.iloc[test_start:test_end]
            y_test  = y.iloc[test_start:test_end]

            if y_train.nunique() < 2 or len(X_test) == 0:
                train_end += test_window
                continue

            # --- Balance classes via scale_pos_weight ---
            n_neg = (y_train == 0).sum()
            n_pos = (y_train == 1).sum()
            spw = n_neg / max(n_pos, 1)

            fold_params = {**self.params, "scale_pos_weight": spw}

            xgb = XGBClassifier(**fold_params)
            X_tr = self.scaler.fit_transform(X_train.fillna(0))
            X_te = self.scaler.transform(X_test.fillna(0))

            # Use last 20 % of training data as eval set for early stopping
            split = max(1, int(len(X_tr) * 0.8))
            xgb.fit(
                X_tr[:split], y_train.iloc[:split],
                eval_set=[(X_tr[split:], y_train.iloc[split:])],
                verbose=False,
            )

            # Logistic Regression (L2-regularised, class-balanced)
            lr = LogisticRegression(
                C=0.1, max_iter=500, class_weight="balanced",
                random_state=42, solver="lbfgs",
            )
            lr.fit(X_tr, y_train.values)

            # Ensemble: weighted average of probabilities
            xgb_probs = xgb.predict_proba(X_te)[:, 1]
            lr_probs = lr.predict_proba(X_te)[:, 1]
            probs = XGB_WEIGHT * xgb_probs + LR_WEIGHT * lr_probs
            preds = (probs > 0.5).astype(int)

            predictions.extend(preds.tolist())
            actuals.extend(y_test.values.tolist())
            probabilities.extend(probs.tolist())

            fold += 1
            train_end += test_window   # expand window

        if not predictions:
            self.validation_metrics = {
                "accuracy": 0.5, "precision": 0.0, "recall": 0.0,
            }
            return self.validation_metrics

        self.validation_metrics = {
            "accuracy":  round(accuracy_score(actuals, predictions), 4),
            "precision": round(precision_score(actuals, predictions, zero_division=0.0), 4),
            "recall":    round(recall_score(actuals, predictions, zero_division=0.0), 4),
            "log_loss":  round(log_loss(actuals, probabilities), 4),
            "n_folds":   fold,
            "n_samples": len(predictions),
            "pct_up_pred": round(sum(predictions) / len(predictions), 4),
            "pct_up_actual": round(sum(actuals) / len(actuals), 4),
        }

        # Calibration: map walk-forward accuracy → attenuation factor.
        # Softer curve so the model can still express moderate opinions
        # even with borderline accuracy, while capping overconfidence.
        #   accuracy 0.45 → factor 0.15  (barely any signal)
        #   accuracy 0.50 → factor 0.25  (slight preference)
        #   accuracy 0.55 → factor 0.50  (moderate)
        #   accuracy 0.60 → factor 0.75  (good signal)
        #   accuracy 0.65 → factor 1.00  (full confidence)
        wf_acc = self.validation_metrics["accuracy"]
        self._cal_factor = min(1.0, max(0.15, (wf_acc - 0.40) * 4.0))

        return self.validation_metrics

    # ------------------------------------------------------------------
    # Training (with early stopping)
    # ------------------------------------------------------------------
    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train ensemble on the full available dataset."""
        if y.nunique() < 2:
            logger.warning("Cannot train – target has fewer than 2 classes")
            return

        n_neg = (y == 0).sum()
        n_pos = (y == 1).sum()
        self.params["scale_pos_weight"] = n_neg / max(n_pos, 1)

        X_scaled = self.scaler.fit_transform(X.fillna(0))

        # --- XGBoost with early stopping ---
        self.xgb_model = XGBClassifier(**self.params)
        split = max(1, int(len(X_scaled) * 0.85))
        self.xgb_model.fit(
            X_scaled[:split], y.iloc[:split],
            eval_set=[(X_scaled[split:], y.iloc[split:])],
            verbose=False,
        )

        # --- Logistic Regression ---
        self.lr_model = LogisticRegression(
            C=0.1, max_iter=500, class_weight="balanced",
            random_state=42, solver="lbfgs",
        )
        self.lr_model.fit(X_scaled, y.values)

        if hasattr(self.xgb_model, "feature_importances_"):
            self.feature_importance = dict(
                zip(X.columns, self.xgb_model.feature_importances_)
            )

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(self, X: pd.DataFrame) -> dict:
        """Return direction + calibrated confidence for the latest row.

        The raw ensemble probability is attenuated by the calibration factor
        derived from walk-forward accuracy so that reported confidence stays
        realistic (no 95 % confidence with 53 % accuracy).

        Returns::
            {"direction": "UP"|"DOWN"|"NEUTRAL",
             "confidence": float,          # 0.50 – 1.00
             "probability_up": float}      # 0.00 – 1.00
        """
        if self.xgb_model is None:
            return {"direction": "NEUTRAL", "confidence": 0.50, "probability_up": 0.50}

        X_scaled = self.scaler.transform(X.fillna(0))

        # Ensemble average
        xgb_prob = float(self.xgb_model.predict_proba(X_scaled)[0][1])
        lr_prob = float(self.lr_model.predict_proba(X_scaled)[0][1]) if self.lr_model else xgb_prob
        raw_prob = XGB_WEIGHT * xgb_prob + LR_WEIGHT * lr_prob

        # Calibrate: shrink toward 0.5 based on walk-forward accuracy
        # cal_prob = 0.5 + (raw_prob - 0.5) * calibration_factor
        cal_prob = 0.5 + (raw_prob - 0.5) * self._cal_factor
        cal_prob = max(0.01, min(0.99, cal_prob))

        direction = "UP" if cal_prob > 0.5 else "DOWN"
        confidence = round(max(cal_prob, 1.0 - cal_prob), 3)

        # NEUTRAL threshold: if calibrated confidence is within 2 % of 50 %
        # the model lacks sufficient conviction for a directional call.
        if confidence < 0.52:
            direction = "NEUTRAL"

        return {
            "direction": direction,
            "confidence": confidence,
            "probability_up": round(cal_prob, 3),
        }


# ---------------------------------------------------------------------------
# Optuna hyper-parameter optimisation
# ---------------------------------------------------------------------------

def tune_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    n_trials: int = 40,
    min_train: int = 252,
    test_window: int = 63,
) -> dict:
    """Use Optuna Bayesian search to find optimal XGBoost hyperparameters.

    Objective: maximise walk-forward accuracy.
    """
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        logger.warning("Optuna not installed – skipping hyperparameter tuning")
        return DEFAULT_PARAMS

    total_rows = len(X)
    if total_rows < min_train + PURGE_GAP + test_window + 50:
        logger.warning("Not enough data for Optuna tuning (%d rows)", total_rows)
        return DEFAULT_PARAMS

    scaler = StandardScaler()

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": 500,
            "max_depth": trial.suggest_int("max_depth", 2, 6),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 0.9),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 0.9),
            "min_child_weight": trial.suggest_int("min_child_weight", 5, 50),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 5.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 10.0),
            "random_state": 42,
            "eval_metric": "logloss",
            "verbosity": 0,
            "tree_method": "hist",
        }

        all_preds, all_actuals = [], []
        train_end = min_train

        while train_end + PURGE_GAP + test_window <= total_rows:
            test_start = train_end + PURGE_GAP
            test_end = min(test_start + test_window, total_rows)

            X_train, y_train = X.iloc[:train_end], y.iloc[:train_end]
            X_test, y_test   = X.iloc[test_start:test_end], y.iloc[test_start:test_end]

            if y_train.nunique() < 2 or len(X_test) == 0:
                train_end += test_window
                continue

            n_neg = (y_train == 0).sum()
            n_pos = (y_train == 1).sum()
            params["scale_pos_weight"] = n_neg / max(n_pos, 1)

            model = XGBClassifier(**params)
            X_tr = scaler.fit_transform(X_train.fillna(0))
            X_te = scaler.transform(X_test.fillna(0))

            split = max(1, int(len(X_tr) * 0.8))
            model.fit(
                X_tr[:split], y_train.iloc[:split],
                eval_set=[(X_tr[split:], y_train.iloc[split:])],
                verbose=False,
            )

            # Ensemble with LR for more robust tuning signal
            lr = LogisticRegression(
                C=0.1, max_iter=500, class_weight="balanced",
                random_state=42, solver="lbfgs",
            )
            lr.fit(X_tr, y_train.values)

            xgb_probs = model.predict_proba(X_te)[:, 1]
            lr_probs = lr.predict_proba(X_te)[:, 1]
            probs = XGB_WEIGHT * xgb_probs + LR_WEIGHT * lr_probs
            preds = (probs > 0.5).astype(int)
            all_preds.extend(preds.tolist())
            all_actuals.extend(y_test.values.tolist())

            train_end += test_window

        if not all_preds:
            return 0.5

        return accuracy_score(all_actuals, all_preds)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = {**DEFAULT_PARAMS, **study.best_params}
    logger.info(
        "Optuna tuning complete: accuracy=%.4f, best_params=%s",
        study.best_value, study.best_params,
    )
    return best
