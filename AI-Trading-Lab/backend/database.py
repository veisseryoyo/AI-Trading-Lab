from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import config
from backend.models import Base, Portfolio, User
from backend.utils.logger import logger

# Create SQLAlchemy engine
# Check if sqlite is used and add connection arguments if so
connect_args = {}
if config.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(config.DATABASE_URL, connect_args=connect_args)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for getting DB session in FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create tables and initialize default values if not present."""
    logger.info("Initializing database and checking tables...")
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        db: Session = SessionLocal()
        try:
            # Seed default user if empty
            if db.query(User).count() == 0:
                default_user = User(username="default_trader")
                db.add(default_user)
                db.commit()
                logger.info("Seeded default user 'default_trader'.")
                
            # Seed default portfolio with $10,000 virtual balance if empty
            if db.query(Portfolio).count() == 0:
                default_portfolio = Portfolio(
                    cash_balance=10000.0,
                    total_value=10000.0
                )
                db.add(default_portfolio)
                db.commit()
                logger.info("Initialized default portfolio with $10,000.00 cash balance.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error seeding initial database: {e}")
        finally:
            db.close()
            
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise e
