"""Data queries for alpha-bench dashboard.

This module handles loading and filtering data for the Streamlit dashboard.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from alpha_bench.config import Config

logger = logging.getLogger(__name__)


class DashboardQueries:
    """Handles data queries for dashboard.

    Attributes:
        config: Configuration object
        benchmarks_file: Path to benchmarks.parquet
    """

    def __init__(self, config: Optional[Config] = None):
        """Initialize dashboard queries.

        Args:
            config: Config object (creates new if None)
        """
        self.config = config or Config.load()
        self.benchmarks_file = self.config.project_root / "results" / "benchmarks.parquet"

    def get_all_benchmarks(self) -> pd.DataFrame:
        """Get all benchmark results.

        Returns:
            DataFrame with all benchmark results
        """
        if not self.benchmarks_file.exists():
            logger.warning("Benchmarks file does not exist")
            return pd.DataFrame()

        try:
            df = pd.read_parquet(self.benchmarks_file)
            # Ensure timestamp is datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df
        except Exception as e:
            logger.error(f"Failed to load benchmarks: {e}")
            return pd.DataFrame()

    def get_model_benchmarks(self, model_id: str) -> pd.DataFrame:
        """Get benchmarks for a specific model.

        Args:
            model_id: Model identifier

        Returns:
            DataFrame filtered to model
        """
        df = self.get_all_benchmarks()
        if df.empty:
            return df
        return df[df["model_id"] == model_id]

    def get_recent_benchmarks(self, days: int = 7) -> pd.DataFrame:
        """Get recent benchmarks within specified days.

        Args:
            days: Number of days to look back

        Returns:
            DataFrame with recent benchmarks
        """
        df = self.get_all_benchmarks()
        if df.empty:
            return df

        cutoff = datetime.utcnow() - pd.Timedelta(days=days)
        return df[df["timestamp"] >= cutoff]

    def get_model_summary(self, model_id: str) -> dict:
        """Get summary statistics for a model.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary with summary stats
        """
        df = self.get_model_benchmarks(model_id)

        if df.empty:
            return {
                "model_id": model_id,
                "num_runs": 0,
                "avg_return": 0.0,
                "std_return": 0.0,
                "avg_sharpe": 0.0,
                "win_rate": 0.0,
            }

        return {
            "model_id": model_id,
            "num_runs": len(df),
            "avg_return": df["total_return_pct"].mean(),
            "std_return": df["total_return_pct"].std(),
            "avg_sharpe": df["sharpe_ratio"].mean(),
            "avg_max_drawdown": df["max_drawdown"].mean(),
            "win_rate": (df["total_return"] > 0).sum() / len(df),
        }

    def get_leaderboard(
        self, metric: str = "sharpe_ratio", top_n: int = 10
    ) -> pd.DataFrame:
        """Get leaderboard of top models.

        Args:
            metric: Metric to rank by
            top_n: Number of top models

        Returns:
            DataFrame with leaderboard
        """
        df = self.get_all_benchmarks()

        if df.empty:
            return pd.DataFrame()

        leaderboard = (
            df.groupby("model_id")[metric]
            .agg(["mean", "std", "count"])
            .sort_values("mean", ascending=False)
            .head(top_n)
        )

        return leaderboard

    def get_run_details(self, run_id: str, model_id: str) -> Optional[dict]:
        """Get details for a specific run.

        Args:
            run_id: Run identifier
            model_id: Model identifier

        Returns:
            Dictionary with run details or None if not found
        """
        results_dir = self.config.project_root / "results" / run_id / model_id

        if not results_dir.exists():
            logger.warning(f"Run details not found: {run_id}/{model_id}")
            return None

        # Load run data
        details = {}

        # Load decisions
        decisions_file = results_dir / "decisions.parquet"
        if decisions_file.exists():
            details["decisions"] = pd.read_parquet(decisions_file)

        # Load fills
        fills_file = results_dir / "fills.parquet"
        if fills_file.exists():
            details["fills"] = pd.read_parquet(fills_file)

        # Load snapshots
        snapshots_file = results_dir / "snapshots.parquet"
        if snapshots_file.exists():
            details["snapshots"] = pd.read_parquet(snapshots_file)

        # Load summary
        summary_file = results_dir / "summary.parquet"
        if summary_file.exists():
            summary_df = pd.read_parquet(summary_file)
            if not summary_df.empty:
                details["summary"] = summary_df.iloc[0].to_dict()

        return details if details else None
