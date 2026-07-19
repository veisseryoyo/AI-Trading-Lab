import pandas as pd
import numpy as np
from typing import Union, List, Dict, Any

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return series.rolling(window=period).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()

    # Exponential moving average for gains/losses
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    # Avoid division by zero
    rs = np.where(avg_loss == 0, 100, avg_gain / avg_loss)
    rsi = 100 - (100 / (1 + rs))
    return pd.Series(rsi, index=series.index)

def calculate_macd(series: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD Line, Signal Line, and MACD Histogram."""
    ema_fast = series.ewm(span=fast_period, adjust=False).mean()
    ema_slow = series.ewm(span=slow_period, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    macd_hist = macd_line - signal_line
    
    return macd_line, signal_line, macd_hist

def compute_indicators(candles: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Computes all required technical indicators from a list of daily candles.
    Returns a pandas DataFrame with timestamps and calculated columns.
    """
    if not candles:
        return pd.DataFrame()
        
    # Create DataFrame sorted by timestamp
    df = pd.DataFrame(candles)
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # Calculate SMAs
    df["sma_20"] = calculate_sma(df["close"], 20)
    df["sma_50"] = calculate_sma(df["close"], 50)
    df["sma_200"] = calculate_sma(df["close"], 200)
    
    # Calculate RSI (14-day)
    df["rsi"] = calculate_rsi(df["close"], 14)
    
    # Calculate MACD
    macd_l, signal_l, hist_l = calculate_macd(df["close"], 12, 26, 9)
    df["macd_line"] = macd_l
    df["macd_signal"] = signal_l
    df["macd_hist"] = hist_l
    
    # Volume analysis (e.g. SMA 20 of volume)
    df["volume_sma_20"] = calculate_sma(df["volume"].astype(float), 20)
    
    return df
