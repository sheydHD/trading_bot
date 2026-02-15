#!/usr/bin/env python3
"""Diagnostic script to identify why the prediction model performs poorly.

Tests on 3 stocks for speed. Investigates:
1. Target class balance
2. Feature NaN rates
3. Data leakage in target construction
4. Walk-forward vs random split comparison
5. Feature importance / signal analysis
6. Probability distribution of predictions
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from apps.backend.prediction.features import (
    TECHNICAL_FEATURE_COLS, FUNDAMENTAL_FEATURE_COLS,
    fetch_ohlcv, fetch_fundamentals, build_feature_matrix, create_target,
    compute_technical_features,
)

TEST_STOCKS = ["AAPL", "MSFT", "NVDA"]
HORIZON = 5

def diagnose_single(symbol: str):
    print(f"\n{'='*70}")
    print(f"  DIAGNOSING: {symbol}")
    print(f"{'='*70}")

    # 1. Fetch data
    ohlcv = fetch_ohlcv(symbol, period="2y")
    if ohlcv is None:
        print("  FAILED: No OHLCV data")
        return
    print(f"\n[1] OHLCV rows: {len(ohlcv)}")
    print(f"    Date range: {ohlcv.index[0].date()} to {ohlcv.index[-1].date()}")

    fundamentals = fetch_fundamentals(symbol)
    print(f"    Fundamentals available: {sum(1 for v in fundamentals.values() if v is not None)}/{len(fundamentals)}")

    # 2. Build features
    df, feature_cols = build_feature_matrix(ohlcv, fundamentals)
    target = create_target(df, horizon=HORIZON)
    df["target"] = target

    print(f"\n[2] FEATURE NaN RATES (after build_feature_matrix):")
    for col in feature_cols:
        nan_rate = df[col].isna().mean()
        if nan_rate > 0:
            print(f"    {col}: {nan_rate:.1%} NaN ({df[col].isna().sum()}/{len(df)})")

    # 3. After dropping NaN on technical cols
    valid = df.dropna(subset=TECHNICAL_FEATURE_COLS + ["target"]).copy()
    for col in feature_cols:
        if col not in TECHNICAL_FEATURE_COLS:
            valid[col] = valid[col].fillna(0)
    print(f"\n[3] VALID ROWS after dropna: {len(valid)}/{len(df)} ({len(valid)/len(df):.0%})")

    X = valid[feature_cols]
    y = valid["target"]

    # 4. Target balance
    counts = y.value_counts()
    print(f"\n[4] TARGET BALANCE:")
    print(f"    UP (1): {counts.get(1, 0)} ({counts.get(1, 0)/len(y):.1%})")
    print(f"    DOWN (0): {counts.get(0, 0)} ({counts.get(0, 0)/len(y):.1%})")

    # 5. Check for autocorrelation / sequential bias
    # Look at target distribution in first half vs second half
    mid = len(y) // 2
    first_half_up = y.iloc[:mid].mean()
    second_half_up = y.iloc[mid:].mean()
    print(f"\n[5] TEMPORAL TARGET DRIFT:")
    print(f"    First half UP rate:  {first_half_up:.1%}")
    print(f"    Second half UP rate: {second_half_up:.1%}")
    print(f"    Last 60 days UP rate: {y.iloc[-60:].mean():.1%}")
    print(f"    Last 30 days UP rate: {y.iloc[-30:].mean():.1%}")

    # 6. Feature correlation with target
    print(f"\n[6] TOP FEATURE CORRELATIONS WITH TARGET:")
    corrs = X.corrwith(y).abs().sort_values(ascending=False)
    for feat, corr in corrs.head(10).items():
        print(f"    {feat}: {corr:.4f}")
    print(f"    ... Average absolute correlation: {corrs.mean():.4f}")

    # 7. Walk-forward test with current params
    print(f"\n[7] WALK-FORWARD VALIDATION (train=180, test=21):")
    train_window, test_window = 180, 21
    all_preds, all_actuals, all_probs = [], [], []

    for start in range(0, len(X) - train_window - test_window, test_window):
        train_end = start + train_window
        test_end = min(train_end + test_window, len(X))
        X_train, y_train = X.iloc[start:train_end], y.iloc[start:train_end]
        X_test, y_test = X.iloc[train_end:test_end], y.iloc[train_end:test_end]

        if y_train.nunique() < 2:
            continue

        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_train.fillna(0))
        X_te = scaler.transform(X_test.fillna(0))

        model = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            random_state=42, eval_metric="logloss", verbosity=0,
        )
        model.fit(X_tr, y_train, verbose=False)
        preds = model.predict(X_te)
        probs = model.predict_proba(X_te)[:, 1]

        all_preds.extend(preds.tolist())
        all_actuals.extend(y_test.values.tolist())
        all_probs.extend(probs.tolist())

    if all_preds:
        acc = accuracy_score(all_actuals, all_preds)
        print(f"    Accuracy: {acc:.4f}")
        print(f"    Predictions UP: {sum(all_preds)}/{len(all_preds)} ({sum(all_preds)/len(all_preds):.1%})")
        print(f"    Actuals UP:     {sum(all_actuals)}/{len(all_actuals)} ({sum(all_actuals)/len(all_actuals):.1%})")
        probs_arr = np.array(all_probs)
        print(f"    Prob UP distribution: mean={probs_arr.mean():.3f}, std={probs_arr.std():.3f}, min={probs_arr.min():.3f}, max={probs_arr.max():.3f}")
        print(f"    Prob UP > 0.5: {(probs_arr > 0.5).sum()}/{len(probs_arr)}")
    else:
        print("    NO VALID FOLDS!")

    # 8. Train on all data, predict latest
    print(f"\n[8] FINAL PREDICTION (train on all, predict latest):")
    scaler = StandardScaler()
    X_all = scaler.fit_transform(X.fillna(0))
    model = XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        random_state=42, eval_metric="logloss", verbosity=0,
    )
    model.fit(X_all, y, verbose=False)

    latest_X = X.iloc[[-1]]
    latest_scaled = scaler.transform(latest_X.fillna(0))
    prob = model.predict_proba(latest_scaled)
    print(f"    Prob [DOWN, UP] = {prob[0]}")
    print(f"    Direction: {'UP' if prob[0][1] > 0.5 else 'DOWN'}")

    # 9. Feature importance
    print(f"\n[9] FEATURE IMPORTANCE (from final model):")
    importances = dict(zip(feature_cols, model.feature_importances_))
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1])[:10]:
        print(f"    {feat}: {imp:.4f}")

    # 10. Check: random baseline
    from sklearn.dummy import DummyClassifier
    dummy = DummyClassifier(strategy="stratified", random_state=42)
    dummy.fit(X_all, y)
    dummy_acc = dummy.score(X_all, y)
    print(f"\n[10] RANDOM BASELINE accuracy: {dummy_acc:.4f}")

    # 11. Check: simpler model (logistic regression)
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr_preds, lr_actuals = [], []
    for start in range(0, len(X) - train_window - test_window, test_window):
        train_end = start + train_window
        test_end = min(train_end + test_window, len(X))
        X_train, y_train = X.iloc[start:train_end], y.iloc[start:train_end]
        X_test, y_test = X.iloc[train_end:test_end], y.iloc[train_end:test_end]
        if y_train.nunique() < 2: continue
        sc = StandardScaler()
        X_tr = sc.fit_transform(X_train.fillna(0))
        X_te = sc.transform(X_test.fillna(0))
        lr.fit(X_tr, y_train)
        lr_preds.extend(lr.predict(X_te).tolist())
        lr_actuals.extend(y_test.values.tolist())
    if lr_preds:
        print(f"\n[11] LOGISTIC REGRESSION walk-forward accuracy: {accuracy_score(lr_actuals, lr_preds):.4f}")
        print(f"     Predictions UP: {sum(lr_preds)}/{len(lr_preds)} ({sum(lr_preds)/len(lr_preds):.1%})")

if __name__ == "__main__":
    for sym in TEST_STOCKS:
        diagnose_single(sym)
