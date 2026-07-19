from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class OrderRequest(BaseModel):
    ticker: str
    action: str  # BUY or SELL
    quantity: float
    price: float
    reason: Optional[str] = "Manual Trade"

class OrderResponse(BaseModel):
    id: Optional[int] = None
    ticker: str
    action: str
    quantity: float
    price: float
    total_value: float
    profit_loss: float
    timestamp: datetime
    success: bool
    message: str
