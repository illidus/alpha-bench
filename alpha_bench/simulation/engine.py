"""Simulation engine for alpha-bench.

This module implements the core paper trading simulation loop that orchestrates
data loading, model decisions, risk management, order execution, and result tracking.

Usage:
    from alpha_bench.simulation.engine import SimulationEngine

    engine = SimulationEngine(model, config)
    results = engine.run(start_time, end_time)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from alpha_bench.config import Config
from alpha_bench.data.features import FeatureEngineer
from alpha_bench.data.loader import MarketDataLoader
from alpha_bench.models.base import BaseTradingModel, TradingDecision
from alpha_bench.simulation.executor import OrderExecutor
from alpha_bench.simulation.risk import Portfolio, RiskManager

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Core simulation engine for paper trading.

    Runs a complete simulation including data loading, feature generation,
    model decisions, risk management, order execution, and performance tracking.

    Attributes:
        model: Trading model to simulate
        config: Configuration object
        initial_capital: Starting capital
        data_loader: Market data loader
        feature_engineer: Feature engineer
        risk_manager: Risk manager
        executor: Order executor
    """

    def __init__(
        self,
        model: BaseTradingModel,
        config: Optional[Config] = None,
        initial_capital: float = 10000.0,
    ):
        """Initialize simulation engine.

        Args:
            model: Trading model to simulate
            config: Config object (creates new if None)
            initial_capital: Starting capital in USD
        """
        self.model = model
        self.config = config or Config.load()
        self.initial_capital = initial_capital

        # Get strategy config
        strategy_config = self.config.get_strategies()

        # Initialize components
        self.data_loader = MarketDataLoader(provider="mock")  # Use mock for testing
        self.feature_engineer = FeatureEngineer()
        self.risk_manager = RiskManager(strategy_config.risk_management)
        self.executor = OrderExecutor(strategy_config.execution)

        # Initialize portfolio
        self.portfolio = Portfolio(
            capital=initial_capital,
            cash=initial_capital,
            positions={},
            equity_curve=[initial_capital],
            peak_equity=initial_capital,
        )

        # Results tracking
        self.decisions: List[Dict] = []
        self.fills: List[Dict] = []
        self.portfolio_snapshots: List[Dict] = []

        logger.info(
            f"Initialized simulation engine for model {model.model_id} "
            f"with ${initial_capital:,.2f} capital"
        )

    def run(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
    ) -> Dict[str, Any]:
        """Run complete simulation.

        Args:
            symbol: Trading symbol
            start: Start datetime
            end: End datetime
            timeframe: Data timeframe

        Returns:
            Dictionary with simulation results
        """
        logger.info(
            f"Starting simulation: {symbol} from {start} to {end} ({timeframe})"
        )

        # Load market data
        try:
            market_data = self.data_loader.fetch_ohlcv(symbol, start, end, timeframe)
        except Exception as e:
            logger.error(f"Failed to load market data: {e}")
            return self._empty_results()

        if market_data.empty:
            logger.error("No market data available")
            return self._empty_results()

        # Generate features
        try:
            feature_list = self.model.config.get("features", [])
            features = self.feature_engineer.generate_features(
                market_data, feature_list
            )
        except Exception as e:
            logger.error(f"Failed to generate features: {e}")
            return self._empty_results()

        # Run simulation loop
        logger.info(f"Running simulation with {len(features)} data points")

        for i in range(len(features)):
            timestamp = features.index[i].isoformat()
            current_price = features.iloc[i]["close"]

            # Get historical features up to current point
            historical_features = features.iloc[: i + 1]

            # Create context
            context = {
                "symbol": symbol,
                "capital": self.portfolio.capital,
                "cash": self.portfolio.cash,
                "positions": self.portfolio.positions.copy(),
                "timestamp": timestamp,
                "current_price": current_price,
            }

            # Generate trading decision
            try:
                decision = self.model.generate_decision(historical_features, context)
            except Exception as e:
                logger.error(f"Model decision failed at {timestamp}: {e}")
                decision = TradingDecision(
                    action="hold",
                    symbol=symbol,
                    size=0.0,
                    confidence=0.0,
                    rationale=f"Error: {e}",
                )

            # Record decision
            self.decisions.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "action": decision.action,
                    "size": decision.size,
                    "confidence": decision.confidence,
                    "rationale": decision.rationale,
                    "price": current_price,
                }
            )

            # Apply risk management
            adjusted_decision = self.risk_manager.apply_risk_limits(
                decision, self.portfolio, current_price
            )

            # Execute order if not hold
            if adjusted_decision.action != "hold":
                self._execute_trade(adjusted_decision, current_price, timestamp)

            # Update portfolio value
            self._update_portfolio_value(symbol, current_price)

            # Record portfolio snapshot
            if i % 10 == 0:  # Every 10 periods
                self._record_snapshot(timestamp)

        # Final snapshot
        self._record_snapshot(features.index[-1].isoformat())

        # Compile results
        results = self._compile_results(symbol, start, end)

        logger.info(
            f"Simulation complete: Final capital=${self.portfolio.capital:,.2f}, "
            f"Return={(self.portfolio.capital / self.initial_capital - 1) * 100:.2f}%"
        )

        return results

    def _execute_trade(
        self, decision: TradingDecision, current_price: float, timestamp: str
    ):
        """Execute a trade based on decision.

        Args:
            decision: Trading decision
            current_price: Current market price
            timestamp: Current timestamp
        """
        # Create order
        order = self.executor.create_order_from_decision(
            decision, self.portfolio.capital, timestamp
        )

        if order is None:
            return

        # Execute order
        fill = self.executor.execute_order(order, current_price, timestamp)

        # Update portfolio
        if fill.action == "buy":
            # Deduct cash
            self.portfolio.cash -= fill.net_cost
            # Add position
            if fill.symbol in self.portfolio.positions:
                self.portfolio.positions[fill.symbol] += fill.size
            else:
                self.portfolio.positions[fill.symbol] = fill.size

        elif fill.action == "sell":
            # Add cash
            self.portfolio.cash += fill.net_cost
            # Reduce position
            if fill.symbol in self.portfolio.positions:
                self.portfolio.positions[fill.symbol] -= fill.size
                # Remove position if near zero
                if abs(self.portfolio.positions[fill.symbol]) < 0.01:
                    del self.portfolio.positions[fill.symbol]

        # Record fill
        self.fills.append(
            {
                "timestamp": timestamp,
                "symbol": fill.symbol,
                "action": fill.action,
                "size": fill.size,
                "price": fill.price,
                "fees": fill.fees,
                "slippage": fill.slippage,
                "net_cost": fill.net_cost,
            }
        )

        # Update risk manager
        self.risk_manager.record_trade()

        logger.debug(
            f"Trade executed: {fill.action} {fill.symbol} "
            f"${fill.size:.2f} @ ${fill.price:.2f}"
        )

    def _update_portfolio_value(self, symbol: str, current_price: float):
        """Update portfolio capital based on current prices.

        Args:
            symbol: Trading symbol
            current_price: Current market price
        """
        # Calculate total position value at current prices
        # For simplicity, assume all positions are in the same symbol
        position_value = self.portfolio.positions.get(symbol, 0.0)

        # Total capital = cash + position value
        self.portfolio.capital = self.portfolio.cash + position_value

        # Update peak equity
        if self.portfolio.capital > self.portfolio.peak_equity:
            self.portfolio.peak_equity = self.portfolio.capital

        # Update equity curve
        self.portfolio.equity_curve.append(self.portfolio.capital)

    def _record_snapshot(self, timestamp: str):
        """Record portfolio snapshot.

        Args:
            timestamp: Current timestamp
        """
        self.portfolio_snapshots.append(
            {
                "timestamp": timestamp,
                "capital": self.portfolio.capital,
                "cash": self.portfolio.cash,
                "positions": self.portfolio.positions.copy(),
                "drawdown": self.portfolio.get_drawdown(),
            }
        )

    def _compile_results(
        self, symbol: str, start: datetime, end: datetime
    ) -> Dict[str, Any]:
        """Compile simulation results.

        Args:
            symbol: Trading symbol
            start: Start datetime
            end: End datetime

        Returns:
            Dictionary with all simulation results
        """
        return {
            "model_id": self.model.model_id,
            "symbol": symbol,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "initial_capital": self.initial_capital,
            "final_capital": self.portfolio.capital,
            "total_return": (self.portfolio.capital / self.initial_capital) - 1,
            "total_return_pct": (
                (self.portfolio.capital / self.initial_capital) - 1
            )
            * 100,
            "peak_equity": self.portfolio.peak_equity,
            "max_drawdown": max(
                [s["drawdown"] for s in self.portfolio_snapshots], default=0.0
            ),
            "num_decisions": len(self.decisions),
            "num_trades": len(self.fills),
            "decisions": pd.DataFrame(self.decisions),
            "fills": pd.DataFrame(self.fills) if self.fills else pd.DataFrame(),
            "snapshots": pd.DataFrame(self.portfolio_snapshots),
            "equity_curve": self.portfolio.equity_curve,
            "risk_stats": self.risk_manager.get_stats(),
            "executor_stats": self.executor.get_stats(),
            "model_stats": self.model.get_stats(),
        }

    def _empty_results(self) -> Dict[str, Any]:
        """Create empty results dict for failed simulations.

        Returns:
            Empty results dictionary
        """
        return {
            "model_id": self.model.model_id,
            "error": True,
            "initial_capital": self.initial_capital,
            "final_capital": self.initial_capital,
            "total_return": 0.0,
            "decisions": pd.DataFrame(),
            "fills": pd.DataFrame(),
            "snapshots": pd.DataFrame(),
        }

    def save_results(self, results: Dict[str, Any], output_dir: Path):
        """Save simulation results to disk.

        Args:
            results: Results dictionary from run()
            output_dir: Directory to save results
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save decisions
        if not results["decisions"].empty:
            results["decisions"].to_parquet(
                output_dir / "decisions.parquet", compression="snappy"
            )

        # Save fills
        if not results["fills"].empty:
            results["fills"].to_parquet(
                output_dir / "fills.parquet", compression="snappy"
            )

        # Save snapshots
        if not results["snapshots"].empty:
            results["snapshots"].to_parquet(
                output_dir / "snapshots.parquet", compression="snappy"
            )

        # Save summary
        summary = {
            k: v
            for k, v in results.items()
            if k not in ["decisions", "fills", "snapshots", "equity_curve"]
        }
        summary_df = pd.DataFrame([summary])
        summary_df.to_parquet(output_dir / "summary.parquet", compression="snappy")

        logger.info(f"Saved results to {output_dir}")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SimulationEngine(model={self.model.model_id}, "
            f"capital=${self.portfolio.capital:,.2f})"
        )
