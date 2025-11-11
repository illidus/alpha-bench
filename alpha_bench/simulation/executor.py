"""Order execution for alpha-bench.

This module handles order execution with realistic fees, slippage, and market impact
modeling for paper trading simulations.

Usage:
    from alpha_bench.simulation.executor import OrderExecutor

    executor = OrderExecutor(config)
    fill = executor.execute_order(order, current_price)
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Order representation.

    Attributes:
        symbol: Trading symbol
        action: 'buy' or 'sell'
        size: Order size in currency units
        order_type: 'market', 'limit', or 'stop'
        price: Limit/stop price (None for market orders)
        timestamp: Order creation timestamp
    """

    symbol: str
    action: str
    size: float
    order_type: str = "market"
    price: Optional[float] = None
    timestamp: Optional[str] = None


@dataclass
class Fill:
    """Order fill representation.

    Attributes:
        symbol: Trading symbol
        action: 'buy' or 'sell'
        size: Fill size in currency units
        price: Execution price
        fees: Total fees paid
        slippage: Slippage amount
        net_cost: Net cost including fees and slippage
        timestamp: Fill timestamp
    """

    symbol: str
    action: str
    size: float
    price: float
    fees: float
    slippage: float
    net_cost: float
    timestamp: str


class OrderExecutor:
    """Executes orders with realistic fees and slippage.

    Simulates market execution with configurable fee structure and
    slippage models.

    Attributes:
        config: Execution configuration from strategies.yaml
        order_count: Number of orders executed
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize order executor.

        Args:
            config: Execution configuration
        """
        self.config = config or {}

        # Fee structure
        self.maker_fee = self.config.get("maker_fee", 0.001)  # 0.1%
        self.taker_fee = self.config.get("taker_fee", 0.001)  # 0.1%

        # Slippage model
        slippage_config = self.config.get("slippage", {})
        self.slippage_enabled = slippage_config.get("enabled", True)
        self.slippage_model = slippage_config.get("model", "proportional")
        self.slippage_rate = slippage_config.get("proportional_rate", 0.0005)  # 0.05%
        self.min_slippage = slippage_config.get("min_slippage", 0.0001)
        self.max_slippage = slippage_config.get("max_slippage", 0.005)

        # State
        self.order_count = 0

        logger.info("Initialized order executor")

    def execute_order(
        self, order: Order, current_price: float, timestamp: str
    ) -> Fill:
        """Execute an order at current market price.

        Args:
            order: Order to execute
            current_price: Current market price
            timestamp: Execution timestamp

        Returns:
            Fill object with execution details
        """
        self.order_count += 1

        # Calculate slippage
        slippage_amount = self._calculate_slippage(
            order.size, current_price, order.action
        )

        # Calculate execution price
        if order.action == "buy":
            execution_price = current_price + slippage_amount
        else:  # sell
            execution_price = current_price - slippage_amount

        # Calculate fees
        fee_rate = self.taker_fee if order.order_type == "market" else self.maker_fee
        fees = order.size * fee_rate

        # Calculate net cost
        if order.action == "buy":
            net_cost = order.size + fees + (slippage_amount * order.size / current_price)
        else:  # sell
            net_cost = order.size - fees - (slippage_amount * order.size / current_price)

        # Create fill
        fill = Fill(
            symbol=order.symbol,
            action=order.action,
            size=order.size,
            price=execution_price,
            fees=fees,
            slippage=slippage_amount,
            net_cost=net_cost,
            timestamp=timestamp,
        )

        logger.debug(
            f"Executed {order.action} {order.symbol}: "
            f"size=${order.size:.2f}, price=${execution_price:.2f}, "
            f"fees=${fees:.2f}, slippage=${slippage_amount:.4f}"
        )

        return fill

    def _calculate_slippage(
        self, order_size: float, current_price: float, action: str
    ) -> float:
        """Calculate slippage based on order size and model.

        Args:
            order_size: Order size in currency units
            current_price: Current market price
            action: 'buy' or 'sell'

        Returns:
            Slippage amount in price units
        """
        if not self.slippage_enabled:
            return 0.0

        if self.slippage_model == "proportional":
            # Simple proportional slippage
            slippage = current_price * self.slippage_rate

        elif self.slippage_model == "fixed":
            # Fixed slippage regardless of size
            slippage = self.slippage_rate

        elif self.slippage_model == "volume_based":
            # Slippage increases with order size
            # Assume larger orders have more market impact
            size_fraction = min(order_size / 10000, 1.0)  # Normalize by $10k
            slippage = current_price * self.slippage_rate * (1 + size_fraction)

        else:
            logger.warning(f"Unknown slippage model: {self.slippage_model}")
            slippage = current_price * self.slippage_rate

        # Apply min/max bounds
        slippage = max(self.min_slippage, min(slippage, self.max_slippage))

        return slippage

    def create_order_from_decision(
        self,
        decision,
        portfolio_capital: float,
        timestamp: str,
    ) -> Optional[Order]:
        """Create an order from a trading decision.

        Args:
            decision: TradingDecision object
            portfolio_capital: Total portfolio capital
            timestamp: Current timestamp

        Returns:
            Order object or None if decision is hold
        """
        if decision.action == "hold":
            return None

        # Calculate order size in currency units
        order_size = decision.size * portfolio_capital

        # Validate order size
        if order_size < 10.0:  # Minimum $10 order
            logger.debug(f"Order size ${order_size:.2f} below minimum, skipping")
            return None

        order = Order(
            symbol=decision.symbol,
            action=decision.action,
            size=order_size,
            order_type="market",
            price=None,
            timestamp=timestamp,
        )

        return order

    def get_stats(self) -> Dict:
        """Get executor statistics.

        Returns:
            Dictionary with execution stats
        """
        return {
            "order_count": self.order_count,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee,
            "slippage_rate": self.slippage_rate,
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"OrderExecutor(orders={self.order_count}, fees={self.taker_fee:.2%})"
