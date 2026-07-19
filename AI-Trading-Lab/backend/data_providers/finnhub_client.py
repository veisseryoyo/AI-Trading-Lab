import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from backend.config import config
from backend.utils.logger import logger
from backend.utils.helpers import get_utc_now

class FinnhubClient:
    def __init__(self):
        self.api_key = config.FINNHUB_API_KEY
        self.base_url = "https://finnhub.io/api/v1"
        self.use_fallback = not bool(self.api_key) or self.api_key == "YOUR_FINNHUB_API_KEY"
        if self.use_fallback:
            logger.warning("Finnhub API key not configured or using default template. Falling back to Mock Data Generator.")

    def _request(self, endpoint: str, params: Dict[str, Any], retries: int = 3, backoff: float = 1.0) -> Optional[Dict[str, Any]]:
        """Internal helper to make requests to Finnhub with retries and rate limit handling."""
        if self.use_fallback:
            return None
            
        params["token"] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(retries):
            try:
                response = requests.get(url, params=params, timeout=10)
                
                # Check for rate limit
                if response.status_code == 429:
                    logger.warning(f"Finnhub API rate limited (429). Retrying in {backoff}s... (Attempt {attempt+1}/{retries})")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                    
                # Check for unauthorized / invalid key
                if response.status_code == 401:
                    logger.error("Finnhub API Unauthorized (401). Invalid API key. Activating Mock Fallback.")
                    self.use_fallback = True
                    return None
                    
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Finnhub request error: {e}. Retrying in {backoff}s... (Attempt {attempt+1}/{retries})")
                time.sleep(backoff)
                backoff *= 2
                
        logger.error(f"Failed to connect to Finnhub after {retries} retries. Enabling Mock Fallback temporarily.")
        return None

    def test_connection(self) -> bool:
        """Test the connection to Finnhub API."""
        if self.use_fallback:
            logger.info("Connection test: PASS (Using Mock Data Generator)")
            return True
            
        data = self._request("quote", {"symbol": "AAPL"})
        if data and "c" in data and data["c"] != 0:
            logger.info("Connection test: PASS (Successfully connected to Finnhub API)")
            return True
        else:
            logger.error("Connection test: FAIL (Finnhub API quote returned invalid data)")
            return False

    def get_current_price(self, ticker: str) -> Dict[str, Any]:
        """
        Get current stock quote.
        Returns unified dictionary format:
        {
            "price": float,
            "open": float,
            "high": float,
            "low": float,
            "prev_close": float,
            "timestamp": datetime,
            "ticker": str,
            "source": str
        }
        """
        ticker = ticker.strip().upper()
        if not self.use_fallback:
            res = self._request("quote", {"symbol": ticker})
            if res and "c" in res and res["c"] != 0:
                # Validate response structure
                return {
                    "price": float(res["c"]),
                    "open": float(res["o"]),
                    "high": float(res["h"]),
                    "low": float(res["l"]),
                    "prev_close": float(res["pc"]),
                    "timestamp": datetime.fromtimestamp(res.get("t", int(time.time())), timezone.utc),
                    "ticker": ticker,
                    "source": "Finnhub API"
                }
            else:
                logger.warning(f"Finnhub API failed to fetch quote for {ticker}. Using Mock fallback.")
                
        # Mock Fallback logic
        import random
        # Generates a pseudo-random price based on ticker hash to stay relatively stable
        seed = sum(ord(char) for char in ticker)
        random.seed(seed + int(time.time() / 3600))  # static-ish price changes hourly
        base_price = (seed % 200) + 50.0  # $50 - $250 base
        daily_noise = random.uniform(-0.02, 0.02)
        price = round(base_price * (1 + daily_noise), 2)
        prev_close = round(base_price, 2)
        open_p = round(prev_close * random.uniform(0.99, 1.01), 2)
        high = round(max(price, open_p) * random.uniform(1.00, 1.02), 2)
        low = round(min(price, open_p) * random.uniform(0.98, 1.00), 2)
        
        return {
            "price": price,
            "open": open_p,
            "high": high,
            "low": low,
            "prev_close": prev_close,
            "timestamp": get_utc_now(),
            "ticker": ticker,
            "source": "Mock Data Generator"
        }

    def get_historical_data(self, ticker: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get historical daily candles (open, high, low, close, volume, timestamp).
        """
        ticker = ticker.strip().upper()
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())
        
        if not self.use_fallback:
            res = self._request("stock/candle", {
                "symbol": ticker,
                "resolution": "D",
                "from": start_ts,
                "to": end_ts
            })
            if res and res.get("s") == "ok":
                candles = []
                for i in range(len(res["t"])):
                    candles.append({
                        "timestamp": datetime.fromtimestamp(res["t"][i], timezone.utc),
                        "open": float(res["o"][i]),
                        "high": float(res["h"][i]),
                        "low": float(res["l"][i]),
                        "close": float(res["c"][i]),
                        "volume": int(res["v"][i]),
                        "ticker": ticker
                    })
                return candles
            else:
                logger.warning(f"Finnhub API historical candles failed for {ticker}. Using Mock fallback.")

        # Mock Fallback logic for historical data
        import random
        candles = []
        seed = sum(ord(char) for char in ticker)
        random.seed(seed)
        
        current_date = start_date
        current_price = (seed % 200) + 50.0  # Base price
        
        while current_date <= end_date:
            # Skip weekends for realistic simulation
            if current_date.weekday() < 5:
                # Add momentum trend
                trend = 0.0005 if (seed % 2 == 0) else -0.0002
                change = random.normalvariate(trend, 0.015)
                open_p = current_price
                close_p = current_price * (1 + change)
                high = max(open_p, close_p) * random.uniform(1.0, 1.02)
                low = min(open_p, close_p) * random.uniform(0.98, 1.0)
                vol = int(random.lognormvariate(12, 0.8))
                
                candles.append({
                    "timestamp": current_date.replace(hour=16, minute=0, second=0, microsecond=0, tzinfo=timezone.utc),
                    "open": round(open_p, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close_p, 2),
                    "volume": vol,
                    "ticker": ticker
                })
                current_price = close_p
            current_date += timedelta(days=1)
            
        return candles

    def get_company_profile(self, ticker: str) -> Dict[str, Any]:
        """
        Get company profile details.
        """
        ticker = ticker.strip().upper()
        if not self.use_fallback:
            res = self._request("stock/profile2", {"symbol": ticker})
            if res and "name" in res:
                return {
                    "company_name": res["name"],
                    "industry": res.get("finnhubIndustry", "Unknown"),
                    "market_cap": float(res.get("marketCapitalization", 0.0)) * 1_000_000, # Profile returns cap in millions
                    "ticker": ticker,
                    "source": "Finnhub API"
                }
            else:
                logger.warning(f"Finnhub API profile failed for {ticker}. Using Mock fallback.")
                
        # Mock Profile mapping
        mock_profiles = {
            "AAPL": {"company_name": "Apple Inc.", "industry": "Technology", "market_cap": 3200000000000},
            "MSFT": {"company_name": "Microsoft Corporation", "industry": "Technology", "market_cap": 3100000000000},
            "GOOGL": {"company_name": "Alphabet Inc.", "industry": "Technology", "market_cap": 2100000000000},
            "AMZN": {"company_name": "Amazon.com, Inc.", "industry": "E-commerce", "market_cap": 1900000000000},
            "TSLA": {"company_name": "Tesla, Inc.", "industry": "Automotive", "market_cap": 600000000000},
            "NVDA": {"company_name": "NVIDIA Corporation", "industry": "Semiconductors", "market_cap": 3000000000000},
        }
        
        profile = mock_profiles.get(ticker, {
            "company_name": f"{ticker} Corp",
            "industry": "General Business",
            "market_cap": 10000000000.0
        })
        
        return {
            **profile,
            "ticker": ticker,
            "source": "Mock Profile Generator"
        }

# Instantiate global client singleton
finnhub_client = FinnhubClient()
