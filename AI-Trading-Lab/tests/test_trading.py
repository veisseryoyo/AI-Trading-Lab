import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Base, Portfolio, Position, Trade
from backend.trading_engine.portfolio import PortfolioManager

@pytest.fixture(name="db_session")
def fixture_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        # Seed default portfolio
        portfolio = Portfolio(cash_balance=10000.0, total_value=10000.0)
        db.add(portfolio)
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_execute_buy_success(db_session):
    res = PortfolioManager.execute_buy(
        db=db_session,
        ticker="AAPL",
        quantity=10.0,
        price=150.0,
        reason="Test buy"
    )
    
    assert res["success"] is True
    
    # Check cash deduction
    portfolio = db_session.query(Portfolio).first()
    assert portfolio.cash_balance == 8500.0 # 10000 - 1500
    
    # Check position creation
    pos = db_session.query(Position).filter(Position.ticker == "AAPL").first()
    assert pos is not None
    assert pos.quantity == 10.0
    assert pos.average_buy_price == 150.0

def test_execute_buy_insufficient_funds(db_session):
    res = PortfolioManager.execute_buy(
        db=db_session,
        ticker="AAPL",
        quantity=100.0,
        price=150.0,  # Cost = 15000, cash = 10000
        reason="Test over-buy"
    )
    
    assert res["success"] is False
    assert "Insufficient cash" in res["message"]
    
    # Check that portfolio wasn't modified
    portfolio = db_session.query(Portfolio).first()
    assert portfolio.cash_balance == 10000.0
    
    pos = db_session.query(Position).filter(Position.ticker == "AAPL").first()
    assert pos is None

def test_execute_sell_success(db_session):
    # Set up initial position
    pos = Position(ticker="AAPL", quantity=10.0, average_buy_price=150.0)
    db_session.add(pos)
    # Deduct cash for initial buy manually
    portfolio = db_session.query(Portfolio).first()
    portfolio.cash_balance = 8500.0
    db_session.commit()
    
    # Sell 6 shares at $160
    res = PortfolioManager.execute_sell(
        db=db_session,
        ticker="AAPL",
        quantity=6.0,
        price=160.0,
        reason="Test sell"
    )
    
    assert res["success"] is True
    assert res["realized_pnl"] == 60.0 # 6 * (160 - 150)
    
    # Check cash
    portfolio = db_session.query(Portfolio).first()
    assert portfolio.cash_balance == 9460.0 # 8500 + 960
    
    # Check remaining position
    pos = db_session.query(Position).filter(Position.ticker == "AAPL").first()
    assert pos is not None
    assert pos.quantity == 4.0
    assert pos.average_buy_price == 150.0 # average price remains same

def test_execute_sell_all_deletes_position(db_session):
    pos = Position(ticker="AAPL", quantity=10.0, average_buy_price=150.0)
    db_session.add(pos)
    db_session.commit()
    
    res = PortfolioManager.execute_sell(
        db=db_session,
        ticker="AAPL",
        quantity=10.0,
        price=170.0,
        reason="Exit fully"
    )
    
    assert res["success"] is True
    
    # Position should be deleted
    pos = db_session.query(Position).filter(Position.ticker == "AAPL").first()
    assert pos is None
    
    # Trade logged
    trade = db_session.query(Trade).filter(Trade.action == "SELL").first()
    assert trade is not None
    assert trade.profit_loss == 200.0
