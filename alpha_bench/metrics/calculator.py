"""Performance metrics calculator for alpha-bench.

This module calculates trading performance metrics including returns, risk-adjusted
metrics (Sharpe, Sortino, Calmar), drawdown analysis, and trading statistics.

Usage:
    from alpha_bench.metrics.calculator import MetricsCalculator

    calculator = MetricsCalculator()
    metrics = calculator.calculate_metrics(results)
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates performance metrics from simulation results.

    Attributes:
        risk_free_rate: Annual risk-free rate for Sharpe/Sortino
        trading_days_per_year: Number of trading days for annualization
    """

    def __init__(
        self, risk_free_rate: float = 0.04, trading_days_per_year: int = 252
    ):
        """Initialize metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 4%)
            trading_days_per_year: Trading days per year (default 252)
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year

    def calculate_metrics(self, results: Dict) -> Dict:
        """Calculate comprehensive performance metrics from simulation results.

        Args:
            results: Results dictionary from SimulationEngine.run()

        Returns:
            Dictionary with calculated metrics
        """
        metrics = {}

        # Basic metrics
        metrics["initial_capital"] = results.get("initial_capital", 0.0)
        metrics["final_capital"] = results.get("final_capital", 0.0)
        metrics["total_return"] = results.get("total_return", 0.0)
        metrics["total_return_pct"] = results.get("total_return_pct", 0.0)

        # Get equity curve
        equity_curve = results.get("equity_curve", [])
        if not equity_curve or len(equity_curve) < 2:
            logger.warning("Insufficient data for metrics calculation")
            return self._default_metrics(metrics)

        # Calculate returns series
        returns = pd.Series(equity_curve).pct_change().dropna()

        # Returns metrics
        metrics["mean_return"] = returns.mean()
        metrics["std_return"] = returns.std()
        metrics["annualized_return"] = self._annualize_return(returns)
        metrics["annualized_volatility"] = self._annualize_volatility(returns)

        # Risk-adjusted metrics
        metrics["sharpe_ratio"] = self._sharpe_ratio(returns)
        metrics["sortino_ratio"] = self._sortino_ratio(returns)

        # Drawdown metrics
        drawdown_metrics = self._calculate_drawdown_metrics(equity_curve)
        metrics.update(drawdown_metrics)

        # Calmar ratio (return / max drawdown)
        if metrics["max_drawdown"] > 0:
            metrics["calmar_ratio"] = (
                metrics["annualized_return"] / metrics["max_drawdown"]
            )
        else:
            metrics["calmar_ratio"] = 0.0

        # Trading metrics
        trading_metrics = self._calculate_trading_metrics(results)
        metrics.update(trading_metrics)

        logger.debug(f"Calculated metrics: Sharpe={metrics['sharpe_ratio']:.2f}")

        return metrics

    def _annualize_return(self, returns: pd.Series) -> float:
        """Annualize returns.

        Args:
            returns: Returns series

        Returns:
            Annualized return
        """
        if len(returns) == 0:
            return 0.0

        cumulative_return = (1 + returns).prod() - 1
        n_periods = len(returns)
        annualization_factor = self.trading_days_per_year / n_periods

        annualized = (1 + cumulative_return) ** annualization_factor - 1
        return annualized

    def _annualize_volatility(self, returns: pd.Series) -> float:
        """Annualize volatility.

        Args:
            returns: Returns series

        Returns:
            Annualized volatility
        """
        if len(returns) == 0:
            return 0.0

        return returns.std() * np.sqrt(self.trading_days_per_year)

    def _sharpe_ratio(self, returns: pd.Series) -> float:
        """Calculate Sharpe ratio.

        Args:
            returns: Returns series

        Returns:
            Sharpe ratio
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0.0

        # Adjust risk-free rate to period
        risk_free_per_period = self.risk_free_rate / self.trading_days_per_year

        excess_returns = returns - risk_free_per_period
        sharpe = excess_returns.mean() / returns.std()

        # Annualize
        sharpe_annualized = sharpe * np.sqrt(self.trading_days_per_year)

        return sharpe_annualized

    def _sortino_ratio(self, returns: pd.Series) -> float:
        """Calculate Sortino ratio (downside deviation version of Sharpe).

        Args:
            returns: Returns series

        Returns:
            Sortino ratio
        """
        if len(returns) == 0:
            return 0.0

        # Adjust risk-free rate to period
        risk_free_per_period = self.risk_free_rate / self.trading_days_per_year

        excess_returns = returns - risk_free_per_period

        # Calculate downside deviation (only negative returns)
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) == 0:
            return 0.0

        downside_std = downside_returns.std()
        if downside_std == 0:
            return 0.0

        sortino = excess_returns.mean() / downside_std

        # Annualize
        sortino_annualized = sortino * np.sqrt(self.trading_days_per_year)

        return sortino_annualized

    def _calculate_drawdown_metrics(self, equity_curve: List[float]) -> Dict:
        """Calculate drawdown metrics.

        Args:
            equity_curve: List of equity values over time

        Returns:
            Dictionary with drawdown metrics
        """
        if not equity_curve or len(equity_curve) < 2:
            return {
                "max_drawdown": 0.0,
                "max_drawdown_duration": 0,
                "current_drawdown": 0.0,
            }

        equity_series = pd.Series(equity_curve)

        # Calculate running maximum
        running_max = equity_series.expanding().max()

        # Calculate drawdown series
        drawdown = (equity_series - running_max) / running_max

        # Max drawdown
        max_drawdown = abs(drawdown.min())

        # Max drawdown duration (periods in drawdown)
        in_drawdown = drawdown < 0
        drawdown_periods = []
        current_duration = 0

        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    drawdown_periods.append(current_duration)
                current_duration = 0

        if current_duration > 0:
            drawdown_periods.append(current_duration)

        max_drawdown_duration = max(drawdown_periods) if drawdown_periods else 0

        # Current drawdown
        current_drawdown = abs(drawdown.iloc[-1])

        return {
            "max_drawdown": max_drawdown,
            "max_drawdown_duration": max_drawdown_duration,
            "current_drawdown": current_drawdown,
        }

    def _calculate_trading_metrics(self, results: Dict) -> Dict:
        """Calculate trading activity metrics.

        Args:
            results: Results dictionary

        Returns:
            Dictionary with trading metrics
        """
        fills = results.get("fills", pd.DataFrame())

        if fills.empty:
            return {
                "num_trades": 0,
                "num_buys": 0,
                "num_sells": 0,
                "total_fees": 0.0,
                "total_slippage": 0.0,
                "avg_trade_size": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
            }

        num_trades = len(fills)
        num_buys = len(fills[fills["action"] == "buy"])
        num_sells = len(fills[fills["action"] == "sell"])

        total_fees = fills["fees"].sum()
        total_slippage = fills["slippage"].sum()
        avg_trade_size = fills["size"].mean()

        # Win rate and profit factor (simplified)
        # For proper calculation, would need to match buy/sell pairs
        if num_sells > 0:
            # Approximate: compare sell prices to average buy price
            buys = fills[fills["action"] == "buy"]
            sells = fills[fills["action"] == "sell"]

            if not buys.empty:
                avg_buy_price = buys["price"].mean()
                winning_sells = sells[sells["price"] > avg_buy_price]
                win_rate = len(winning_sells) / len(sells)

                profits = sells[sells["price"] > avg_buy_price]["net_cost"].sum()
                losses = abs(
                    sells[sells["price"] <= avg_buy_price]["net_cost"].sum()
                )

                if losses > 0:
                    profit_factor = profits / losses
                else:
                    profit_factor = profits if profits > 0 else 0.0
            else:
                win_rate = 0.0
                profit_factor = 0.0
        else:
            win_rate = 0.0
            profit_factor = 0.0

        return {
            "num_trades": num_trades,
            "num_buys": num_buys,
            "num_sells": num_sells,
            "total_fees": total_fees,
            "total_slippage": total_slippage,
            "avg_trade_size": avg_trade_size,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
        }

    def _default_metrics(self, base_metrics: Dict) -> Dict:
        """Create default metrics for failed calculations.

        Args:
            base_metrics: Base metrics to include

        Returns:
            Dictionary with default metrics
        """
        return {
            **base_metrics,
            "mean_return": 0.0,
            "std_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "current_drawdown": 0.0,
            "num_trades": 0,
            "num_buys": 0,
            "num_sells": 0,
            "total_fees": 0.0,
            "total_slippage": 0.0,
            "avg_trade_size": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MetricsCalculator(risk_free_rate={self.risk_free_rate:.2%}, "
            f"trading_days={self.trading_days_per_year})"
        )
