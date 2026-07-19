import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import config
from backend.database import init_db, SessionLocal, get_db
from backend.models import Portfolio, Position, Trade, StrategyLog, MarketData
from backend.trading_engine.engine import TradingEngine
from backend.trading_engine.portfolio import PortfolioManager
from backend.backtesting.backtester import HistoricalBacktester
from backend.ai_analysis import ai_analysis_module
from backend.data_providers.finnhub_client import finnhub_client
from backend.utils.logger import logger

# Global flag to control the background scheduler
scheduler_running = True

def run_automated_scheduler():
    """Background worker thread that runs the market scan at a fixed interval."""
    logger.info("Automated Scheduler thread started.")
    # Wait a few seconds for server startup
    time.sleep(5)
    
    while scheduler_running:
        try:
            logger.info("Scheduler triggering automated market scan...")
            db = SessionLocal()
            try:
                results = TradingEngine.run_market_scan(db, config.DEFAULT_TICKERS)
                logger.info(f"Automated market scan complete. Results: {list(results.keys())}")
            except Exception as e:
                logger.error(f"Error during automated market scan: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Database session error in scheduler: {e}")
            
        # Sleep for the configured scan frequency
        time.sleep(config.SCAN_FREQUENCY_SECONDS)
        
    logger.info("Automated Scheduler thread stopped.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database schema and spawn scheduler
    init_db()
    global scheduler_running
    scheduler_running = True
    thread = threading.Thread(target=run_automated_scheduler, daemon=True)
    thread.start()
    yield
    # Shutdown: Stop the background thread
    scheduler_running = False
    logger.info("Lifespan shutdown: stopping scheduler thread.")

app = FastAPI(
    title="AI Trading Lab API",
    description="Backend API for algorithmic stock market analysis and paper trading platform.",
    version="1.0.0",
    lifespan=lifespan
)

# API Endpoint models
class BacktestRequest(BaseModel):
    ticker: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    stop_loss: float = 0.05
    take_profit: float = 0.15

class ManualScanRequest(BaseModel):
    tickers: Optional[List[str]] = None

@app.get("/")
def read_root():
    return {"status": "running", "project": "AI Trading Lab", "time": datetime.now()}

@app.get("/api/portfolio")
def get_portfolio_status(db: Session = Depends(get_db)):
    """Retrieve current portfolio, open positions, and calculated PnL."""
    portfolio = PortfolioManager.get_portfolio(db)
    positions = PortfolioManager.get_positions(db)
    
    # Recalculate portfolio value with live prices
    try:
        PortfolioManager.recalculate_portfolio_value(db)
    except Exception as e:
        logger.error(f"Error updating portfolio value on fetch: {e}")
        
    pos_list = []
    for pos in positions:
        quote = finnhub_client.get_current_price(pos.ticker)
        current_price = quote["price"]
        value = pos.quantity * current_price
        cost_basis = pos.quantity * pos.average_buy_price
        unrealized_pnl = value - cost_basis
        unrealized_pnl_pct = (current_price - pos.average_buy_price) / pos.average_buy_price if pos.average_buy_price > 0 else 0
        
        pos_list.append({
            "ticker": pos.ticker,
            "quantity": pos.quantity,
            "average_buy_price": pos.average_buy_price,
            "current_price": current_price,
            "total_value": value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct
        })
        
    return {
        "cash_balance": portfolio.cash_balance,
        "total_value": portfolio.total_value,
        "total_unrealized_pnl": sum(p["unrealized_pnl"] for p in pos_list),
        "positions": pos_list,
        "updated_at": portfolio.updated_at
    }

@app.post("/api/scan")
def trigger_manual_scan(request: ManualScanRequest, db: Session = Depends(get_db)):
    """Trigger an on-demand market scan and order execution."""
    tickers = request.tickers if request.tickers else config.DEFAULT_TICKERS
    try:
        results = TradingEngine.run_market_scan(db, tickers)
        return {"success": True, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Market scan failed: {str(e)}")

@app.get("/api/history")
def get_trading_history(limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve full history of trades executed."""
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(limit).all()
    return trades

@app.get("/api/strategy-logs")
def get_strategy_logs(limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve log history of generated strategy signals."""
    logs = db.query(StrategyLog).order_by(StrategyLog.timestamp.desc()).limit(limit).all()
    return logs

@app.post("/api/backtest")
def run_historical_backtest(req: BacktestRequest):
    """Run a historical simulation on a ticker."""
    try:
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
    backtester = HistoricalBacktester()
    res = backtester.run_backtest(
        ticker=req.ticker,
        start_date=start_dt,
        end_date=end_dt,
        stop_loss_pct=req.stop_loss,
        take_profit_pct=req.take_profit
    )
    return res

@app.get("/api/ai-report")
def get_ai_report(db: Session = Depends(get_db)):
    """Generate an AI commentary report of portfolio performance."""
    portfolio = PortfolioManager.get_portfolio(db)
    positions = PortfolioManager.get_positions(db)
    trades = db.query(Trade).all()
    
    pos_data = [{"ticker": p.ticker, "quantity": p.quantity, "average_buy_price": p.average_buy_price} for p in positions]
    trade_data = [{"ticker": t.ticker, "action": t.action, "profit_loss": t.profit_loss, "total_value": t.total_value} for t in trades]
    
    report = ai_analysis_module.generate_portfolio_report(
        portfolio_val=portfolio.total_value,
        cash=portfolio.cash_balance,
        positions=pos_data,
        trades=trade_data
    )
    return {"report": report}

@app.get("/api/config")
def get_current_config():
    """Retrieve current system configuration settings."""
    return {
        "tickers": config.DEFAULT_TICKERS,
        "scan_frequency_seconds": config.SCAN_FREQUENCY_SECONDS,
        "database": config.DATABASE_URL.split("@")[-1] if "@" in config.DATABASE_URL else "SQLite"
    }

@app.post("/api/reset")
def reset_portfolio_database(db: Session = Depends(get_db)):
    """Reset the database to starting state ($10,000 cash, no trades, no positions)."""
    try:
        # Clear positions, trades, logs, market data
        db.query(Position).delete()
        db.query(Trade).delete()
        db.query(StrategyLog).delete()
        db.query(MarketData).delete()
        
        # Reset Portfolio
        portfolio = db.query(Portfolio).first()
        if portfolio:
            portfolio.cash_balance = 10000.0
            portfolio.total_value = 10000.0
            portfolio.updated_at = datetime.now()
        else:
            portfolio = Portfolio(cash_balance=10000.0, total_value=10000.0)
            db.add(portfolio)
            
        db.commit()
        logger.info("User triggered database reset. Starting balance reset to $10,000.00.")
        return {"success": True, "message": "Database and portfolio reset successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")
