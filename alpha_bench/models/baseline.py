"""Baseline trading models for alpha-bench.

This module implements simple baseline models for comparison against LLMs.
Includes random action, trend-following, and other simple strategies.

Usage:
    from alpha_bench.models.baseline import RandomBaselineModel

    model = RandomBaselineModel(model_id, config)
    decision = model.generate_decision(features)
"""

import logging
import random
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from alpha_bench.models.base import BaselineModel, TradingDecision

logger = logging.getLogger(__name__)


class RandomBaselineModel(BaselineModel):
    """Random action baseline model (Monte Carlo control).

    Makes random trading decisions with configurable action distribution.
    Useful as a lower bound baseline.
    """

    def __init__(self, model_id: str, config: Dict[str, Any]):
        """Initialize random baseline model.

        Args:
            model_id: Model identifier
            config: Model configuration
        """
        super().__init__(model_id, config)

        # Get action distribution from config
        self.action_dist = config.get("action_distribution", {
            "buy": 0.33,
            "sell": 0.33,
            "hold": 0.34,
        })

        # Position size
        self.position_size = config.get("position_size", 0.01)

        logger.info(f"Initialized random baseline: {model_id}")

    def generate_decision(
        self,
        features: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> TradingDecision:
        """Generate random trading decision.

        Args:
            features: Feature DataFrame (not used)
            context: Optional context

        Returns:
            Random trading decision
        """
        self.increment_call_count()

        # Randomly select action based on distribution
        actions = list(self.action_dist.keys())
        probabilities = list(self.action_dist.values())
        action = random.choices(actions, weights=probabilities)[0]

        # Get symbol from context
        symbol = context.get("symbol", "UNKNOWN") if context else "UNKNOWN"

        # Create decision
        decision = TradingDecision(
            action=action,
            symbol=symbol,
            size=self.position_size if action != "hold" else 0.0,
            confidence=0.5,  # Random has no confidence
            rationale=f"Random action: {action}",
            metadata={"strategy": "random"},
        )

        return decision


class TrendFollowingModel(BaselineModel):
    """Simple trend-following baseline using EMA crossover.

    Buys when fast EMA crosses above slow EMA, sells when it crosses below.
    Classic simple strategy for comparison.
    """

    def __init__(self, model_id: str, config: Dict[str, Any]):
        """Initialize trend-following model.

        Args:
            model_id: Model identifier
            config: Model configuration
        """
        super().__init__(model_id, config)

        # EMA periods
        self.fast_ema = config.get("fast_ema", 12)
        self.slow_ema = config.get("slow_ema", 26)

        # Position size
        self.position_size = config.get("position_size", 0.02)

        # Signal confirmation
        self.signal_confirmation = config.get("signal_confirmation", True)

        logger.info(
            f"Initialized trend-following baseline: {model_id} "
            f"(EMA {self.fast_ema}/{self.slow_ema})"
        )

    def generate_decision(
        self,
        features: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> TradingDecision:
        """Generate trend-following decision based on EMA crossover.

        Args:
            features: Feature DataFrame with ema_12 and ema_26
            context: Optional context

        Returns:
            Trading decision based on EMA crossover
        """
        self.increment_call_count()

        try:
            # Check if we have required features
            fast_col = f"ema_{self.fast_ema}"
            slow_col = f"ema_{self.slow_ema}"

            if fast_col not in features.columns or slow_col not in features.columns:
                logger.warning(
                    f"Missing EMA features for trend following: {fast_col}, {slow_col}"
                )
                return self._hold_decision(context)

            # Get latest values
            latest = features.iloc[-1]
            fast_ema = latest[fast_col]
            slow_ema = latest[slow_col]

            # Get previous values for crossover detection
            if len(features) >= 2:
                previous = features.iloc[-2]
                prev_fast = previous[fast_col]
                prev_slow = previous[slow_col]
            else:
                prev_fast = fast_ema
                prev_slow = slow_ema

            # Determine action based on crossover
            action = "hold"
            confidence = 0.5
            rationale = "No clear signal"

            # Bullish crossover (fast crosses above slow)
            if fast_ema > slow_ema:
                if not self.signal_confirmation or (prev_fast <= prev_slow):
                    action = "buy"
                    spread = (fast_ema - slow_ema) / slow_ema
                    confidence = min(0.5 + spread * 10, 0.9)
                    rationale = f"Bullish: Fast EMA ({fast_ema:.2f}) > Slow EMA ({slow_ema:.2f})"

            # Bearish crossover (fast crosses below slow)
            elif fast_ema < slow_ema:
                if not self.signal_confirmation or (prev_fast >= prev_slow):
                    action = "sell"
                    spread = (slow_ema - fast_ema) / slow_ema
                    confidence = min(0.5 + spread * 10, 0.9)
                    rationale = f"Bearish: Fast EMA ({fast_ema:.2f}) < Slow EMA ({slow_ema:.2f})"

            # Get symbol
            symbol = context.get("symbol", "UNKNOWN") if context else "UNKNOWN"

            # Create decision
            decision = TradingDecision(
                action=action,
                symbol=symbol,
                size=self.position_size if action != "hold" else 0.0,
                confidence=confidence,
                rationale=rationale,
                metadata={
                    "strategy": "ema_crossover",
                    "fast_ema": float(fast_ema),
                    "slow_ema": float(slow_ema),
                },
            )

            return decision

        except Exception as e:
            logger.error(f"Error in trend-following decision: {e}")
            self.increment_error_count()
            return self._hold_decision(context)

    def _hold_decision(self, context: Optional[Dict[str, Any]]) -> TradingDecision:
        """Create a safe hold decision.

        Args:
            context: Optional context

        Returns:
            Hold decision
        """
        symbol = context.get("symbol", "UNKNOWN") if context else "UNKNOWN"
        return TradingDecision(
            action="hold",
            symbol=symbol,
            size=0.0,
            confidence=0.0,
            rationale="Error or insufficient data",
            metadata={"strategy": "ema_crossover", "error": True},
        )


class BuyAndHoldModel(BaselineModel):
    """Buy and hold baseline strategy.

    Buys at the beginning and holds for the entire period.
    """

    def __init__(self, model_id: str, config: Dict[str, Any]):
        """Initialize buy and hold model.

        Args:
            model_id: Model identifier
            config: Model configuration
        """
        super().__init__(model_id, config)

        self.initial_buy_fraction = config.get("initial_buy_fraction", 0.95)
        self.has_bought = False

        logger.info(f"Initialized buy-and-hold baseline: {model_id}")

    def generate_decision(
        self,
        features: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> TradingDecision:
        """Generate buy decision on first call, then hold.

        Args:
            features: Feature DataFrame
            context: Optional context

        Returns:
            Buy decision on first call, hold thereafter
        """
        self.increment_call_count()

        symbol = context.get("symbol", "UNKNOWN") if context else "UNKNOWN"

        if not self.has_bought:
            self.has_bought = True
            return TradingDecision(
                action="buy",
                symbol=symbol,
                size=self.initial_buy_fraction,
                confidence=1.0,
                rationale="Initial buy for buy-and-hold strategy",
                metadata={"strategy": "buy_and_hold"},
            )
        else:
            return TradingDecision(
                action="hold",
                symbol=symbol,
                size=0.0,
                confidence=1.0,
                rationale="Holding position",
                metadata={"strategy": "buy_and_hold"},
            )
