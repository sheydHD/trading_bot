#!/usr/bin/env python3
"""Quick validation of the rewritten prediction pipeline on 3 stocks + 1 crypto.

Run:  poetry run python scripts/test_accuracy.py
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from apps.backend.prediction.features import (
    FEATURE_COLS, fetch_ohlcv, compute_technical_features, create_target,
)
from apps.backend.prediction.model import StockPredictor, tune_hyperparameters, DEFAULT_PARAMS

TICKERS = ["AAPL", "MSFT", "NVDA"]
CRYPTO = "BTC-USD"
HORIZON = 5

def test_stock(symbol, params=None):
    print(f"\n{'='*60}")
    print(f"  {symbol}")
    print(f"{'='*60}")
    ohlcv = fetch_ohlcv(symbol, period="5y")
    if ohlcv is None:
        print(f"  SKIP – no data")
        return None

    print(f"  OHLCV rows: {len(ohlcv)}")
    df = compute_technical_features(ohlcv)
    target = create_target(df, horizon=HORIZON)
    df["target"] = target
    valid = df.dropna(subset=FEATURE_COLS + ["target"]).copy()
    print(f"  Valid rows: {len(valid)}  (lost {len(ohlcv) - len(valid)} to warmup/NaN)")
    print(f"  Target UP %: {valid['target'].mean():.1%}")
    print(f"  Features: {len(FEATURE_COLS)}")

    X = valid[FEATURE_COLS]
    y = valid["target"]

    t0 = time.time()
    predictor = StockPredictor(params=params)
    metrics = predictor.walk_forward_validate(X, y)
    predictor.train(X, y)
    elapsed = time.time() - t0

    prediction = predictor.predict(df[FEATURE_COLS].iloc[[-1]])

    print(f"  Walk-forward  : acc={metrics['accuracy']:.3f}  "
          f"prec={metrics.get('precision',0):.3f}  "
          f"rec={metrics.get('recall',0):.3f}  "
          f"folds={metrics.get('n_folds',0)}")
    print(f"  Predicted %UP : {metrics.get('pct_up_pred', 0):.1%}  "
          f"(actual %UP: {metrics.get('pct_up_actual', 0):.1%})")
    print(f"  Latest pred   : {prediction['direction']}  "
          f"prob_up={prediction['probability_up']:.3f}  "
          f"confidence={prediction['confidence']:.3f}")
    print(f"  Time          : {elapsed:.1f}s")

    if predictor.feature_importance:
        top5 = sorted(predictor.feature_importance.items(), key=lambda x: -x[1])[:5]
        print(f"  Top features  : {', '.join(f'{k}={v:.3f}' for k,v in top5)}")

    return metrics.get("accuracy")


def main():
    print("=" * 60)
    print("  PREDICTION PIPELINE VALIDATION (default params)")
    print("=" * 60)

    accuracies = []
    for sym in TICKERS:
        acc = test_stock(sym)
        if acc is not None:
            accuracies.append(acc)

    # Also test a crypto
    acc = test_stock(CRYPTO)
    if acc is not None:
        accuracies.append(acc)

    if accuracies:
        print(f"\n{'='*60}")
        print(f"  SUMMARY: avg accuracy = {np.mean(accuracies):.3f}")
        print(f"  per-ticker: {[f'{a:.3f}' for a in accuracies]}")
        print(f"{'='*60}")

    # --- Optuna tuning on AAPL ---
    print(f"\n{'='*60}")
    print(f"  OPTUNA TUNING on AAPL (40 trials)")
    print(f"{'='*60}")
    ohlcv = fetch_ohlcv("AAPL", period="5y")
    if ohlcv is not None:
        df = compute_technical_features(ohlcv)
        target = create_target(df, horizon=HORIZON)
        df["target"] = target
        valid = df.dropna(subset=FEATURE_COLS + ["target"])
        X, y = valid[FEATURE_COLS], valid["target"]

        t0 = time.time()
        best_params = tune_hyperparameters(X, y, n_trials=40)
        elapsed = time.time() - t0
        print(f"  Tuning time: {elapsed:.1f}s")

        # Re-test all with tuned params
        print(f"\n{'='*60}")
        print(f"  RE-TEST WITH TUNED PARAMS")
        print(f"{'='*60}")
        tuned_accs = []
        for sym in TICKERS + [CRYPTO]:
            acc = test_stock(sym, params=best_params)
            if acc is not None:
                tuned_accs.append(acc)
        if tuned_accs:
            print(f"\n{'='*60}")
            print(f"  TUNED SUMMARY: avg accuracy = {np.mean(tuned_accs):.3f}")
            print(f"  per-ticker: {[f'{a:.3f}' for a in tuned_accs]}")
            print(f"{'='*60}")


if __name__ == "__main__":
    main()
