from typing import Dict, Any, Tuple
from backend.utils.logger import logger

class RiskManager:
    """
    Risk Manager:
    Enforces risk rules to protect capital.
    Includes allocation limits, stop-loss and take-profit validations, and drawdown calculations.
    """
    
    def __init__(
        self, 
        max_allocation_pct: float = 0.10,  # Max 10% portfolio value per stock
        stop_loss_pct: float = 0.05,        # 5% stop-loss
        take_profit_pct: float = 0.15,      # 15% take-profit
        min_risk_reward_ratio: float = 2.0  # 1:2 risk/reward ratio minimum
    ):
        self.max_allocation_pct = max_allocation_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_risk_reward_ratio = min_risk_reward_ratio

    def validate_buy(
        self, 
        ticker: str, 
        current_price: float, 
        portfolio_value: float, 
        current_position_value: float
    ) -> Tuple[bool, str, float]:
        """
        Validate whether a buy trade is allowed.
        Returns:
            (allowed: bool, reason: str, max_quantity_to_buy: float)
        """
        if portfolio_value <= 0:
            return False, "Portfolio has no value", 0.0
            
        # Calculate max allowable value for this stock
        max_allowed_value = portfolio_value * self.max_allocation_pct
        
        # Calculate how much more value we can allocate
        remaining_allocation = max_allowed_value - current_position_value
        
        if remaining_allocation <= 0:
            return False, f"Maximum allocation limit of {self.max_allocation_pct*100}% reached for {ticker}", 0.0
            
        # Max quantity we can buy with remaining allocation
        max_qty = remaining_allocation / current_price
        
        # Risk/reward check simulation (e.g. entry at current_price, stop-loss, take-profit)
        # target profit / risk size = (price * take_profit_pct) / (price * stop_loss_pct)
        # Here, ratio is (take_profit_pct) / (stop_loss_pct) = 0.15 / 0.05 = 3.0 (which is >= min_risk_reward_ratio)
        actual_ratio = self.take_profit_pct / self.stop_loss_pct
        if actual_ratio < self.min_risk_reward_ratio:
            return False, f"Risk/Reward ratio ({actual_ratio:.1f}) is below minimum ({self.min_risk_reward_ratio})", 0.0
            
        return True, "Allowed", max_qty

    def check_position_limits(
        self, 
        ticker: str, 
        current_price: float, 
        average_buy_price: float
    ) -> Tuple[bool, str]:
        """
        Check if a position has hit stop-loss or take-profit thresholds.
        Returns:
            (should_exit: bool, reason: str)
        """
        if average_buy_price <= 0:
            return False, "Valid average buy price must be positive."
            
        pct_change = (current_price - average_buy_price) / average_buy_price
        
        # Stop-loss check
        if pct_change <= -self.stop_loss_pct:
            return True, f"STOP-LOSS triggered: Position down {pct_change*100:.2f}% (Limit: -{self.stop_loss_pct*100}%)"
            
        # Take-profit check
        if pct_change >= self.take_profit_pct:
            return True, f"TAKE-PROFIT triggered: Position up {pct_change*100:.2f}% (Limit: {self.take_profit_pct*100}%)"
            
        return False, "Hold position"

    def calculate_drawdown(self, portfolio_history: list[float]) -> float:
        """
        Calculate the maximum drawdown from a history of portfolio values.
        Formula: (Peak - Trough) / Peak
        """
        if not portfolio_history:
            return 0.0
            
        max_drawdown = 0.0
        peak = portfolio_history[0]
        
        for val in portfolio_history:
            if val > peak:
                peak = val
            drawdown = (peak - val) / peak if peak > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        return max_drawdown

# Instantiate global risk manager singleton
risk_manager = RiskManager()
