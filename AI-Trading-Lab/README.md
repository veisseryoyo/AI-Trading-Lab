# AI Trading Lab

AI Trading Lab is a professional-grade automated stock analysis, algorithmic backtesting, and paper trading research platform. The system retrieves real-time quotes and historical data from the Finnhub API, evaluates stocks using a momentum-based indicator model, performs risk management checks, and runs an automated scanning and execution loop. Results are presented in a high-fidelity Streamlit dashboard.

## Features

- **Finnhub API Integration**: Fetches daily candles, live stock quotes, and company profiles with automatic rate-limit backing off and network error handling.
- **Mock Data Fallback**: Works out-of-the-box using simulated quotes if a Finnhub API key is not configured or is invalid.
- **Smart Momentum Strategy**: Trend-following system combining SMA crossovers (20, 50, 200), RSI analysis, MACD histograms, and relative volume surges.
- **Paper Trading Engine**: Decoupled virtual broker tracking cash balance (starting $10,000), position holdings, and realized/unrealized PnL.
- **Automated Scheduler**: Background scanning engine that polls, runs strategy analysis, validates trades, and executes orders automatically.
- **Risk Management**: Enforces strict position allocation constraints (maximum 10% exposure per stock), tracks maximum portfolio drawdown, and checks stop-loss (5%) and take-profit (15%) boundaries dynamically.
- **Historical Backtesting Engine**: Performs rolling-window simulations over historical candles to compute performance metrics (Sharpe ratio, Win rate, drawdowns, annualized returns).
- **Streamlit Dashboard**: Dark-themed interactive interface displaying Portfolio Overview, Active Positions, Executed Trades history, Strategy logs, Anomaly scanning, and interactive backtesting charts.

---

## Project Structure

```text
AI-Trading-Lab/
├── backend/
│   ├── main.py                  # FastAPI Application & Background Scheduler
│   ├── config.py                # Environment configuration
│   ├── database.py              # SQLAlchemy DB setup & seeder
│   ├── models.py                # SQLAlchemy ORM schemas
│   ├── ai_analysis.py           # Anomaly detector & AI Report Generator
│   ├── data_providers/
│   │   └── finnhub_client.py    # Finnhub API Wrapper & Mock Fallback
│   ├── strategies/
│   │   ├── momentum_strategy.py # Smart Momentum trading strategy rules
│   │   └── strategy_manager.py  # Manager interface for strategy swapping
│   ├── trading_engine/
│   │   ├── engine.py            # Core market scan & orchestration logic
│   │   ├── portfolio.py         # Position manager & virtual executor
│   │   └── orders.py            # Order request schema models
│   ├── indicators/
│   │   └── technical_indicators.py # Calculations for SMA, RSI, MACD
│   ├── risk_management/
│   │   └── risk_manager.py      # Protection rules (limits, SL, TP)
│   ├── backtesting/
│   │   └── backtester.py        # Historical simulation engine
│   └── utils/
│       ├── logger.py            # Console output formatting
│       └── helpers.py           # Text/date formatters
├── dashboard/
│   └── dashboard.py             # Streamlit dashboard code
├── tests/                       # Pytest verification suites
├── requirements.txt             # Python dependencies
├── .env.example                 # Config template
└── README.md                    # System documentation
```

---

## Installation & Setup

### 1. Python Environment Setup
Ensure you have Python 3.12+ installed. Clone or copy the directory:

```bash
cd AI-Trading-Lab
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

Install all necessary packages:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit the `.env` file to add your API credentials:
- **`FINNHUB_API_KEY`**: Obtain a free API key at [Finnhub](https://finnhub.io/) and paste it. If left blank or template value is used, the platform automatically starts in Mock mode using simulated data.
- **`DATABASE_URL`**: Defaults to SQLite (`sqlite:///./trading_lab.db`). To connect to a live Supabase PostgreSQL server, configure:
  `DATABASE_URL=postgresql://postgres:[password]@[db-host].supabase.co:5432/postgres`

---

## Running Locally

To run the system locally, you can start the backend API and dashboard.

### Step 1: Start the FastAPI Backend
Start the FastAPI server. This runs the background scheduler worker which executes market scans every minute (as configured in `.env`).
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
You can view the interactive documentation at `http://127.0.0.1:8000/docs`.

### Step 2: Start the Streamlit Dashboard
Run the Streamlit frontend:
```bash
streamlit run dashboard/dashboard.py
```
This will open your browser to `http://localhost:8501`. If the FastAPI backend is running, the dashboard will connect to it automatically. If the backend is offline, the dashboard falls back to Direct DB mode.

---

## Running Verification Tests

To verify calculations and system transactions, run the test suites:
```bash
python -m pytest
```

---

## Extending the Platform

### Adding New Strategies
1. Create a new strategy class in `backend/strategies/` (e.g. `mean_reversion.py`). It should implement an `analyze(self, df: pd.DataFrame) -> dict` method returning:
   ```json
   {
     "signal": "BUY" | "SELL" | "HOLD",
     "confidence": 0-100,
     "explanation": "text rationale"
   }
   ```
2. Register the strategy inside `backend/strategies/strategy_manager.py`:
   ```python
   from backend.strategies.mean_reversion import MeanReversionStrategy
   # ...
   self.strategies = {
       "momentum": SmartMomentumStrategy(),
       "mean_reversion": MeanReversionStrategy()
   }
   ```
3. Set your active strategy in `strategy_manager.py` or change it dynamically by calling `strategy_manager.set_active_strategy("mean_reversion")`.

### Connecting to a Real Broker
The system is designed with a fully decoupled broker interface (`PortfolioManager` in `backend/trading_engine/portfolio.py` and `TradingEngine` in `backend/trading_engine/engine.py`).
To switch from paper trading to live trading:
1. Create a broker client wrapper (e.g. for Alpaca, Interactive Brokers, or Robinhood) under `backend/data_providers/`.
2. Replace call statements in `PortfolioManager.execute_buy` and `PortfolioManager.execute_sell` with actual API order executions via your broker client.
3. Replace the `PortfolioManager.recalculate_portfolio_value` and `Position` checks with API calls that fetch your actual account equity and open broker positions.
