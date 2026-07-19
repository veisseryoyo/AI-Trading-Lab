from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from backend.data_providers.finnhub_client import finnhub_client
from backend.indicators.technical_indicators import compute_indicators
from backend.strategies.strategy_manager import strategy_manager
from backend.risk_management.risk_manager import risk_manager
from backend.trading_engine.portfolio import PortfolioManager
from backend.models import MarketData, StrategyLog, Stock
from backend.utils.logger import logger
from backend.utils.helpers import get_utc_now

class TradingEngine:
    """
    Trading Engine:
    Main orchestrator for paper trading. Checks prices, evaluates strategies,
    applies risk controls, and executes trades.
    """
    
    @staticmethod
    def run_market_scan(db: Session, tickers: list[str]) -> dict:
        """
        Scan a list of tickers. Fetch quote and historical data,
        recalculate indicators, evaluate signals, and execute trades.
        """
        logger.info(f"Starting market scan for: {tickers}")
        scan_results = {}
        
        # 1. Update/Recalculate portfolio value based on latest prices
        latest_prices = {}
        for ticker in tickers:
            try:
                quote = finnhub_client.get_current_price(ticker)
                latest_prices[ticker] = quote["price"]
                
                # Save market data to DB
                md = MarketData(
                    ticker=ticker,
                    price=quote["price"],
                    volume=int(quote["high"] - quote["low"]), # mock volume if needed
                    timestamp=get_utc_now()
                )
                db.add(md)
                
                # Register stock in stocks table if missing
                stock = db.query(Stock).filter(Stock.ticker == ticker).first()
                if not stock:
                    profile = finnhub_client.get_company_profile(ticker)
                    stock = Stock(ticker=ticker, company_name=profile["company_name"])
                    db.add(stock)
                    
            except Exception as e:
                logger.error(f"Failed to fetch current quote for {ticker}: {e}")
                
        db.commit()
        
        # Update portfolio value
        portfolio = PortfolioManager.get_portfolio(db)
        PortfolioManager.recalculate_portfolio_value(db, current_prices=latest_prices)
        
        # 2. Check risk limits (Stop-Loss and Take-Profit) for all open positions
        positions = PortfolioManager.get_positions(db)
        for pos in positions:
            ticker = pos.ticker
            if ticker in latest_prices:
                curr_price = latest_prices[ticker]
                should_exit, exit_reason = risk_manager.check_position_limits(
                    ticker=ticker,
                    current_price=curr_price,
                    average_buy_price=pos.average_buy_price
                )
                
                if should_exit:
                    logger.warning(f"Risk Manager triggered exit for {ticker}. Reason: {exit_reason}")
                    PortfolioManager.execute_sell(
                        db=db,
                        ticker=ticker,
                        quantity=pos.quantity,
                        price=curr_price,
                        reason=exit_reason
                    )
                    
        # 3. Analyze each ticker for new signals
        for ticker in tickers:
            if ticker not in latest_prices:
                continue
                
            curr_price = latest_prices[ticker]
            
            try:
                # Fetch 250 days of historical data for SMA-200
                end_date = get_utc_now()
                start_date = end_date - timedelta(days=365) # 1 year of history
                
                candles = finnhub_client.get_historical_data(ticker, start_date, end_date)
                
                # Append the latest quote to simulate the absolute latest data point
                candles.append({
                    "timestamp": end_date,
                    "open": curr_price,
                    "high": curr_price,
                    "low": curr_price,
                    "close": curr_price,
                    "volume": 0, # simulated volume
                    "ticker": ticker
                })
                
                # Compute indicators
                df = compute_indicators(candles)
                
                # Run strategy analysis
                analysis = strategy_manager.analyze_ticker(df)
                signal = analysis["signal"]
                confidence = analysis["confidence"]
                explanation = analysis["explanation"]
                
                # Log strategy decision
                strat_log = StrategyLog(
                    ticker=ticker,
                    signal=signal,
                    confidence_score=confidence,
                    explanation=explanation,
                    timestamp=get_utc_now()
                )
                db.add(strat_log)
                db.commit()
                
                # Store results
                scan_results[ticker] = {
                    "price": curr_price,
                    "signal": signal,
                    "confidence": confidence,
                    "explanation": explanation
                }
                
                # Process signal decisions
                pos = PortfolioManager.get_position(db, ticker)
                current_pos_val = (pos.quantity * curr_price) if pos else 0.0
                
                if signal == "BUY":
                    # Run buy risk validation
                    allowed, reason, max_qty_allowed = risk_manager.validate_buy(
                        ticker=ticker,
                        current_price=curr_price,
                        portfolio_value=portfolio.total_value,
                        current_position_value=current_pos_val
                    )
                    
                    if allowed:
                        # Standard trade size: Allocate 10% of portfolio value per trade
                        target_allocation = portfolio.total_value * 0.10
                        # Calculate qty
                        qty_to_buy = min(max_qty_allowed, target_allocation / curr_price)
                        # Check cash constraints
                        if qty_to_buy * curr_price > portfolio.cash_balance:
                            qty_to_buy = portfolio.cash_balance / curr_price
                            
                        # Floor to 4 decimal places
                        qty_to_buy = round(qty_to_buy, 4)
                        
                        if qty_to_buy > 0:
                            PortfolioManager.execute_buy(
                                db=db,
                                ticker=ticker,
                                quantity=qty_to_buy,
                                price=curr_price,
                                reason=f"Strategy Buy Signal (Conf: {confidence}%) - {explanation}"
                            )
                        else:
                            logger.info(f"Skipping BUY for {ticker}: Cash balance too low.")
                    else:
                        logger.info(f"BUY signal rejected by Risk Manager for {ticker}. Reason: {reason}")
                        
                elif signal == "SELL":
                    if pos and pos.quantity > 0:
                        PortfolioManager.execute_sell(
                            db=db,
                            ticker=ticker,
                            quantity=pos.quantity,
                            price=curr_price,
                            reason=f"Strategy Sell Signal (Conf: {confidence}%) - {explanation}"
                        )
                    else:
                        logger.info(f"SELL signal for {ticker} ignored: No open position.")
                        
            except Exception as e:
                logger.error(f"Error analyzing or trading {ticker}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                
        # Final update of portfolio total value
        PortfolioManager.recalculate_portfolio_value(db, current_prices=latest_prices)
        
        return scan_results
