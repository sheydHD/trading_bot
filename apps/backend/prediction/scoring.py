"""Multi-factor scoring system.

Three independent scores (0 – 100) are combined into an overall score:

* **Technical** – based on RSI, MACD, moving-average alignment, Bollinger
  position, ADX, and volume.
* **Fundamental** – based on P/E, PEG, ROE, revenue growth, profit margins,
  and debt levels.
* **ML** – the XGBoost direction-prediction confidence converted to a 0-100
  scale.

The overall score is a *weighted average*:
  35 % technical  +  30 % fundamental  +  35 % ML.
"""

from __future__ import annotations

from typing import Any


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(max(lo, min(hi, value)))


# ---------------------------------------------------------------------------
# Technical score
# ---------------------------------------------------------------------------

def compute_technical_score(indicators: dict[str, Any]) -> int:
    """Compute a 0–100 technical score from the latest indicator row.

    Starts at 50 (neutral) and adjusts based on RSI zones, MACD sign,
    price-vs-SMA alignment, ADX, Bollinger band position, and volume.

    Args:
        indicators: Dict of indicator values (e.g. ``rsi_14``, ``macd_hist``,
            ``price_vs_sma20``, ``adx``, ``bb_pct``, ``volume_ratio``).

    Returns:
        Integer score clamped to [0, 100].
    """
    score = 50.0

    # RSI (14)
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            score += 12      # oversold → bullish
        elif rsi < 40:
            score += 6
        elif rsi > 70:
            score -= 12      # overbought → bearish
        elif rsi > 60:
            score -= 6

    # MACD histogram
    macd_hist = indicators.get("macd_hist")
    if macd_hist is not None:
        score += 10 if macd_hist > 0 else -10

    # Price vs moving averages
    for col, weight in [("price_vs_sma20", 4), ("price_vs_sma50", 5), ("price_vs_sma100", 6)]:
        val = indicators.get(col)
        if val is not None:
            score += weight if val > 0 else -weight

    # ADX – strong trend confirmation
    adx = indicators.get("adx")
    if adx is not None and adx > 25:
        score += 5

    # Bollinger band position
    bb_pct = indicators.get("bb_pct")
    if bb_pct is not None:
        if bb_pct < 0.2:
            score += 6       # near lower band → bullish
        elif bb_pct > 0.8:
            score -= 6       # near upper band → bearish

    # Volume surge
    vol_ratio = indicators.get("volume_ratio")
    if vol_ratio is not None and vol_ratio > 1.5:
        score += 4

    return _clamp(score)


# ---------------------------------------------------------------------------
# Fundamental score
# ---------------------------------------------------------------------------

def compute_fundamental_score(fundamentals: dict[str, Any]) -> int:
    """Compute a 0–100 fundamental score from financial metrics.

    Evaluates: P/E ratio, PEG, ROE, revenue growth, profit margins,
    and debt-to-equity.  Starts at 50 (neutral).

    Args:
        fundamentals: Dict from ``features.fetch_fundamentals()``.

    Returns:
        Integer score clamped to [0, 100].
    """
    score = 50.0

    # P/E ratio
    pe = fundamentals.get("pe_ratio")
    if pe is not None:
        if 0 < pe < 15:
            score += 10
        elif 15 <= pe < 25:
            score += 5
        elif pe > 50:
            score -= 10
        elif pe < 0:
            score -= 15       # negative earnings

    # PEG ratio
    peg = fundamentals.get("peg_ratio")
    if peg is not None:
        if 0 < peg < 1:
            score += 10
        elif 1 <= peg < 1.5:
            score += 5
        elif peg > 3:
            score -= 10

    # Return on equity
    roe = fundamentals.get("return_on_equity")
    if roe is not None:
        if roe > 0.20:
            score += 10
        elif roe > 0.10:
            score += 5
        elif roe < 0:
            score -= 10

    # Revenue growth
    rg = fundamentals.get("revenue_growth")
    if rg is not None:
        if rg > 0.20:
            score += 10
        elif rg > 0.05:
            score += 5
        elif rg < 0:
            score -= 10

    # Profit margin
    pm = fundamentals.get("profit_margin")
    if pm is not None:
        if pm > 0.20:
            score += 8
        elif pm > 0.10:
            score += 4
        elif pm < 0:
            score -= 10

    # Debt to equity
    de = fundamentals.get("debt_to_equity")
    if de is not None:
        if de < 50:
            score += 5
        elif de > 200:
            score -= 8

    return _clamp(score)


# ---------------------------------------------------------------------------
# Overall composite score
# ---------------------------------------------------------------------------

def compute_overall_score(
    technical: int,
    fundamental: int,
    ml_confidence: float,
    ml_direction: str,
    ml_accuracy: float | None = None,
) -> int:
    """Weighted blend with **dynamic ML weight** based on accuracy.

    When the model has no edge (~50 %), ML gets minimal weight and the
    score is driven by technical + fundamental analysis.  As accuracy
    improves, ML earns more influence (up to 40 %).
    """
    # Convert ML output to a 0-100 score
    if ml_direction == "UP":
        ml_score = 50.0 + (ml_confidence - 0.5) * 100.0
    else:
        ml_score = 50.0 - (ml_confidence - 0.5) * 100.0
    ml_score = max(0.0, min(100.0, ml_score))

    # Dynamic ML weight: rises with accuracy
    if ml_accuracy is not None and ml_accuracy > 0.52:
        ml_w = min(0.40, 0.10 + (ml_accuracy - 0.50) * 3.0)
    else:
        ml_w = 0.10  # minimal when model has no edge

    tech_w = (1.0 - ml_w) * 0.55
    fund_w = 1.0 - ml_w - tech_w

    overall = tech_w * technical + fund_w * fundamental + ml_w * ml_score
    return _clamp(overall)
