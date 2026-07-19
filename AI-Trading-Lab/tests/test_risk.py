import pytest
from backend.risk_management.risk_manager import RiskManager

def test_validate_buy_limit():
    # Allocations check: Max 10% allocation per stock
    risk = RiskManager(max_allocation_pct=0.10)
    
    # Portfolio total value = $10,000. Max allocation is $1,000.
    # Case 1: No current position. Let's see if allowed.
    allowed, reason, max_qty = risk.validate_buy(
        ticker="AAPL",
        current_price=100.0,
        portfolio_value=10000.0,
        current_position_value=0.0
    )
    
    assert allowed is True
    # Max allocation is $1,000, price is $100 -> max quantity = 10
    assert max_qty == 10.0
    
    # Case 2: Already holding $800 worth of AAPL. Remaining allocation is $200.
    allowed, reason, max_qty = risk.validate_buy(
        ticker="AAPL",
        current_price=100.0,
        portfolio_value=10000.0,
        current_position_value=800.0
    )
    assert allowed is True
    assert max_qty == 2.0 # Remaining $200 / $100 price
    
    # Case 3: Already holding $1,000 worth of AAPL. Remaining allocation is $0.
    allowed, reason, max_qty = risk.validate_buy(
        ticker="AAPL",
        current_price=100.0,
        portfolio_value=10000.0,
        current_position_value=1000.0
    )
    assert allowed is False
    assert "limit" in reason.lower()

def test_check_position_limits():
    risk = RiskManager(stop_loss_pct=0.05, take_profit_pct=0.15)
    
    # Average buy price = 100.0
    # Case 1: Price drops to 94.0 (down 6%, below stop-loss 5%)
    should_exit, reason = risk.check_position_limits(
        ticker="AAPL",
        current_price=94.0,
        average_buy_price=100.0
    )
    assert should_exit is True
    assert "STOP-LOSS" in reason
    
    # Case 2: Price rises to 116.0 (up 16%, above take-profit 15%)
    should_exit, reason = risk.check_position_limits(
        ticker="AAPL",
        current_price=116.0,
        average_buy_price=100.0
    )
    assert should_exit is True
    assert "TAKE-PROFIT" in reason
    
    # Case 3: Normal fluctuation, price is 105 (up 5%, within limits)
    should_exit, reason = risk.check_position_limits(
        ticker="AAPL",
        current_price=105.0,
        average_buy_price=100.0
    )
    assert should_exit is False
    assert "Hold" in reason

def test_calculate_drawdown():
    risk = RiskManager()
    
    # Portfolio values peak at 12000, then drop to 9000 (drawdown = 25%)
    history = [10000.0, 11000.0, 12000.0, 10000.0, 9000.0, 9500.0, 11500.0]
    dd = risk.calculate_drawdown(history)
    
    # Max peak was 12,000, trough after peak was 9,000 -> dd = (12000-9000)/12000 = 0.25
    assert dd == 0.25
    
    # Empty history
    assert risk.calculate_drawdown([]) == 0.0
