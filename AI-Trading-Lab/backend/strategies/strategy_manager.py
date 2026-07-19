from typing import Dict, Any, List
import pandas as pd
from backend.strategies.momentum_strategy import SmartMomentumStrategy
from backend.utils.logger import logger

class StrategyManager:
    """
    Strategy Manager:
    Manages active trading strategies. Allows running analysis and expanding
    to new strategies in the future.
    """
    
    def __init__(self):
        self.strategies = {
            "momentum": SmartMomentumStrategy()
        }
        self.active_strategy_name = "momentum"

    def set_active_strategy(self, strategy_name: str) -> bool:
        """Change the active strategy."""
        if strategy_name in self.strategies:
            self.active_strategy_name = strategy_name
            logger.info(f"Active strategy set to: {strategy_name}")
            return True
        logger.error(f"Strategy {strategy_name} not found.")
        return False

    def list_strategies(self) -> List[str]:
        """List all available strategies."""
        return list(self.strategies.keys())

    def analyze_ticker(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze a ticker's historical DataFrame with the active strategy.
        Returns:
            dict containing: signal, confidence, explanation
        """
        strategy = self.strategies[self.active_strategy_name]
        return strategy.analyze(df)

# Global strategy manager singleton
strategy_manager = StrategyManager()
