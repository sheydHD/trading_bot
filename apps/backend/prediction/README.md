# Prediction Engine — ML Direction Forecasting

Ensemble machine-learning pipeline that predicts 5-day stock/crypto price
direction using XGBoost + Logistic Regression with walk-forward validation,
noise-filtered targets, and probability calibration.

---

## Pipeline Overview

```
┌──────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│  features.py │    │      model.py       │    │    scoring.py    │
│              │    │                     │    │                  │
│ fetch_ohlcv()│───►│ walk_forward_       │    │ compute_         │
│ compute_     │    │   validate()        │    │   technical_     │
│   technical_ │    │ train()             │    │   score()        │
│   features() │    │ predict()           │───►│ compute_         │
│ create_      │    │                     │    │   fundamental_   │
│   target()   │    │ StockPredictor      │    │   score()        │
│              │    │ (XGB + LR ensemble) │    │ compute_         │
└──────┬───────┘    └─────────┬───────────┘    │   overall_       │
       │                      │                │   score()        │
       │                      │                └────────┬─────────┘
       ▼                      ▼                         ▼
┌───────────────────────────────────────────────────────────────────┐
│                        analyzer.py                                │
│  _analyze_stock()  ·  _analyze_crypto()  ·  run_prediction_      │
│                                              analysis()          │
└───────────────────────────────────────────┬───────────────────────┘
                                            ▼
┌───────────────────────────────────────────────────────────────────┐
│  run_analysis.py — subprocess entry-point (invoked by Flask API) │
└───────────────────────────────────────────────────────────────────┘
```

---

## Feature Engineering (`features.py`)

### Data Source

`fetch_ohlcv(symbol, period="5y")` downloads daily OHLCV via **yfinance**.
5 years ≈ 1 250 rows — sufficient for expanding-window walk-forward
validation after the 99-row SMA100 warmup.

### Feature Vector (24 columns)

`FEATURE_COLS` defines the ML input. Every feature is either
scale-invariant or normalised by price, allowing the model to learn
cross-asset patterns.

| Category | # | Features | Rationale |
|----------|---|----------|-----------|
| **Trend** | 6 | `price_vs_sma{20,50,100}`, `macd_norm`, `macd_signal_norm`, `macd_hist_norm` | Relative distance to SMAs; MACD normalised by price for cross-stock comparability |
| **Momentum** | 5 | `rsi_14`, `rsi_delta_5`, `stoch_k`, `stoch_d`, `adx` | RSI, Stochastic oscillator, trend strength; `rsi_delta_5` captures momentum acceleration |
| **Volatility** | 3 | `bb_pct`, `atr_pct`, `volatility_20d` | Bollinger %B, ATR/price, realised vol — all dimensionless ratios |
| **Volume** | 1 | `volume_ratio` | Current volume / 20-day SMA — detects unusual activity |
| **Returns** | 5 | `return_{1,5,20,60,120}d` | Multi-horizon momentum (Jegadeesh–Titman 6-month momentum at 120d) |
| **Regime** | 4 | `momentum_quality_60`, `trend_strength_60`, `range_position_60d`, `up_days_ratio_20` | Win-rate, R² of trend, position in range, recent up-day fraction |

**Key helper**: `_rolling_r2(series, window=60)` computes rolling
$R^2$ of price vs. time — measures how consistent (non-noisy) the
current trend is.

### Target Variable

`create_target(df, horizon=5, noise_filter=True)` builds a binary label:

$$
\text{target} = \begin{cases}
1 & \text{if } r_{t+5} > 0.2 \cdot \sigma \cdot \sqrt{5} \\
0 & \text{if } r_{t+5} < -0.2 \cdot \sigma \cdot \sqrt{5} \\
\text{NaN} & \text{otherwise (excluded from training)}
\end{cases}
$$

where $\sigma$ is 20-day realised volatility and the threshold is
floored at 0.2 %. This **noise filter** removes ambiguous tiny moves,
improving label quality and model calibration.

### Experimental Utilities (not used in production)

| Function | Purpose | Status |
|----------|---------|--------|
| `fetch_market_context()` | Download SPY + VIX (cached per session) | Available |
| `add_macro_features()` | Merge VIX level, SPY momentum, relative-strength | Available |
| `create_alpha_target()` | Excess-return target (stock vs SPY) | Available |

Ablation study across 10 stocks showed these **hurt** average accuracy
by 1–2 %, likely due to multicollinearity with existing features at
this data scale. Kept for future experimentation.

---

## Model (`model.py`)

### Architecture

**Soft-vote ensemble** of XGBoost (60 %) + Logistic Regression (40 %):

$$
p_{\text{up}} = 0.6 \cdot p_{\text{XGB}} + 0.4 \cdot p_{\text{LR}}
$$

LR provides a regularised linear baseline that is robust to small
samples. XGB captures non-linear interactions. The blend reduces
variance compared to either model alone.

### Walk-Forward Validation

```
time ──────────────────────────────────────────────────►

Fold 1: [=== train (252d) ===]..gap..[test 63d]
Fold 2: [======= train (315d) =======]..gap..[test 63d]
Fold 3: [=========== train (378d) ===========]..gap..[test 63d]
         ...expanding...                       5-day purge
```

- **Expanding window**: each fold starts at day 0 (no data is discarded)
- **`min_train = 252`**: ~1 year initial training set
- **`test_window = 63`**: ~3 months per fold — large enough for stable metrics
- **`PURGE_GAP = 5`**: 5-day gap between train/test boundaries prevents
  target look-ahead leakage (matches `PREDICTION_HORIZON`)
- **Early stopping** (`EARLY_STOP = 30`): halts XGB training when
  validation loss plateaus; last 20% of training data used as eval set

### Class Balancing

Per-fold `scale_pos_weight = n_negative / n_positive` corrects for any
class imbalance. LR uses `class_weight="balanced"` separately.

### Probability Calibration

After walk-forward validation, the model's historical accuracy is
converted to an **attenuation factor** that shrinks raw probabilities
toward 0.5:

$$
p_{\text{cal}} = 0.5 + (p_{\text{raw}} - 0.5) \cdot f_{\text{cal}}
$$

where $f_{\text{cal}} = \min(1.0, \max(0.15, (acc - 0.40) \times 4.0))$:

| Walk-Forward Accuracy | Calibration Factor | Effect |
|----------------------:|-------------------:|--------|
| 45% | 0.20 | Near-zero signal |
| 50% | 0.40 | Slight preference |
| 55% | 0.60 | Moderate conviction |
| 60% | 0.80 | Strong signal |
| 65%+ | 1.00 | Full confidence |

### NEUTRAL Threshold

If calibrated confidence $< 52\%$, the prediction is set to
**NEUTRAL** — the model lacks sufficient conviction for a directional
call. This prevents noisy predictions from influencing user decisions.

### Default Hyperparameters

```python
DEFAULT_PARAMS = {
    "n_estimators": 500,       # upper bound (early stopping cuts)
    "max_depth": 3,            # shallow → less overfitting
    "learning_rate": 0.03,
    "subsample": 0.7,
    "colsample_bytree": 0.7,
    "min_child_weight": 10,    # large → more regularisation
    "gamma": 1.0,              # pruning threshold
    "reg_alpha": 0.5,          # L1
    "reg_lambda": 2.0,         # L2
}
```

### Optuna Tuning (optional)

`tune_hyperparameters(X, y, n_trials=40)` runs Bayesian optimisation
via TPE sampler, maximising walk-forward accuracy. Disabled in
production by default — useful for per-stock experiments.

---

## Scoring (`scoring.py`)

Three independent 0–100 scores combined into a weighted overall score.

### Technical Score

Starts at 50. Adjusts based on:
- RSI zones: oversold (< 30: +12) / overbought (> 70: −12)
- MACD histogram sign: ±10
- Price vs SMA20/50/100: ±4/5/6
- ADX > 25 (strong trend): +5
- Bollinger %B near bands: ±6
- Volume surge (> 1.5×): +4

### Fundamental Score

Starts at 50. Evaluates: P/E, PEG, ROE, revenue growth, profit
margins, debt-to-equity. **Stocks only** (cryptos skip this).

### Overall Score

Dynamic weighting based on ML model accuracy:

$$
\text{score} = w_T \cdot S_T + w_F \cdot S_F + w_{ML} \cdot S_{ML}
$$

| Accuracy | ML Weight | Tech Weight | Fundamental Weight |
|---------:|----------:|------------:|-------------------:|
| ≤ 52% | 10% | 49.5% | 40.5% |
| 56% | 28% | 39.6% | 32.4% |
| 60%+ | 40% | 33.0% | 27.0% |

When the model has no edge ($acc \leq 52\%$), score is driven almost
entirely by technical + fundamental analysis. As accuracy rises, ML
earns more influence.

---

## Analyzer (`analyzer.py`)

Orchestrates the full pipeline per asset.

### `_analyze_stock(symbol, fundamentals, model_params=None)`

1. `fetch_ohlcv(symbol, "5y")` → daily OHLCV
2. `compute_technical_features(ohlcv)` → 24 features
3. `create_target(df, horizon=5)` → noise-filtered binary label
4. Drop NaN rows (SMA warmup + noise filter)
5. If rows ≥ 120: walk-forward validate → train → predict
6. If rows < 120: skip ML, use technical-only scoring
7. Compute technical + fundamental + overall scores
8. Assemble result dict with all metadata

### `_analyze_crypto(symbol, model_params=None)`

Same as stocks but: no fundamentals fetch, `fundamental_score = 50`
(neutral), no sector/name metadata.

### `run_prediction_analysis(status_callback=None)`

1. Fetch fundamentals for all `PREDICTION_STOCKS` (parallel, 4 threads)
2. Analyze each stock (parallel, 4 threads)
3. Analyze each crypto (parallel, 4 threads)
4. Analyze wallet holdings (`WALLET_STOCKS` + `WALLET_CRYPTOS`)
5. Compute aggregate metadata (avg accuracy, feature count, etc.)
6. Return complete result payload

Reports progress via `status_callback(step, total, name)`.

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `PREDICTION_HORIZON` | 5 | Trading days to predict ahead |
| `MIN_ROWS_FOR_ML` | 120 | Minimum feature rows to attempt XGBoost |
| `MAX_WORKERS_IO` | 4 | ThreadPoolExecutor max workers |

---

## Subprocess Entry-Point (`run_analysis.py`)

Invoked by the Flask API:

```bash
python -m apps.backend.prediction.run_analysis
```

1. Loads `.env` → configures logging
2. Calls `run_prediction_analysis(status_callback=_write_status)`
3. Writes progress to `STATUS_FILE` (read by API `/status` endpoint)
4. Saves results to `PersistentCache` (read by API `/latest` endpoint)
5. Exits with code 0 (success) or 1 (failure)

---

## Performance Characteristics

| Metric | Typical Value |
|--------|---------------|
| Total analysis time | 5–8 minutes |
| Stocks analyzed | 34 (20 prediction + 16 wallet, ~2 overlap) |
| Cryptos analyzed | 14 (10 prediction + 6 wallet, ~2 overlap) |
| Walk-forward folds per stock | 12–16 (5 years data) |
| Average model accuracy | ~50% (efficient-market baseline) |
| Predictions with NEUTRAL | ~25% of stocks |
