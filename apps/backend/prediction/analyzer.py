"""High-level analysis orchestrator.

Coordinates data fetching, feature engineering, model training, scoring,
and result assembly for both stocks and cryptocurrencies.

Entry point::

    from apps.backend.prediction.analyzer import run_prediction_analysis
    results = run_prediction_analysis(progress_callback=my_cb)

Pipeline per asset:
    1. Download 5 y daily OHLCV (``features.fetch_ohlcv``)
    2. Compute 24 technical features (``features.compute_technical_features``)
    3. Build noise-filtered target (``features.create_target``)
    4. Walk-forward validate → train → predict (``model.StockPredictor``)
    5. Score 0–100 (``scoring.compute_overall_score``)
    6. Assemble JSON-serialisable result dict
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import numpy as np

from apps.backend.prediction.features import (
    FEATURE_COLS,
    compute_technical_features,
    create_target,
    fetch_fundamentals,
    fetch_ohlcv,
)
from apps.backend.prediction.model import StockPredictor, tune_hyperparameters
from apps.backend.prediction.scoring import (
    compute_fundamental_score,
    compute_overall_score,
    compute_technical_score,
)
from apps.backend.utils.config import (
    PREDICTION_CRYPTOS,
    PREDICTION_STOCKS,
    WALLET_CRYPTOS,
    WALLET_STOCKS,
)

logger = logging.getLogger(__name__)

PREDICTION_HORIZON = 5          # trading days ahead
MIN_ROWS_FOR_ML = 120           # minimum valid feature rows to attempt XGBoost
MAX_WORKERS_IO = 4              # threads for parallel I/O


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any, ndigits: int = 2) -> float | None:
    """Convert *val* to a rounded float, or ``None`` if non-finite.

    Used throughout result assembly to sanitise potentially ``NaN`` /
    ``Inf`` values from numpy/pandas before JSON serialisation.
    """
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, ndigits)
    except (TypeError, ValueError):
        return None


def _trend_label(row: dict) -> str:
    """Derive a human-readable trend label from price-vs-SMA distances.

    Returns one of: ``ABOVE_SMA100``, ``ABOVE_SMA50``, ``ABOVE_SMA20``,
    ``BELOW_SMA20`` (from strongest uptrend to weakest).
    """
    pv100 = row.get("price_vs_sma100")
    pv50 = row.get("price_vs_sma50")
    pv20 = row.get("price_vs_sma20")
    if pv100 is not None and pv100 > 0:
        return "ABOVE_SMA100"
    if pv50 is not None and pv50 > 0:
        return "ABOVE_SMA50"
    if pv20 is not None and pv20 > 0:
        return "ABOVE_SMA20"
    return "BELOW_SMA20"


# ---------------------------------------------------------------------------
# Single-stock analysis
# ---------------------------------------------------------------------------

def _analyze_stock(
    symbol: str,
    fundamentals: dict,
    *,
    model_params: dict | None = None,
) -> dict | None:
    """Full prediction pipeline for a single stock.

    Fetches OHLCV, engineers features, runs walk-forward validation,
    trains the ensemble, predicts, scores, and returns a result dict
    ready for JSON serialisation.

    Args:
        symbol: Ticker symbol (e.g. ``"AAPL"``).
        fundamentals: Output of ``features.fetch_fundamentals()``.
        model_params: Override XGBoost hyper-parameters (e.g. from Optuna).

    Returns:
        Result dict with ``symbol``, ``prediction``, ``confidence``,
        ``score``, etc. — or ``None`` if data is insufficient.
    """
    ohlcv = fetch_ohlcv(symbol, period="5y")
    if ohlcv is None or len(ohlcv) < MIN_ROWS_FOR_ML:
        logger.warning(
            "Skipping %s – insufficient data (%s rows)",
            symbol, len(ohlcv) if ohlcv is not None else 0,
        )
        return None

    # Feature engineering (purely technical)
    df = compute_technical_features(ohlcv)
    target = create_target(df, horizon=PREDICTION_HORIZON)
    df["target"] = target

    # Drop rows where technical indicators haven't warmed up or target is NaN
    valid = df.dropna(subset=FEATURE_COLS + ["target"]).copy()

    if len(valid) < MIN_ROWS_FOR_ML:
        logger.warning("Skipping %s – too few valid rows (%d)", symbol, len(valid))
        return None

    X = valid[FEATURE_COLS]
    y = valid["target"]

    # Walk-forward validate → then train on full set → predict
    predictor = StockPredictor(params=model_params)
    metrics = predictor.walk_forward_validate(X, y)
    predictor.train(X, y)

    latest_features = df[FEATURE_COLS].iloc[[-1]]
    prediction = predictor.predict(latest_features)

    # Scores
    latest_row = df.iloc[-1].to_dict()
    tech_score = compute_technical_score(latest_row)
    fund_score = compute_fundamental_score(fundamentals)
    overall = compute_overall_score(
        tech_score, fund_score,
        prediction["confidence"], prediction["direction"],
        ml_accuracy=metrics.get("accuracy"),
    )

    current_price = _safe_float(ohlcv["Close"].values.flat[-1])

    return {
        "symbol": symbol,
        "name": fundamentals.get("short_name", symbol),
        "sector": fundamentals.get("sector", "Unknown"),
        "price": current_price,
        "change_1d": _safe_float((latest_row.get("return_1d") or 0) * 100),
        "change_5d": _safe_float((latest_row.get("return_5d") or 0) * 100),
        "change_20d": _safe_float((latest_row.get("return_20d") or 0) * 100),
        "prediction": prediction["direction"],
        "confidence": prediction["confidence"],
        "probability_up": prediction["probability_up"],
        "score": overall,
        "technical_score": tech_score,
        "fundamental_score": fund_score,
        "rsi": _safe_float(latest_row.get("rsi_14"), 1),
        "macd_trend": "BULLISH" if (latest_row.get("macd_hist") or 0) > 0 else "BEARISH",
        "trend": _trend_label(latest_row),
        "pe_ratio": _safe_float(fundamentals.get("pe_ratio"), 1),
        "volume_trend": (
            "ABOVE_AVG" if (latest_row.get("volume_ratio") or 0) > 1.0 else "BELOW_AVG"
        ),
        "model_accuracy": metrics.get("accuracy"),
        "support": _safe_float(latest_row.get("bb_low"), 2),
        "resistance": _safe_float(latest_row.get("bb_high"), 2),
        "high_52w": _safe_float(fundamentals.get("fifty_two_week_high")),
        "low_52w": _safe_float(fundamentals.get("fifty_two_week_low")),
    }


# ---------------------------------------------------------------------------
# Single-crypto analysis (technical-only)
# ---------------------------------------------------------------------------

def _analyze_crypto(
    symbol: str,
    *,
    model_params: dict | None = None,
) -> dict | None:
    """Technical-analysis + ML pipeline for a single cryptocurrency.

    Same as ``_analyze_stock`` but: no fundamental data (score fixed at 50),
    symbol is converted to Yahoo format (e.g. ``BTC`` → ``BTC-USD``),
    and the overall score uses a crypto-specific dynamic ML weight.

    Args:
        symbol: Crypto base symbol (e.g. ``"BTC"``, ``"ETH"``).
        model_params: Override XGBoost hyper-parameters.

    Returns:
        Result dict or ``None``.
    """
    yf_symbol = f"{symbol}-USD"
    ohlcv = fetch_ohlcv(yf_symbol, period="5y")
    if ohlcv is None or len(ohlcv) < 60:
        logger.warning("Skipping crypto %s – insufficient data", symbol)
        return None

    df = compute_technical_features(ohlcv)
    latest_row = df.iloc[-1].to_dict()
    tech_score = compute_technical_score(latest_row)

    # ML on technical features
    prediction: dict = {"direction": "NEUTRAL", "confidence": 0.50, "probability_up": 0.50}
    model_accuracy: float | None = None

    target = create_target(df, horizon=PREDICTION_HORIZON)
    df["target"] = target
    valid = df.dropna(subset=FEATURE_COLS + ["target"])
    if len(valid) >= MIN_ROWS_FOR_ML:
        X = valid[FEATURE_COLS]
        y = valid["target"]
        predictor = StockPredictor(params=model_params)
        metrics = predictor.walk_forward_validate(X, y)
        predictor.train(X, y)
        prediction = predictor.predict(df[FEATURE_COLS].iloc[[-1]])
        model_accuracy = metrics.get("accuracy")

    # Dynamic ML weight based on accuracy (no fundamentals for crypto)
    if model_accuracy is not None and model_accuracy > 0.52:
        ml_w = min(0.50, 0.15 + (model_accuracy - 0.50) * 3.5)
    else:
        ml_w = 0.15
    tech_w = 1.0 - ml_w

    if prediction["direction"] == "UP":
        ml_score = 50 + (prediction["confidence"] - 0.5) * 100
    else:
        ml_score = 50 - (prediction["confidence"] - 0.5) * 100
    overall = int(tech_w * tech_score + ml_w * max(0, min(100, ml_score)))

    current_price = _safe_float(ohlcv["Close"].values.flat[-1])

    return {
        "symbol": symbol,
        "price": current_price,
        "change_1d": _safe_float((latest_row.get("return_1d") or 0) * 100),
        "change_5d": _safe_float((latest_row.get("return_5d") or 0) * 100),
        "change_20d": _safe_float((latest_row.get("return_20d") or 0) * 100),
        "prediction": prediction["direction"],
        "confidence": prediction["confidence"],
        "score": overall,
        "rsi": _safe_float(latest_row.get("rsi_14"), 1),
        "macd_trend": "BULLISH" if (latest_row.get("macd_hist") or 0) > 0 else "BEARISH",
        "trend": _trend_label(latest_row),
        "support": _safe_float(latest_row.get("bb_low"), 2),
        "resistance": _safe_float(latest_row.get("bb_high"), 2),
        "model_accuracy": model_accuracy,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_prediction_analysis(
    *,
    progress_callback: callable | None = None,
    enable_tuning: bool = False,
) -> dict[str, Any]:
    """Run the full prediction analysis and return a JSON-serialisable dict.

    Parameters
    ----------
    progress_callback:
        Optional ``(step: int, total: int, message: str) -> None`` called
        to report progress.
    enable_tuning:
        If *True*, run Optuna hyperparameter tuning on a representative
        stock (AAPL) and reuse the best params for all assets.

    Returns
    -------
    dict with keys: ``timestamp``, ``stocks``, ``cryptos``, ``portfolio``,
    ``model_info``.
    """

    total_steps = 5 if enable_tuning else 4

    def _progress(step: int, msg: str) -> None:
        if progress_callback:
            progress_callback(step, total_steps, msg)

    _progress(1, "Fetching fundamental data")

    # ---- 1. Fetch fundamentals in parallel --------------------------------
    stock_symbols = list(set(PREDICTION_STOCKS + WALLET_STOCKS))
    fundamentals: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_IO) as pool:
        futures = {pool.submit(fetch_fundamentals, sym): sym for sym in stock_symbols}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                fundamentals[sym] = future.result()
            except Exception as exc:
                logger.error("Fundamentals error for %s: %s", sym, exc)
                fundamentals[sym] = {"sector": "Unknown", "short_name": sym}

    # ---- 1b. Optional Optuna hyper-parameter tuning -----------------------
    tuned_params: dict | None = None
    if enable_tuning:
        _progress(2, "Tuning hyperparameters (Optuna)")
        try:
            # Tune on a liquid, well-behaved stock
            ref_ohlcv = fetch_ohlcv("AAPL", period="5y")
            if ref_ohlcv is not None and len(ref_ohlcv) > 500:
                ref_df = compute_technical_features(ref_ohlcv)
                ref_target = create_target(ref_df, horizon=PREDICTION_HORIZON)
                ref_df["target"] = ref_target
                ref_valid = ref_df.dropna(subset=FEATURE_COLS + ["target"])
                if len(ref_valid) >= 400:
                    tuned_params = tune_hyperparameters(
                        ref_valid[FEATURE_COLS],
                        ref_valid["target"],
                        n_trials=40,
                    )
                    logger.info("Optuna tuning complete – reusing params for all assets")
        except Exception as exc:
            logger.error("Optuna tuning failed: %s", exc)

    step_offset = 1 if enable_tuning else 0

    _progress(2 + step_offset, "Analyzing stocks")

    # ---- 2. Analyze stocks ------------------------------------------------
    stock_results: list[dict] = []
    for sym in stock_symbols:
        try:
            result = _analyze_stock(sym, fundamentals.get(sym, {}), model_params=tuned_params)
            if result:
                stock_results.append(result)
        except Exception as exc:
            logger.error("Stock analysis failed for %s: %s", sym, exc)

    stock_results.sort(key=lambda r: r["score"], reverse=True)

    _progress(3 + step_offset, "Analyzing cryptocurrencies")

    # ---- 3. Analyze cryptos -----------------------------------------------
    crypto_symbols = list(set(PREDICTION_CRYPTOS + WALLET_CRYPTOS))
    crypto_results: list[dict] = []
    for sym in crypto_symbols:
        try:
            result = _analyze_crypto(sym, model_params=tuned_params)
            if result:
                crypto_results.append(result)
        except Exception as exc:
            logger.error("Crypto analysis failed for %s: %s", sym, exc)

    crypto_results.sort(key=lambda r: r["score"], reverse=True)

    _progress(4 + step_offset, "Compiling results")

    # ---- 4. Separate portfolio items from main list -----------------------
    wallet_stock_set = set(WALLET_STOCKS)
    wallet_crypto_set = set(WALLET_CRYPTOS)

    portfolio_stocks = [r for r in stock_results if r["symbol"] in wallet_stock_set]
    portfolio_cryptos = [r for r in crypto_results if r["symbol"] in wallet_crypto_set]

    # Model-info summary
    stock_accuracies = [r["model_accuracy"] for r in stock_results if r.get("model_accuracy")]
    crypto_accuracies = [r["model_accuracy"] for r in crypto_results if r.get("model_accuracy")]
    all_accuracies = stock_accuracies + crypto_accuracies

    result = {
        "timestamp": datetime.now().isoformat(),
        "stocks": stock_results,
        "cryptos": crypto_results,
        "portfolio": {
            "stocks": portfolio_stocks,
            "cryptos": portfolio_cryptos,
        },
        "model_info": {
            "avg_accuracy": round(np.mean(all_accuracies), 4) if all_accuracies else None,
            "stocks_analyzed": len(stock_results),
            "cryptos_analyzed": len(crypto_results),
            "prediction_horizon": f"{PREDICTION_HORIZON} trading days",
            "method": "XGBoost + LR Ensemble + Multi-Factor Scoring",
            "features_used": len(FEATURE_COLS),
            "tuning_enabled": enable_tuning,
        },
    }

    logger.info(
        "Prediction analysis complete: %d stocks, %d cryptos (avg accuracy %.3f)",
        len(stock_results),
        len(crypto_results),
        result["model_info"]["avg_accuracy"] or 0,
    )

    return result
