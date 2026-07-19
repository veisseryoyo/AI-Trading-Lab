from typing import Dict, Any
import pandas as pd
from backend.utils.logger import logger

class SmartMomentumStrategy:
    """
    Smart Momentum Strategy:
    Uses SMA 20, 50, 200, RSI, MACD, and Volume to identify and trade momentum trends.
    """
    
    def __init__(self, rsi_buy_threshold: float = 45.0, rsi_sell_threshold: float = 70.0):
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyzes stock data and returns a dictionary with signal, confidence, and explanation.
        Requires a DataFrame containing computed indicators.
        """
        if df.empty or len(df) < 200:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "explanation": f"Insufficient historical data to compute 200-day indicators. Available: {len(df)} days, need: 200 days."
            }
            
        # Get the latest row of data
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        close = latest["close"]
        sma_20 = latest["sma_20"]
        sma_50 = latest["sma_50"]
        sma_200 = latest["sma_200"]
        rsi = latest["rsi"]
        macd_line = latest["macd_line"]
        macd_signal = latest["macd_signal"]
        volume = latest["volume"]
        volume_sma_20 = latest["volume_sma_20"]
        
        # Check NaN values
        if any(pd.isna([sma_20, sma_50, sma_200, rsi, macd_line, macd_signal, volume_sma_20])):
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "explanation": "Calculated indicators contain NaN values. Waiting for more data."
            }

        # BUY logic check flags
        long_term_trend_bullish = close > sma_200 and sma_50 > sma_200
        momentum_bullish = sma_20 > sma_50 and macd_line > macd_signal and rsi > self.rsi_buy_threshold and rsi < 70
        volume_confirmed = volume > volume_sma_20
        
        # SELL logic check flags
        trend_weakening = close < sma_50
        momentum_bearish = macd_line < macd_signal or rsi > self.rsi_sell_threshold or (prev["rsi"] > self.rsi_sell_threshold and rsi < prev["rsi"])
        
        # Determine signals
        if long_term_trend_bullish and momentum_bullish and volume_confirmed:
            # Calculate confidence score based on indicator strengths
            # 1. MACD histogram height relative to signal
            # 2. RSI level (ideal range 50-65)
            # 3. Volume surge intensity
            rsi_factor = 30 - abs(rsi - 55)  # Max 30 points if RSI is 55
            vol_factor = min(35, (volume / volume_sma_20) * 15)  # Max 35 points
            trend_factor = 35 if close > sma_20 else 20  # Max 35 points
            confidence = round(max(50.0, min(100.0, rsi_factor + vol_factor + trend_factor)), 1)
            
            explanation = (
                f"BUY: Price ({close:.2f}) is in a long-term uptrend above SMA-200 ({sma_200:.2f}). "
                f"Short-term momentum is rising with SMA-20 ({sma_20:.2f}) > SMA-50 ({sma_50:.2f}) and MACD crossover. "
                f"Volume of {volume:,} exceeds SMA-20 volume {int(volume_sma_20):,}, confirming buying pressure. RSI is at {rsi:.1f}."
            )
            return {
                "signal": "BUY",
                "confidence": confidence,
                "explanation": explanation
            }
            
        elif trend_weakening or momentum_bearish:
            # Determine sell confidence
            confidence = 50.0
            reasons = []
            if trend_weakening:
                reasons.append(f"Price ({close:.2f}) dropped below SMA-50 ({sma_50:.2f})")
                confidence += 25.0
            if macd_line < macd_signal:
                reasons.append("MACD bearish crossover occurred")
                confidence += 15.0
            if rsi > self.rsi_sell_threshold:
                reasons.append(f"RSI is overbought at {rsi:.1f}")
                confidence += 10.0
                
            explanation = f"SELL: " + ", ".join(reasons) + "."
            return {
                "signal": "SELL",
                "confidence": min(100.0, confidence),
                "explanation": explanation
            }
            
        else:
            # Default HOLD
            explanation = (
                f"HOLD: Indicators are neutral. Price ({close:.2f}) is stable relative to SMAs. "
                f"RSI is at {rsi:.1f} (Neutral zone). MACD Histogram is at {latest['macd_hist']:.4f}."
            )
            return {
                "signal": "HOLD",
                "confidence": 100.0,
                "explanation": explanation
            }
