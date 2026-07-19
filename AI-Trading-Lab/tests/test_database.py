import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Base, User, Portfolio, Stock, MarketData, Trade, Position, StrategyLog
from backend.utils.helpers import get_utc_now

# In-memory SQLite for isolated testing
DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session")
def fixture_db_session():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_user_creation(db_session):
    user = User(username="test_trader")
    db_session.add(user)
    db_session.commit()
    
    db_user = db_session.query(User).filter(User.username == "test_trader").first()
    assert db_user is not None
    assert db_user.username == "test_trader"
    assert db_user.id is not None

def test_portfolio_initialization(db_session):
    portfolio = Portfolio(cash_balance=10000.0, total_value=10000.0)
    db_session.add(portfolio)
    db_session.commit()
    
    db_portfolio = db_session.query(Portfolio).first()
    assert db_portfolio.cash_balance == 10000.0
    assert db_portfolio.total_value == 10000.0

def test_trade_logging(db_session):
    trade = Trade(
        ticker="AAPL",
        action="BUY",
        quantity=10.0,
        price=150.0,
        total_value=1500.0,
        profit_loss=0.0,
        reason="Test buy order",
        timestamp=get_utc_now()
    )
    db_session.add(trade)
    db_session.commit()
    
    db_trade = db_session.query(Trade).filter(Trade.ticker == "AAPL").first()
    assert db_trade.action == "BUY"
    assert db_trade.quantity == 10.0
    assert db_trade.price == 150.0
    assert db_trade.total_value == 1500.0
