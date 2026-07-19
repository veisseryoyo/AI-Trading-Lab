from datetime import datetime, timezone
from typing import Union

def format_currency(value: float) -> str:
    """Format a float as currency (USD)."""
    return f"${value:,.2f}"

def format_percentage(value: float) -> str:
    """Format a float as percentage."""
    return f"{value * 100:+.2f}%" if value >= 0 else f"{value * 100:.2f}%"

def clean_ticker(ticker: str) -> str:
    """Standardize stock tickers."""
    return ticker.strip().upper()

def get_utc_now() -> datetime:
    """Get the current datetime in UTC timezone."""
    return datetime.now(timezone.utc)

def parse_timestamp(ts: Union[int, float, str]) -> datetime:
    """Convert unix timestamp or ISO string to UTC datetime."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, timezone.utc)
    elif isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return get_utc_now()
