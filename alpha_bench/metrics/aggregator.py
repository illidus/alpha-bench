"""Results aggregator for alpha-bench.

This module handles aggregation of benchmark results across multiple runs and models,
maintaining the longitudinal benchmarks.parquet file.

Usage:
    from alpha_bench.metrics.aggregator import ResultsAggregator

    aggregator = ResultsAggregator()
    aggregator.add_result(run_id, model_id, metrics)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ResultsAggregator:
    """Aggregates benchmark results across runs and models.

    Maintains a master benchmarks.parquet file with all historical results.

    Attributes:
        results_dir: Directory for storing results
        benchmarks_file: Path to benchmarks.parquet
    """

    def __init__(self, results_dir: Optional[Path] = None):
        """Initialize results aggregator.

        Args:
            results_dir: Results directory (defaults to ./results/)
        """
        if results_dir is None:
            # Auto-detect project root
            from alpha_bench.config import Config

            config = Config.load()
            results_dir = config.project_root / "results"

        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.benchmarks_file = self.results_dir / "benchmarks.parquet"

        logger.info(f"Results aggregator initialized: {self.results_dir}")

    def add_result(
        self, run_id: str, model_id: str, metrics: Dict, metadata: Optional[Dict] = None
    ) -> None:
        """Add a new result to the benchmarks file.

        Args:
            run_id: Run identifier (e.g., '2025-11-10T12:00Z')
            model_id: Model identifier
            metrics: Metrics dictionary from MetricsCalculator
            metadata: Optional metadata (symbol, config, etc.)
        """
        # Create result record
        record = {
            "run_id": run_id,
            "model_id": model_id,
            "timestamp": datetime.utcnow().isoformat(),
            **metrics,
        }

        # Add metadata if provided
        if metadata:
            record.update(metadata)

        # Load existing benchmarks
        if self.benchmarks_file.exists():
            try:
                existing_df = pd.read_parquet(self.benchmarks_file)
            except Exception as e:
                logger.error(f"Error loading benchmarks file: {e}")
                existing_df = pd.DataFrame()
        else:
            existing_df = pd.DataFrame()

        # Append new result
        new_df = pd.DataFrame([record])
        combined_df = (
            pd.concat([existing_df, new_df], ignore_index=True)
            if not existing_df.empty
            else new_df
        )

        # Save back to file
        combined_df.to_parquet(self.benchmarks_file, compression="snappy", index=False)

        logger.info(
            f"Added result: run={run_id}, model={model_id}, "
            f"return={metrics.get('total_return_pct', 0):.2f}%"
        )

    def get_benchmarks(
        self,
        model_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Get benchmark results with optional filtering.

        Args:
            model_id: Filter by model ID
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)

        Returns:
            DataFrame with benchmark results
        """
        if not self.benchmarks_file.exists():
            logger.warning("Benchmarks file does not exist")
            return pd.DataFrame()

        df = pd.read_parquet(self.benchmarks_file)

        # Apply filters
        if model_id:
            df = df[df["model_id"] == model_id]

        if start_date:
            df = df[df["timestamp"] >= start_date]

        if end_date:
            df = df[df["timestamp"] <= end_date]

        return df

    def get_model_summary(self, model_id: str) -> Dict:
        """Get summary statistics for a model across all runs.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary with summary statistics
        """
        df = self.get_benchmarks(model_id=model_id)

        if df.empty:
            return {"model_id": model_id, "num_runs": 0}

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
        """Get leaderboard of top models by metric.

        Args:
            metric: Metric to rank by (default 'sharpe_ratio')
            top_n: Number of top models to return

        Returns:
            DataFrame with top models
        """
        df = self.get_benchmarks()

        if df.empty:
            return pd.DataFrame()

        # Group by model and calculate mean metric
        leaderboard = (
            df.groupby("model_id")[metric]
            .agg(["mean", "std", "count"])
            .sort_values("mean", ascending=False)
            .head(top_n)
        )

        return leaderboard

    def __repr__(self) -> str:
        """String representation."""
        if self.benchmarks_file.exists():
            df = pd.read_parquet(self.benchmarks_file)
            num_results = len(df)
            num_models = df["model_id"].nunique()
        else:
            num_results = 0
            num_models = 0

        return (
            f"ResultsAggregator(results={num_results}, "
            f"models={num_models}, dir={self.results_dir})"
        )
