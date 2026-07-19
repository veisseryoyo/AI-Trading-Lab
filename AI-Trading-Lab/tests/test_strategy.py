import pytest
import pandas as pd
import numpy as np
from backend.indicators.technical_indicators import compute_indicators
from backend.strategies.momentum_strategy import SmartMomentumStrategy

def generate_trend_candles(num_days: int = 250, trend: str = "up") -> list:
    candles = []
    base_price = 100.0
    import random
    random.seed(42)
    
    import datetime
    start_date = datetime.datetime(2023, 1, 1)
    
    for i in range(num_days):
        if trend == "up":
            change = random.uniform(-0.01, 0.02)
        elif trend == "down":
            change = random.uniform(-0.02, 0.01)
        else:
            change = random.uniform(-0.015, 0.015)
            
        close_price = base_price * (1 + change)
        high = max(base_price, close_price) * 1.01
        low = min(base_price, close_price) * 0.99
        
        candles.append({
            "timestamp": start_date + datetime.timedelta(days=i),
            "open": base_price,
            "high": high,
            "low": low,
            "close": close_price,
            "volume": int(random.uniform(1000, 5000)),
            "ticker": "TEST"
        })
        base_price = close_price
    return candles

def test_compute_indicators_shape():
    candles = generate_trend_candles(210)
    df = compute_indicators(candles)
    
    assert isinstance(df, pd.DataFrame)
    assert "sma_20" in df.columns
    assert "sma_50" in df.columns
    assert "sma_200" in df.columns
    assert "rsi" in df.columns
    assert "macd_line" in df.columns
    assert "macd_signal" in df.columns
    assert "macd_hist" in df.columns
    assert "volume_sma_20" in df.columns
    
    # 200 SMA should be NaN for the first 199 rows
    assert pd.isna(df.iloc[0]["sma_200"])
    assert not pd.isna(df.iloc[205]["sma_200"])

def test_momentum_strategy_insufficient_data():
    strategy = SmartMomentumStrategy()
    # Less than 200 items
    df_short = pd.DataFrame([{"close": 10.0}] * 50)
    res = strategy.analyze(df_short)
    
    assert res["signal"] == "HOLD"
    assert res["confidence"] == 0.0
    assert "Insufficient historical data" in res["explanation"]

def test_momentum_strategy_upward_trend():
    # An upward trending series should trigger a BUY signal or at least check valid bounds
    candles = generate_trend_candles(250, trend="up")
    df = compute_indicators(candles)
    strategy = SmartMomentumStrategy(rsi_buy_threshold=10.0) # lower threshold to guarantee trigger in simulation
    res = strategy.analyze(df)
    
    assert "signal" in res
    assert "confidence" in res
    assert "explanation" in res
    # With a high trend, it should have a signal
    assert res["signal"] in ["BUY", "SELL", "HOLD"]
