"""Risk management for alpha-bench.

This module implements risk management rules and constraints for paper trading
simulations, including position size limits, drawdown limits, and exposure caps.

Usage:
    from alpha_bench.simulation.risk import RiskManager

    risk_mgr = RiskManager(config)
    adjusted_size = risk_mgr.apply_risk_limits(decision, portfolio)
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from alpha_bench.models.base import TradingDecision

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    """Portfolio state representation.

    Attributes:
        capital: Total capital (cash + positions value)
        cash: Available cash
        positions: Dict mapping symbol to position size (in currency)
        equity_curve: List of historical equity values
        peak_equity: Maximum equity reached
    """

    capital: float
    cash: float
    positions: Dict[str, float]
    equity_curve: list
    peak_equity: float

    def get_position_value(self, symbol: str) -> float:
        """Get current position value for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Position value in currency units
        """
        return self.positions.get(symbol, 0.0)

    def get_total_exposure(self) -> float:
        """Get total exposure as fraction of capital.

        Returns:
            Total exposure (0.0 to 1.0+)
        """
        if self.capital <= 0:
            return 0.0
        total_positions = sum(abs(v) for v in self.positions.values())
        return total_positions / self.capital

    def get_drawdown(self) -> float:
        """Get current drawdown from peak.

        Returns:
            Drawdown as fraction (0.0 to 1.0)
        """
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.capital) / self.peak_equity


class RiskLimitExceeded(Exception):
    """Raised when risk limits are breached."""

    pass


class RiskManager:
    """Manages risk limits and constraints for trading.

    Implements various risk management rules including position size limits,
    drawdown limits, exposure caps, and daily loss limits.

    Attributes:
        config: Risk management configuration
        daily_pnl: Running daily P&L tracker
        trade_count: Number of trades executed
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize risk manager.

        Args:
            config: Risk management configuration from strategies.yaml
        """
        self.config = config or {}

        # Extract limits from config
        self.max_position_size = self.config.get("max_position_size", 0.25)
        self.max_total_exposure = self.config.get("max_total_exposure", 1.0)
        self.max_daily_loss = self.config.get("max_daily_loss", 0.05)
        self.max_drawdown = self.config.get("max_drawdown", 0.20)
        self.max_positions = self.config.get("max_positions", 5)
        self.max_loss_per_trade = self.config.get("max_loss_per_trade", 0.02)

        # State tracking
        self.daily_pnl = 0.0
        self.trade_count = 0
        self.rejected_trades = 0

        logger.info("Initialized risk manager")

    def apply_risk_limits(
        self,
        decision: TradingDecision,
        portfolio: Portfolio,
        current_price: float,
    ) -> TradingDecision:
        """Apply risk limits to a trading decision.

        Checks all risk constraints and adjusts position size if needed.
        May reject trade entirely by setting action to 'hold'.

        Args:
            decision: Original trading decision
            portfolio: Current portfolio state
            current_price: Current asset price

        Returns:
            Adjusted trading decision (may be modified or rejected)
        """
        # If already hold, no risk checks needed
        if decision.action == "hold":
            return decision

        # Check drawdown limit
        if not self._check_drawdown_limit(portfolio):
            logger.warning("Drawdown limit exceeded, rejecting trade")
            self.rejected_trades += 1
            return self._reject_decision(decision, "Drawdown limit exceeded")

        # Check daily loss limit
        if not self._check_daily_loss_limit(portfolio):
            logger.warning("Daily loss limit exceeded, rejecting trade")
            self.rejected_trades += 1
            return self._reject_decision(decision, "Daily loss limit exceeded")

        # Check max positions limit
        if not self._check_max_positions(decision, portfolio):
            logger.warning("Max positions limit reached, rejecting trade")
            self.rejected_trades += 1
            return self._reject_decision(decision, "Max positions limit reached")

        # Adjust position size based on capital
        adjusted_size = self._adjust_position_size(
            decision.size, decision.action, portfolio, current_price
        )

        # Check if adjusted size is too small to trade
        if adjusted_size * portfolio.capital < 10.0:  # Minimum $10 trade
            logger.debug("Position size too small after risk adjustments")
            return self._reject_decision(decision, "Position size too small")

        # Create adjusted decision
        adjusted_decision = TradingDecision(
            action=decision.action,
            symbol=decision.symbol,
            size=adjusted_size,
            confidence=decision.confidence,
            rationale=decision.rationale
            + f" (risk-adjusted from {decision.size:.4f} to {adjusted_size:.4f})",
            metadata={**(decision.metadata or {}), "risk_adjusted": True},
        )

        logger.debug(
            f"Risk check passed: {decision.action} {decision.symbol} "
            f"size={adjusted_size:.4f}"
        )

        return adjusted_decision

    def _check_drawdown_limit(self, portfolio: Portfolio) -> bool:
        """Check if drawdown is within limits.

        Args:
            portfolio: Current portfolio state

        Returns:
            True if within limits, False otherwise
        """
        drawdown = portfolio.get_drawdown()
        if drawdown > self.max_drawdown:
            logger.warning(
                f"Drawdown {drawdown:.2%} exceeds limit {self.max_drawdown:.2%}"
            )
            return False
        return True

    def _check_daily_loss_limit(self, portfolio: Portfolio) -> bool:
        """Check if daily loss is within limits.

        Args:
            portfolio: Current portfolio state

        Returns:
            True if within limits, False otherwise
        """
        if portfolio.capital <= 0:
            return False

        daily_loss_pct = -self.daily_pnl / portfolio.capital
        if daily_loss_pct > self.max_daily_loss:
            logger.warning(
                f"Daily loss {daily_loss_pct:.2%} exceeds limit {self.max_daily_loss:.2%}"
            )
            return False
        return True

    def _check_max_positions(
        self, decision: TradingDecision, portfolio: Portfolio
    ) -> bool:
        """Check if adding position would exceed max positions limit.

        Args:
            decision: Trading decision
            portfolio: Current portfolio state

        Returns:
            True if within limits, False otherwise
        """
        # If selling existing position, it's allowed
        if decision.action == "sell" and decision.symbol in portfolio.positions:
            return True

        # If buying, check if we'd exceed max positions
        if decision.action == "buy":
            current_positions = len(
                [v for v in portfolio.positions.values() if abs(v) > 0.01]
            )
            if current_positions >= self.max_positions:
                return False

        return True

    def _adjust_position_size(
        self,
        requested_size: float,
        action: str,
        portfolio: Portfolio,
        current_price: float,
    ) -> float:
        """Adjust position size based on risk limits.

        Args:
            requested_size: Requested position size as fraction of capital
            action: Trading action ('buy', 'sell')
            portfolio: Current portfolio state
            current_price: Current asset price

        Returns:
            Adjusted position size
        """
        # Start with requested size
        adjusted_size = requested_size

        # Apply max position size limit
        adjusted_size = min(adjusted_size, self.max_position_size)

        # Apply max exposure limit
        current_exposure = portfolio.get_total_exposure()
        remaining_exposure = max(0.0, self.max_total_exposure - current_exposure)
        adjusted_size = min(adjusted_size, remaining_exposure)

        # Ensure we have enough cash for buy orders
        if action == "buy":
            required_cash = adjusted_size * portfolio.capital
            available_cash = portfolio.cash
            if required_cash > available_cash:
                adjusted_size = available_cash / portfolio.capital

        # Floor at zero
        adjusted_size = max(0.0, adjusted_size)

        return adjusted_size

    def _reject_decision(
        self, original_decision: TradingDecision, reason: str
    ) -> TradingDecision:
        """Create a rejected (hold) decision.

        Args:
            original_decision: Original trading decision
            reason: Reason for rejection

        Returns:
            Hold decision with rejection reason
        """
        return TradingDecision(
            action="hold",
            symbol=original_decision.symbol,
            size=0.0,
            confidence=0.0,
            rationale=f"Trade rejected: {reason}. Original: {original_decision.rationale}",
            metadata={
                **(original_decision.metadata or {}),
                "rejected": True,
                "rejection_reason": reason,
            },
        )

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracker.

        Args:
            pnl: P&L to add
        """
        self.daily_pnl += pnl

    def reset_daily_pnl(self):
        """Reset daily P&L tracker (call at start of new day)."""
        self.daily_pnl = 0.0

    def record_trade(self):
        """Record that a trade was executed."""
        self.trade_count += 1

    def get_stats(self) -> Dict:
        """Get risk management statistics.

        Returns:
            Dictionary with risk stats
        """
        return {
            "trade_count": self.trade_count,
            "rejected_trades": self.rejected_trades,
            "rejection_rate": (
                self.rejected_trades / (self.trade_count + self.rejected_trades)
                if (self.trade_count + self.rejected_trades) > 0
                else 0.0
            ),
            "daily_pnl": self.daily_pnl,
        }

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_stats()
        return (
            f"RiskManager(trades={stats['trade_count']}, "
            f"rejected={stats['rejected_trades']}, "
            f"daily_pnl={stats['daily_pnl']:.2f})"
        )
