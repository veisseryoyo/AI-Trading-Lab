import pytest
from backend.data_providers.finnhub_client import FinnhubClient

def test_finnhub_client_initialization():
    client = FinnhubClient()
    # Check that it initializes
    assert client is not None
    # We should have configured it, but fallback depends on whether user's key is valid
    assert hasattr(client, 'use_fallback')

def test_connection_testing():
    client = FinnhubClient()
    # Test connection will return True either via real API request or fallback
    connection_ok = client.test_connection()
    assert connection_ok is True

def test_get_current_price():
    client = FinnhubClient()
    quote = client.get_current_price("AAPL")
    
    assert "price" in quote
    assert "ticker" in quote
    assert quote["ticker"] == "AAPL"
    assert quote["price"] > 0
    assert "prev_close" in quote

def test_get_company_profile():
    client = FinnhubClient()
    profile = client.get_company_profile("AAPL")
    
    assert "company_name" in profile
    assert "industry" in profile
    assert profile["ticker"] == "AAPL"

def test_get_historical_data():
    from datetime import datetime, timedelta
    client = FinnhubClient()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)
    
    candles = client.get_historical_data("AAPL", start_date, end_date)
    assert isinstance(candles, list)
    if len(candles) > 0:
        first = candles[0]
        assert "open" in first
        assert "close" in first
        assert "high" in first
        assert "low" in first
        assert "volume" in first
        assert first["ticker"] == "AAPL"
