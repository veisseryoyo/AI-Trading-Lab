from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.data_providers.finnhub_client import finnhub_client
from backend.indicators.technical_indicators import compute_indicators
from backend.strategies.strategy_manager import strategy_manager
from backend.risk_management.risk_manager import RiskManager
from backend.utils.logger import logger

class HistoricalBacktester:
    """
    Historical Backtester:
    Simulates a paper trading strategy over historical daily candles.
    """
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        
    def run_backtest(
        self, 
        ticker: str, 
        start_date: datetime, 
        end_date: datetime,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.15
    ) -> Dict[str, Any]:
        """Runs a backtest simulation on a single stock and returns performance metrics."""
        logger.info(f"Starting historical backtest for {ticker} from {start_date.date()} to {end_date.date()}")
        
        # 1. Fetch historical candles
        candles = finnhub_client.get_historical_data(ticker, start_date, end_date)
        if not candles or len(candles) < 200:
            return {
                "success": False,
                "message": f"Insufficient data for backtest. Found {len(candles) if candles else 0} candles, need at least 200."
            }
            
        # Compute indicators on entire dataset first (for efficiency)
        df = compute_indicators(candles)
        
        # Simulation variables
        cash = self.initial_capital
        quantity = 0.0
        avg_buy_price = 0.0
        
        trades = []
        portfolio_history = []
        timestamps = []
        
        # Instantiate localized RiskManager for backtest run
        backtest_risk = RiskManager(
            max_allocation_pct=0.10,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct
        )
        
        # 2. Iterate day by day, starting at index 200 (so indicator values are calculated)
        for i in range(200, len(df)):
            row = df.iloc[i]
            current_time = row["timestamp"]
            close_price = row["close"]
            
            # Slice historical data up to current point to simulate realistic backtest environment
            df_slice = df.iloc[:i+1]
            
            # Check Risk Limits first (Stop-Loss and Take-Profit)
            if quantity > 0:
                should_exit, exit_reason = backtest_risk.check_position_limits(
                    ticker=ticker,
                    current_price=close_price,
                    average_buy_price=avg_buy_price
                )
                if should_exit:
                    # Sell full position
                    proceeds = quantity * close_price
                    realized_pnl = proceeds - (quantity * avg_buy_price)
                    cash += proceeds
                    
                    trades.append({
                        "timestamp": current_time,
                        "action": "SELL",
                        "price": close_price,
                        "quantity": quantity,
                        "total_value": proceeds,
                        "pnl": realized_pnl,
                        "pnl_pct": (close_price - avg_buy_price) / avg_buy_price,
                        "reason": exit_reason
                    })
                    quantity = 0.0
                    avg_buy_price = 0.0
            
            # Evaluate strategy signals
            analysis = strategy_manager.analyze_ticker(df_slice)
            signal = analysis["signal"]
            explanation = analysis["explanation"]
            
            portfolio_val = cash + (quantity * close_price)
            
            if signal == "BUY" and quantity == 0:
                # Calculate allocation (Max 10% of total portfolio value)
                target_allocation = portfolio_val * 0.10
                buy_cost = min(cash, target_allocation)
                
                if buy_cost > 0:
                    quantity = buy_cost / close_price
                    avg_buy_price = close_price
                    cash -= buy_cost
                    
                    trades.append({
                        "timestamp": current_time,
                        "action": "BUY",
                        "price": close_price,
                        "quantity": quantity,
                        "total_value": buy_cost,
                        "pnl": 0.0,
                        "pnl_pct": 0.0,
                        "reason": f"Strategy Signal: {explanation}"
                    })
                    
            elif signal == "SELL" and quantity > 0:
                # Sell full position
                proceeds = quantity * close_price
                realized_pnl = proceeds - (quantity * avg_buy_price)
                cash += proceeds
                
                trades.append({
                    "timestamp": current_time,
                    "action": "SELL",
                    "price": close_price,
                    "quantity": quantity,
                    "total_value": proceeds,
                    "pnl": realized_pnl,
                    "pnl_pct": (close_price - avg_buy_price) / avg_buy_price,
                    "reason": f"Strategy Signal: {explanation}"
                })
                quantity = 0.0
                avg_buy_price = 0.0
                
            # Log portfolio value for that day
            current_portfolio_value = cash + (quantity * close_price)
            portfolio_history.append(current_portfolio_value)
            timestamps.append(current_time)
            
        # 3. Calculate Performance Metrics
        final_value = cash + (quantity * df.iloc[-1]["close"])
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # Calculate maximum drawdown
        max_drawdown = backtest_risk.calculate_drawdown(portfolio_history)
        
        # Parse trades
        sell_trades = [t for t in trades if t["action"] == "SELL"]
        win_trades = [t for t in sell_trades if t["pnl"] > 0]
        win_rate = len(win_trades) / len(sell_trades) if sell_trades else 0.0
        avg_trade_pnl = np.mean([t["pnl"] for t in sell_trades]) if sell_trades else 0.0
        
        # Annualized return calculation
        days_count = (end_date - start_date).days
        years = max(0.1, days_count / 365.25)
        annualized_return = (final_value / self.initial_capital) ** (1 / years) - 1
        
        # Sharpe ratio calculation
        portfolio_series = pd.Series(portfolio_history)
        daily_returns = portfolio_series.pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            # Assuming risk-free rate = 0
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
            
        logger.info(f"Backtest complete for {ticker}. Final Value: ${final_value:,.2f}, Return: {total_return*100:+.2f}%, Max Drawdown: {max_drawdown*100:.2f}%")
        
        return {
            "success": True,
            "ticker": ticker,
            "initial_capital": self.initial_capital,
            "final_value": final_value,
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "num_trades": len(trades),
            "num_completed_trades": len(sell_trades),
            "average_trade_pnl": avg_trade_pnl,
            "sharpe_ratio": sharpe_ratio,
            "trades": trades,
            "portfolio_history": portfolio_history,
            "timestamps": timestamps
        }
