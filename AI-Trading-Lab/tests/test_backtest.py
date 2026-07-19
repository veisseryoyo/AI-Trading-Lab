import pytest
from datetime import datetime, timedelta
from backend.backtesting.backtester import HistoricalBacktester

def test_backtester_run():
    backtester = HistoricalBacktester(initial_capital=10000.0)
    
    # Run backtest for Apple over a short timeframe
    # Since we are using the Mock generator fallback in test mode, this should complete instantly
    end_date = datetime.now()
    start_date = end_date - timedelta(days=220) # Need >200 candles
    
    res = backtester.run_backtest(
        ticker="AAPL",
        start_date=start_date,
        end_date=end_date,
        stop_loss_pct=0.05,
        take_profit_pct=0.15
    )
    
    # Verify shape of output
    assert "success" in res
    if res["success"]:
        assert "ticker" in res
        assert res["ticker"] == "AAPL"
        assert "initial_capital" in res
        assert res["initial_capital"] == 10000.0
        assert "final_value" in res
        assert "total_return" in res
        assert "max_drawdown" in res
        assert "win_rate" in res
        assert "trades" in res
        assert "portfolio_history" in res
        assert "timestamps" in res
        assert len(res["portfolio_history"]) == len(res["timestamps"])
