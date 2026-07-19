import os
from pathlib import Path
from dotenv import load_dotenv
from backend.utils.logger import logger

# Load environment variables from the root folder
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Config:
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    
    # Fallback to a local SQLite database in the backend/ folder if DATABASE_URL is not set
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{Path(__file__).resolve().parent.parent / 'trading_lab.db'}"
    )
    
    # Convert SCAN_FREQUENCY_SECONDS to integer (default: 60 seconds)
    SCAN_FREQUENCY_SECONDS: int = int(os.getenv("SCAN_FREQUENCY_SECONDS", "60"))
    
    # Parse DEFAULT_TICKERS (comma-separated list)
    tickers_raw: str = os.getenv("DEFAULT_TICKERS", "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA")
    DEFAULT_TICKERS: list[str] = [ticker.strip().upper() for ticker in tickers_raw.split(",") if ticker.strip()]

config = Config()

# Log current configuration (obscuring the API key)
key_obscured = config.FINNHUB_API_KEY[:4] + "*" * 12 if config.FINNHUB_API_KEY else "NOT_SET"
logger.info(f"Configuration Loaded. DB URL: {config.DATABASE_URL.split('@')[-1] if '@' in config.DATABASE_URL else config.DATABASE_URL}, Finnhub API Key: {key_obscured}")
