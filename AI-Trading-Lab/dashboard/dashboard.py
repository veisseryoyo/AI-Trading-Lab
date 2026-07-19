import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
import plotly.express as px
import os
import sys

# Add project root to sys.path so we can fallback to importing modules directly if the backend is offline
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.database import SessionLocal
    from backend.trading_engine.portfolio import PortfolioManager
    from backend.trading_engine.engine import TradingEngine
    from backend.backtesting.backtester import HistoricalBacktester
    from backend.models import Trade, StrategyLog, Portfolio, Position, MarketData
    from backend.ai_analysis import ai_analysis_module
    from backend.data_providers.finnhub_client import finnhub_client
    from backend.config import config
    DIRECT_IMPORT_AVAILABLE = True
except ImportError:
    DIRECT_IMPORT_AVAILABLE = False

# Backend URL config
BACKEND_URL = "http://localhost:8000"

def check_backend_online() -> bool:
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=1)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

BACKEND_ONLINE = check_backend_online()

# Helper to fetch data (with automatic direct-DB fallback)
def get_portfolio_data():
    if BACKEND_ONLINE:
        try:
            return requests.get(f"{BACKEND_URL}/api/portfolio").json()
        except Exception:
            pass
            
    if DIRECT_IMPORT_AVAILABLE:
        db = SessionLocal()
        try:
            PortfolioManager.recalculate_portfolio_value(db)
            portfolio = PortfolioManager.get_portfolio(db)
            positions = PortfolioManager.get_positions(db)
            
            pos_list = []
            for pos in positions:
                quote = finnhub_client.get_current_price(pos.ticker)
                curr_price = quote["price"]
                value = pos.quantity * curr_price
                cost_basis = pos.quantity * pos.average_buy_price
                unrealized_pnl = value - cost_basis
                unrealized_pnl_pct = (curr_price - pos.average_buy_price) / pos.average_buy_price if pos.average_buy_price > 0 else 0
                
                pos_list.append({
                    "ticker": pos.ticker,
                    "quantity": pos.quantity,
                    "average_buy_price": pos.average_buy_price,
                    "current_price": curr_price,
                    "total_value": value,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_pct": unrealized_pnl_pct
                })
                
            return {
                "cash_balance": portfolio.cash_balance,
                "total_value": portfolio.total_value,
                "total_unrealized_pnl": sum(p["unrealized_pnl"] for p in pos_list),
                "positions": pos_list,
                "updated_at": portfolio.updated_at.isoformat() if hasattr(portfolio.updated_at, 'isoformat') else str(portfolio.updated_at)
            }
        finally:
            db.close()
            
    # Mock data if everything else fails
    return {
        "cash_balance": 10000.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
        "positions": [],
        "updated_at": str(datetime.now())
    }

def run_scan():
    if BACKEND_ONLINE:
        try:
            res = requests.post(f"{BACKEND_URL}/api/scan", json={}).json()
            return res.get("success", False), "Market scan executed via API."
        except Exception as e:
            return False, f"API trigger failed: {e}"
            
    if DIRECT_IMPORT_AVAILABLE:
        db = SessionLocal()
        try:
            results = TradingEngine.run_market_scan(db, config.DEFAULT_TICKERS)
            return True, f"Scan completed successfully for: {list(results.keys())}"
        except Exception as e:
            return False, f"Scan failed: {e}"
        finally:
            db.close()
            
    return False, "Backend and local modules unavailable."

def reset_db():
    if BACKEND_ONLINE:
        try:
            res = requests.post(f"{BACKEND_URL}/api/reset").json()
            return res.get("success", False)
        except Exception:
            pass
            
    if DIRECT_IMPORT_AVAILABLE:
        db = SessionLocal()
        try:
            db.query(Position).delete()
            db.query(Trade).delete()
            db.query(StrategyLog).delete()
            db.query(MarketData).delete()
            portfolio = db.query(Portfolio).first()
            if portfolio:
                portfolio.cash_balance = 10000.0
                portfolio.total_value = 10000.0
            db.commit()
            return True
        except Exception:
            db.rollback()
        finally:
            db.close()
    return False

def get_trades():
    if BACKEND_ONLINE:
        try:
            return requests.get(f"{BACKEND_URL}/api/history").json()
        except Exception:
            pass
            
    if DIRECT_IMPORT_AVAILABLE:
        db = SessionLocal()
        try:
            trades = db.query(Trade).order_by(Trade.timestamp.desc()).all()
            return [{
                "ticker": t.ticker,
                "action": t.action,
                "quantity": t.quantity,
                "price": t.price,
                "total_value": t.total_value,
                "profit_loss": t.profit_loss,
                "reason": t.reason,
                "timestamp": t.timestamp.isoformat() if hasattr(t.timestamp, 'isoformat') else str(t.timestamp)
            } for t in trades]
        finally:
            db.close()
    return []

def get_strategy_logs():
    if BACKEND_ONLINE:
        try:
            return requests.get(f"{BACKEND_URL}/api/strategy-logs").json()
        except Exception:
            pass
            
    if DIRECT_IMPORT_AVAILABLE:
        db = SessionLocal()
        try:
            logs = db.query(StrategyLog).order_by(StrategyLog.timestamp.desc()).all()
            return [{
                "ticker": t.ticker,
                "signal": t.signal,
                "confidence_score": t.confidence_score,
                "explanation": t.explanation,
                "timestamp": t.timestamp.isoformat() if hasattr(t.timestamp, 'isoformat') else str(t.timestamp)
            } for t in logs]
        finally:
            db.close()
    return []

def get_ai_report():
    if BACKEND_ONLINE:
        try:
            return requests.get(f"{BACKEND_URL}/api/ai-report").json().get("report", "")
        except Exception:
            pass
            
    if DIRECT_IMPORT_AVAILABLE:
        db = SessionLocal()
        try:
            portfolio = PortfolioManager.get_portfolio(db)
            positions = PortfolioManager.get_positions(db)
            trades = db.query(Trade).all()
            
            pos_data = [{"ticker": p.ticker, "quantity": p.quantity, "average_buy_price": p.average_buy_price} for p in positions]
            trade_data = [{"ticker": t.ticker, "action": t.action, "profit_loss": t.profit_loss, "total_value": t.total_value} for t in trades]
            
            return ai_analysis_module.generate_portfolio_report(
                portfolio_val=portfolio.total_value,
                cash=portfolio.cash_balance,
                positions=pos_data,
                trades=trade_data
            )
        finally:
            db.close()
    return "AI Module unavailable."

# Streamlit Page Setup
st.set_page_config(
    page_title="AI Trading Lab Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium CSS Dark Theme
st.markdown("""
<style>
    /* Premium dark mode styling */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #58a6ff;
    }
    div[data-testid="stMetricDelta"] > div {
        font-size: 0.95rem;
    }
    /* Style tables */
    .dataframe {
        border-collapse: collapse;
        width: 100%;
        color: #c9d1d9;
    }
    .dataframe th {
        background-color: #161b22;
        color: #58a6ff;
        text-align: left;
        padding: 8px;
    }
    .dataframe td {
        border: 1px solid #21262d;
        padding: 8px;
    }
    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #1f6feb 0%, #1153b8 100%);
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #388bfd 0%, #1f6feb 100%);
        box-shadow: 0 4px 15px rgba(31, 111, 235, 0.4);
    }
    /* Decorative header gradient line */
    .header-line {
        height: 4px;
        background: linear-gradient(90deg, #1f6feb 0%, #58a6ff 50%, #885df1 100%);
        margin-bottom: 25px;
        border-radius: 2px;
    }
</style>
""", unsafe_allow_html=True)

# Main Title & Subheader
st.title("📈 AI Trading Lab")
st.subheader("Algorithmic Trading Research & Simulation Platform")
st.markdown('<div class="header-line"></div>', unsafe_allow_html=True)

# Sidebar config
st.sidebar.title("🎛️ Control Panel")

# System Connection Status badge
if BACKEND_ONLINE:
    st.sidebar.success("● API Server Online (FastAPI)")
else:
    st.sidebar.warning("● Standalone DB Mode (Direct Engine)")

# Scan settings & actions
st.sidebar.markdown("### ⚡ Quick Actions")
if st.sidebar.button("Run On-Demand Scan"):
    with st.spinner("Executing market scan..."):
        success, msg = run_scan()
        if success:
            st.sidebar.success(msg)
            st.rerun()
        else:
            st.sidebar.error(msg)

if st.sidebar.button("Reset Portfolio to $10,000"):
    if reset_db():
        st.sidebar.success("Database and portfolio reset!")
        st.rerun()
    else:
        st.sidebar.error("Failed to reset database.")

# Config info in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ System Configuration")
tickers_list = config.DEFAULT_TICKERS if DIRECT_IMPORT_AVAILABLE else ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]
st.sidebar.write(f"**Default Tickers:** {', '.join(tickers_list)}")
scan_freq = config.SCAN_FREQUENCY_SECONDS if DIRECT_IMPORT_AVAILABLE else 60
st.sidebar.write(f"**Scan Frequency:** {scan_freq}s")

# Warnings
st.sidebar.warning("⚠️ **Safety Notice:** This platform is intended purely for research, paper trading, and simulation. No real funds are involved. No trading strategies represent guaranteed profits.")

# Fetch portfolio data
port = get_portfolio_data()

# Metric definitions
cash = port.get("cash_balance", 10000.0)
nav = port.get("total_value", 10000.0)
pnl = nav - 10000.0
pnl_pct = (pnl / 10000.0) * 100
positions_list = port.get("positions", [])
open_pos_count = len(positions_list)

# Tabs
tab_overview, tab_portfolio, tab_history, tab_strategy, tab_backtester = st.tabs([
    "📊 Overview", 
    "💼 Portfolio Holdings", 
    "📜 Trading History", 
    "🤖 Strategy & Anomalies",
    "🧪 Historical Backtester"
])

with tab_overview:
    # 4 metrics in columns
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Net Asset Value (NAV)", f"${nav:,.2f}", delta=f"${pnl:+,.2f}")
    with m_col2:
        st.metric("Cash Balance", f"${cash:,.2f}")
    with m_col3:
        st.metric("Return on Investment", f"{pnl_pct:+.2f}%", delta=f"{pnl_pct:+.2f}%")
    with m_col4:
        st.metric("Open Positions", f"{open_pos_count}")
        
    st.markdown("---")
    
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        st.markdown("### 📈 Asset Allocation")
        if open_pos_count > 0:
            labels = ["Cash"] + [p["ticker"] for p in positions_list]
            values = [cash] + [p["total_value"] for p in positions_list]
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3)])
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#c9d1d9',
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No open stock positions. Portfolio is 100% Cash.")
            
    with col_right:
        # AI executive summary
        st.markdown(get_ai_report())

with tab_portfolio:
    st.markdown("### 💼 Current Positions")
    if open_pos_count > 0:
        df_pos = pd.DataFrame(positions_list)
        # Rename columns for presentation
        df_pos_show = df_pos.rename(columns={
            "ticker": "Ticker",
            "quantity": "Shares Held",
            "average_buy_price": "Avg Buy Price ($)",
            "current_price": "Current Price ($)",
            "total_value": "Current Value ($)",
            "unrealized_pnl": "Unrealized PnL ($)",
            "unrealized_pnl_pct": "Unrealized PnL (%)"
        })
        
        # Format currency & percent
        df_pos_show["Avg Buy Price ($)"] = df_pos_show["Avg Buy Price ($)"].map(lambda x: f"${x:,.2f}")
        df_pos_show["Current Price ($)"] = df_pos_show["Current Price ($)"].map(lambda x: f"${x:,.2f}")
        df_pos_show["Current Value ($)"] = df_pos_show["Current Value ($)"].map(lambda x: f"${x:,.2f}")
        df_pos_show["Unrealized PnL ($)"] = df_pos_show["Unrealized PnL ($)"].map(lambda x: f"${x:+,.2f}")
        df_pos_show["Unrealized PnL (%)"] = df_pos_show["Unrealized PnL (%)"].map(lambda x: f"{x*100:+.2f}%")
        
        st.dataframe(df_pos_show, use_container_width=True, hide_index=True)
    else:
        st.info("No active positions. Trigger a market scan in the control panel or configure the API key to generate mock data.")

with tab_history:
    st.markdown("### 📜 Executed Trades Log")
    trades = get_trades()
    if trades:
        df_trades = pd.DataFrame(trades)
        
        # Search & filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            search_ticker = st.text_input("🔍 Filter by Ticker symbol", "").upper().strip()
        with col_f2:
            filter_action = st.selectbox("Action Type", ["ALL", "BUY", "SELL"])
            
        if search_ticker:
            df_trades = df_trades[df_trades["ticker"] == search_ticker]
        if filter_action != "ALL":
            df_trades = df_trades[df_trades["action"] == filter_action]
            
        if not df_trades.empty:
            df_show = df_trades.rename(columns={
                "timestamp": "Execution Time",
                "ticker": "Ticker",
                "action": "Action",
                "quantity": "Shares",
                "price": "Execution Price ($)",
                "total_value": "Total Value ($)",
                "profit_loss": "Realized PnL ($)",
                "reason": "Execution Reason"
            })
            
            # Format
            df_show["Execution Price ($)"] = df_show["Execution Price ($)"].map(lambda x: f"${x:,.2f}")
            df_show["Total Value ($)"] = df_show["Total Value ($)"].map(lambda x: f"${x:,.2f}")
            df_show["Realized PnL ($)"] = df_show["Realized PnL ($)"].map(lambda x: f"${x:+,.2f}" if x != 0 else "$0.00")
            
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.warning("No trades match the current filter criteria.")
    else:
        st.info("No trading history recorded yet.")

with tab_strategy:
    st.markdown("### 🤖 Strategy Monitoring & Signals")
    logs = get_strategy_logs()
    
    col_l, col_r = st.columns([3, 2])
    
    with col_l:
        st.markdown("#### Recent Decision Logs")
        if logs:
            df_logs = pd.DataFrame(logs)
            df_logs_show = df_logs.rename(columns={
                "timestamp": "Time Analyzed",
                "ticker": "Ticker",
                "signal": "Decision Signal",
                "confidence_score": "Confidence Score (%)",
                "explanation": "Technical Logic Explanation"
            })
            st.dataframe(df_logs_show, use_container_width=True, hide_index=True)
        else:
            st.info("No strategy execution logs yet. Run an on-demand scan.")
            
    with col_r:
        st.markdown("#### Anomaly & Volatility Scanner")
        selected_scan_ticker = st.selectbox("Select stock to scan for anomalies", tickers_list)
        
        if DIRECT_IMPORT_AVAILABLE:
            try:
                # Fetch 30 days of candles
                end = datetime.now(timezone.utc)
                start = end - timedelta(days=30)
                candles = finnhub_client.get_historical_data(selected_scan_ticker, start, end)
                
                anomaly_commentary = ai_analysis_module.detect_unusual_behavior(selected_scan_ticker, candles)
                st.markdown(anomaly_commentary)
                
                # Plot the last 30 days close
                if candles:
                    df_candles = pd.DataFrame(candles)
                    fig_candles = px.line(df_candles, x="timestamp", y="close", title=f"30-Day Close Price for {selected_scan_ticker}")
                    fig_candles.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='#c9d1d9',
                        xaxis_gridcolor='#21262d',
                        yaxis_gridcolor='#21262d'
                    )
                    st.plotly_chart(fig_candles, use_container_width=True)
            except Exception as e:
                st.error(f"Error fetching anomalies: {e}")
        else:
            st.info("Anomaly scanner requires local module imports.")

with tab_backtester:
    st.markdown("### 🧪 Historical Backtester Engine")
    st.write("Evaluate how the active strategy would perform in the past using historical market data.")
    
    # Backtest form parameters
    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        bt_ticker = st.text_input("Ticker to Backtest", "AAPL").upper().strip()
        bt_start = st.date_input("Start Date", datetime.now() - timedelta(days=365*2))
    with col_b2:
        bt_stop_loss = st.slider("Stop-Loss Threshold (%)", 1.0, 20.0, 5.0, step=0.5) / 100.0
        bt_end = st.date_input("End Date", datetime.now())
    with col_b3:
        bt_take_profit = st.slider("Take-Profit Threshold (%)", 2.0, 50.0, 15.0, step=0.5) / 100.0
        
    if st.button("Run Historical Simulation"):
        if bt_start >= bt_end:
            st.error("Error: Start Date must be earlier than End Date.")
        else:
            with st.spinner("Running historical backtest simulation..."):
                # Call backtester
                if DIRECT_IMPORT_AVAILABLE:
                    try:
                        backtester = HistoricalBacktester()
                        res = backtester.run_backtest(
                            ticker=bt_ticker,
                            start_date=datetime.combine(bt_start, datetime.min.time(), timezone.utc),
                            end_date=datetime.combine(bt_end, datetime.min.time(), timezone.utc),
                            stop_loss_pct=bt_stop_loss,
                            take_profit_pct=bt_take_profit
                        )
                        
                        if res.get("success", False):
                            st.success(f"Backtest successfully executed for {bt_ticker}!")
                            
                            # Metrics summary
                            st.markdown("#### 📈 Backtest Performance Summary")
                            bm1, bm2, bm3, bm4 = st.columns(4)
                            with bm1:
                                st.metric("Final Portfolio Value", f"${res['final_value']:,.2f}", delta=f"{(res['final_value']-10000.0)/100:+.2f}%")
                            with bm2:
                                st.metric("Annualized Return", f"{res['annualized_return']*100:+.2f}%")
                            with bm3:
                                st.metric("Max Drawdown", f"{res['max_drawdown']*100:.2f}%")
                            with bm4:
                                st.metric("Win Rate / Completed Trades", f"{res['win_rate']*100:.1f}% ({res['num_completed_trades']} Trades)")
                                
                            # Detail metrics
                            st.markdown(f"""
                            - **Total Returns:** {res['total_return']*100:+.2f}% (Starting: $10,000.00)
                            - **Sharpe Ratio:** {res['sharpe_ratio']:.2f}
                            - **Average Trade Result:** ${res['average_trade_pnl']:+,.2f}
                            """)
                            
                            # Performance Chart
                            st.markdown("#### 📊 Portfolio Value Curve")
                            hist_df = pd.DataFrame({
                                "Date": res["timestamps"],
                                "Portfolio Value": res["portfolio_history"]
                            })
                            fig_bt = px.line(hist_df, x="Date", y="Portfolio Value", title=f"Equity Curve - {bt_ticker}")
                            fig_bt.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font_color='#c9d1d9',
                                xaxis_gridcolor='#21262d',
                                yaxis_gridcolor='#21262d'
                            )
                            st.plotly_chart(fig_bt, use_container_width=True)
                            
                            # Trade logs table
                            st.markdown("#### 📜 Simulated Trades")
                            if res["trades"]:
                                df_bt_trades = pd.DataFrame(res["trades"])
                                df_bt_show = df_bt_trades.rename(columns={
                                    "timestamp": "Execution Time",
                                    "action": "Action",
                                    "price": "Execution Price ($)",
                                    "quantity": "Shares",
                                    "total_value": "Total Value ($)",
                                    "pnl": "Realized PnL ($)",
                                    "pnl_pct": "Return (%)",
                                    "reason": "Execution Logic"
                                })
                                df_bt_show["Execution Price ($)"] = df_bt_show["Execution Price ($)"].map(lambda x: f"${x:,.2f}")
                                df_bt_show["Total Value ($)"] = df_bt_show["Total Value ($)"].map(lambda x: f"${x:,.2f}")
                                df_bt_show["Realized PnL ($)"] = df_bt_show["Realized PnL ($)"].map(lambda x: f"${x:+,.2f}" if x != 0 else "$0.00")
                                df_bt_show["Return (%)"] = df_bt_show["Return (%)"].map(lambda x: f"{x*100:+.2f}%" if x != 0 else "0.00%")
                                st.dataframe(df_bt_show, use_container_width=True, hide_index=True)
                            else:
                                st.info("No trades were triggered during the backtest period. Try extending the date range or adjusting the strategy parameters.")
                                
                        else:
                            st.error(res.get("message", "Backtesting simulation failed."))
                            
                    except Exception as e:
                        st.error(f"Failed to run local simulation: {e}")
                        import traceback
                        st.error(traceback.format_exc())
                else:
                    st.error("Historical Backtester module imports failed. Please check backend installation.")
