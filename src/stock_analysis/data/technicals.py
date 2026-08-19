from __future__ import annotations

import math

import pandas as pd

from stock_analysis.models.market_data import PriceBar, TechnicalSeriesPoint, TechnicalSnapshot


def compute_technicals(ticker: str, bars: list[PriceBar]) -> TechnicalSnapshot:
    """Compute technical indicators from OHLCV bars. Pure pandas, no LLM."""
    if not bars:
        raise ValueError(f"No price bars for {ticker}")

    df = pd.DataFrame([b.model_dump() for b in bars])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    def _value(s: pd.Series, index: int, min_periods: int) -> float | None:
        if index + 1 < min_periods:
            return None
        val = s.iloc[index]
        if val is None or pd.isna(val) or not math.isfinite(float(val)):
            return None
        return round(float(val), 4)

    def _last(s: pd.Series, min_periods: int) -> float | None:
        return _value(s, len(s) - 1, min_periods)

    # --- Moving averages ---
    sma_20_s = close.rolling(20).mean()
    sma_50_s = close.rolling(50).mean()
    sma_200_s = close.rolling(200).mean()
    ema_20_s = close.ewm(span=20, adjust=False).mean()

    # --- RSI 14 ---
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi_14_s = 100 - (100 / (1 + gain / loss))

    # --- MACD (12, 26, 9) ---
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    macd_signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_histogram_s = macd_line - macd_signal_line

    # --- Bollinger Bands (20, 2σ) ---
    bb_mid = sma_20_s
    bb_std = close.rolling(20).std()
    bb_upper_s = bb_mid + 2 * bb_std
    bb_lower_s = bb_mid - 2 * bb_std
    bb_pct_s = (close - bb_lower_s) / (bb_upper_s - bb_lower_s)

    # --- ATR 14 ---
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_14_s = tr.rolling(14).mean()

    # --- Volume ---
    last_vol = int(volume.iloc[-1])
    vol_sma_20_s = volume.astype(float).rolling(20).mean()
    vol_ratio_s = volume / vol_sma_20_s

    # The chart consumes this series directly. Keep it beside the snapshot so
    # local JSON, FastAPI, and cloud JSONB all share the same Python-owned
    # calculations instead of reimplementing indicators in TypeScript.
    series = [
        TechnicalSeriesPoint(
            date=timestamp.date(),
            sma_20=_value(sma_20_s, i, 20),
            sma_50=_value(sma_50_s, i, 50),
            sma_200=_value(sma_200_s, i, 200),
            ema_20=_value(ema_20_s, i, 20),
            rsi_14=_value(rsi_14_s, i, 15),
            macd_line=_value(macd_line, i, 26),
            macd_signal=_value(macd_signal_line, i, 26),
            macd_histogram=_value(macd_histogram_s, i, 26),
            bb_upper=_value(bb_upper_s, i, 20),
            bb_middle=_value(bb_mid, i, 20),
            bb_lower=_value(bb_lower_s, i, 20),
            bb_pct=_value(bb_pct_s, i, 20),
            atr_14=_value(atr_14_s, i, 14),
            volume_sma_20=_value(vol_sma_20_s, i, 20),
            volume_ratio=_value(vol_ratio_s, i, 20),
        )
        for i, timestamp in enumerate(df["date"])
    ]

    sma_20 = _last(sma_20_s, 20)
    sma_50 = _last(sma_50_s, 50)
    sma_200 = _last(sma_200_s, 200)
    ema_20 = _last(ema_20_s, 20)
    rsi_14 = _last(rsi_14_s, 15)
    macd_line_val = _last(macd_line, 26)
    macd_signal_val = _last(macd_signal_line, 26)
    macd_hist_val = _last(macd_histogram_s, 26)
    bb_upper = _last(bb_upper_s, 20)
    bb_middle = _last(bb_mid, 20)
    bb_lower = _last(bb_lower_s, 20)
    last_close = round(float(close.iloc[-1]), 4)
    bb_pct = _last(bb_pct_s, 20)
    atr_14 = _last(atr_14_s, 14)
    vol_sma_20 = _last(vol_sma_20_s, 20)
    vol_ratio = _last(vol_ratio_s, 20)

    # --- 52-week high/low ---
    last_date = df["date"].iloc[-1].date()
    yr_df = df[df["date"] >= df["date"].iloc[-1] - pd.Timedelta(days=365)]
    high_52w = round(float(yr_df["high"].max()), 4) if not yr_df.empty else None
    low_52w = round(float(yr_df["low"].min()), 4) if not yr_df.empty else None
    pct_from_high = round((last_close - high_52w) / high_52w, 4) if high_52w else None
    pct_from_low = round((last_close - low_52w) / low_52w, 4) if low_52w else None

    return TechnicalSnapshot(
        ticker=ticker,
        as_of_date=last_date,
        close=last_close,
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
        ema_20=ema_20,
        rsi_14=rsi_14,
        macd_line=macd_line_val,
        macd_signal=macd_signal_val,
        macd_histogram=macd_hist_val,
        bb_upper=bb_upper,
        bb_middle=bb_middle,
        bb_lower=bb_lower,
        bb_pct=bb_pct,
        atr_14=atr_14,
        volume=last_vol,
        volume_sma_20=vol_sma_20,
        volume_ratio=vol_ratio,
        high_52w=high_52w,
        low_52w=low_52w,
        pct_from_52w_high=pct_from_high,
        pct_from_52w_low=pct_from_low,
        above_sma_20=last_close > sma_20 if sma_20 else None,
        above_sma_50=last_close > sma_50 if sma_50 else None,
        above_sma_200=last_close > sma_200 if sma_200 else None,
        series=series,
    )
