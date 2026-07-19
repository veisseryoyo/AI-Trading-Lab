from sqlalchemy.orm import Session
from backend.models import Portfolio, Position, Trade
from backend.utils.helpers import get_utc_now
from backend.utils.logger import logger
from typing import Dict, Any, List

class PortfolioManager:
    """
    Portfolio Manager:
    Manages database transactions for the virtual paper trading portfolio.
    Executes buys/sells and calculates portfolio values.
    """
    
    @staticmethod
    def get_portfolio(db: Session) -> Portfolio:
        """Retrieve the single portfolio row, seeding it if missing."""
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            portfolio = Portfolio(cash_balance=10000.0, total_value=10000.0)
            db.add(portfolio)
            db.commit()
            db.refresh(portfolio)
        return portfolio

    @staticmethod
    def get_positions(db: Session) -> List[Position]:
        """Get all open positions."""
        return db.query(Position).all()

    @staticmethod
    def get_position(db: Session, ticker: str) -> Position:
        """Get open position for a specific ticker."""
        return db.query(Position).filter(Position.ticker == ticker).first()

    @staticmethod
    def execute_buy(
        db: Session, 
        ticker: str, 
        quantity: float, 
        price: float, 
        reason: str
    ) -> Dict[str, Any]:
        """
        Execute virtual BUY trade.
        Decreases cash, increases/creates position, logs trade.
        """
        if quantity <= 0 or price <= 0:
            return {"success": False, "message": "Quantity and price must be greater than zero."}

        portfolio = PortfolioManager.get_portfolio(db)
        total_cost = quantity * price
        
        if portfolio.cash_balance < total_cost:
            return {
                "success": False, 
                "message": f"Insufficient cash. Required: ${total_cost:,.2f}, Available: ${portfolio.cash_balance:,.2f}"
            }
            
        try:
            # Update Portfolio cash balance
            portfolio.cash_balance -= total_cost
            portfolio.updated_at = get_utc_now()
            
            # Update or create Position
            position = PortfolioManager.get_position(db, ticker)
            if position:
                # Recalculate average buy price
                total_qty = position.quantity + quantity
                total_cost_basis = (position.quantity * position.average_buy_price) + total_cost
                position.average_buy_price = round(total_cost_basis / total_qty, 4)
                position.quantity = total_qty
            else:
                position = Position(
                    ticker=ticker,
                    quantity=quantity,
                    average_buy_price=price
                )
                db.add(position)
                
            # Log the Trade
            trade = Trade(
                ticker=ticker,
                action="BUY",
                quantity=quantity,
                price=price,
                total_value=total_cost,
                profit_loss=0.0,
                reason=reason,
                timestamp=get_utc_now()
            )
            db.add(trade)
            db.commit()
            
            # Refresh portfolio total value
            PortfolioManager.recalculate_portfolio_value(db)
            
            logger.info(f"Executed BUY order: {quantity} shares of {ticker} at ${price:.2f} (Reason: {reason})")
            return {
                "success": True, 
                "message": f"Successfully bought {quantity} shares of {ticker} at ${price:.2f}",
                "trade_id": trade.id
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Error executing buy order for {ticker}: {e}")
            return {"success": False, "message": f"Database transaction failed: {str(e)}"}

    @staticmethod
    def execute_sell(
        db: Session, 
        ticker: str, 
        quantity: float, 
        price: float, 
        reason: str
    ) -> Dict[str, Any]:
        """
        Execute virtual SELL trade.
        Increases cash, decreases/deletes position, calculates realized PnL, logs trade.
        """
        if quantity <= 0 or price <= 0:
            return {"success": False, "message": "Quantity and price must be greater than zero."}

        position = PortfolioManager.get_position(db, ticker)
        if not position or position.quantity < quantity:
            available = position.quantity if position else 0.0
            return {
                "success": False, 
                "message": f"Insufficient shares to sell. Required: {quantity}, Available: {available}"
            }
            
        portfolio = PortfolioManager.get_portfolio(db)
        total_proceeds = quantity * price
        
        try:
            # Calculate realized PnL
            cost_basis = quantity * position.average_buy_price
            realized_pnl = total_proceeds - cost_basis
            
            # Update Portfolio cash balance
            portfolio.cash_balance += total_proceeds
            portfolio.updated_at = get_utc_now()
            
            # Update or delete position
            if position.quantity == quantity:
                db.delete(position)
            else:
                position.quantity -= quantity
                
            # Log the Trade
            trade = Trade(
                ticker=ticker,
                action="SELL",
                quantity=quantity,
                price=price,
                total_value=total_proceeds,
                profit_loss=realized_pnl,
                reason=reason,
                timestamp=get_utc_now()
            )
            db.add(trade)
            db.commit()
            
            # Refresh portfolio total value
            PortfolioManager.recalculate_portfolio_value(db)
            
            logger.info(f"Executed SELL order: {quantity} shares of {ticker} at ${price:.2f} (Realized PnL: ${realized_pnl:+.2f})")
            return {
                "success": True, 
                "message": f"Successfully sold {quantity} shares of {ticker} at ${price:.2f}. PnL: ${realized_pnl:+.2f}",
                "trade_id": trade.id,
                "realized_pnl": realized_pnl
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Error executing sell order for {ticker}: {e}")
            return {"success": False, "message": f"Database transaction failed: {str(e)}"}

    @staticmethod
    def recalculate_portfolio_value(db: Session, current_prices: Dict[str, float] = None) -> float:
        """
        Recalculate and update the total value of the portfolio.
        Can fetch current prices from Finnhub or use provided dictionary.
        """
        portfolio = PortfolioManager.get_portfolio(db)
        positions = PortfolioManager.get_positions(db)
        
        total_holdings_value = 0.0
        
        if positions:
            # If current prices are not provided, we fetch them from FinnhubClient
            from backend.data_providers.finnhub_client import finnhub_client
            
            for pos in positions:
                if current_prices and pos.ticker in current_prices:
                    price = current_prices[pos.ticker]
                else:
                    try:
                        quote = finnhub_client.get_current_price(pos.ticker)
                        price = quote["price"]
                    except Exception as e:
                        logger.error(f"Could not get current price for {pos.ticker} to update portfolio: {e}")
                        price = pos.average_buy_price
                total_holdings_value += pos.quantity * price
                
        portfolio.total_value = portfolio.cash_balance + total_holdings_value
        portfolio.updated_at = get_utc_now()
        
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update portfolio total value: {e}")
            
        return portfolio.total_value
