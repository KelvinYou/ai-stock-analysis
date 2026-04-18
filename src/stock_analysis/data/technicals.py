from __future__ import annotations

import pandas as pd

from stock_analysis.models.market_data import PriceBar, TechnicalSnapshot


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

    def _last(s: pd.Series, min_periods: int) -> float | None:
        val = s.iloc[-1] if len(s) >= min_periods else None
        if val is None or pd.isna(val):
            return None
        return round(float(val), 4)

    # --- Moving averages ---
    sma_20 = _last(close.rolling(20).mean(), 20)
    sma_50 = _last(close.rolling(50).mean(), 50)
    sma_200 = _last(close.rolling(200).mean(), 200)
    ema_20 = _last(close.ewm(span=20, adjust=False).mean(), 20)

    # --- RSI 14 ---
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi_14 = _last(100 - (100 / (1 + gain / loss)), 15)

    # --- MACD (12, 26, 9) ---
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    macd_signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_line_val = _last(macd_line, 26)
    macd_signal_val = _last(macd_signal_line, 26)
    macd_hist_val = _last(macd_line - macd_signal_line, 26)

    # --- Bollinger Bands (20, 2σ) ---
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper_s = bb_mid + 2 * bb_std
    bb_lower_s = bb_mid - 2 * bb_std
    bb_upper = _last(bb_upper_s, 20)
    bb_middle = _last(bb_mid, 20)
    bb_lower = _last(bb_lower_s, 20)
    last_close = round(float(close.iloc[-1]), 4)
    bb_pct = None
    if bb_upper and bb_lower and bb_upper != bb_lower:
        bb_pct = round((last_close - bb_lower) / (bb_upper - bb_lower), 4)

    # --- ATR 14 ---
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_14 = _last(tr.rolling(14).mean(), 14)

    # --- Volume ---
    last_vol = int(volume.iloc[-1])
    vol_sma_20 = _last(volume.astype(float).rolling(20).mean(), 20)
    vol_ratio = round(last_vol / vol_sma_20, 4) if vol_sma_20 else None

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
    )
