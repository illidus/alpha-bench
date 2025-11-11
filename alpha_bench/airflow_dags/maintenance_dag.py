"""Maintenance DAG for alpha-bench.

This DAG handles data cleanup, archival, and system maintenance tasks.
Runs daily to keep the system clean and performant.

Schedule: Daily at 2 AM UTC (0 2 * * *)
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)


# Default arguments
default_args = {
    "owner": "alpha-bench",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def archive_old_results(**context):
    """Archive results older than 90 days to cold storage.

    Args:
        **context: Airflow context
    """
    from alpha_bench.config import Config

    logger.info("Starting results archival")

    config = Config.load()
    results_dir = config.project_root / "results"
    archive_dir = results_dir / "archive"
    archive_dir.mkdir(exist_ok=True)

    # Calculate cutoff date (90 days ago)
    cutoff_date = datetime.utcnow() - timedelta(days=90)

    archived_count = 0
    for run_dir in results_dir.iterdir():
        if not run_dir.is_dir() or run_dir.name == "archive":
            continue

        # Try to parse directory name as date
        try:
            # Format: 2025-11-10T12:00:00Z or similar
            run_date_str = run_dir.name.split("T")[0]
            run_date = datetime.strptime(run_date_str, "%Y-%m-%d")

            if run_date < cutoff_date:
                # Archive this directory
                archive_path = archive_dir / run_dir.name
                logger.info(f"Archiving {run_dir.name}")
                shutil.move(str(run_dir), str(archive_path))
                archived_count += 1

        except (ValueError, IndexError) as e:
            logger.debug(f"Skipping {run_dir.name}: not a dated directory")

    logger.info(f"Archived {archived_count} old result directories")


def cleanup_cache(**context):
    """Clean up expired cache entries and compress large caches.

    Args:
        **context: Airflow context
    """
    from alpha_bench.data.cache import DataCache

    logger.info("Starting cache maintenance")

    cache = DataCache()

    # Clear expired entries
    expired_count = cache.clear_expired()

    # Get cache stats
    stats = cache.get_stats()

    logger.info(
        f"Cache maintenance complete: "
        f"Deleted {expired_count} expired files, "
        f"{stats['count']} files remaining, "
        f"{stats['size_mb']:.2f} MB total"
    )


def optimize_benchmarks_file(**context):
    """Optimize benchmarks.parquet file for query performance.

    Args:
        **context: Airflow context
    """
    from alpha_bench.config import Config
    import pandas as pd

    logger.info("Starting benchmarks file optimization")

    config = Config.load()
    benchmarks_file = config.project_root / "results" / "benchmarks.parquet"

    if not benchmarks_file.exists():
        logger.info("No benchmarks file to optimize")
        return

    # Read and re-write with optimal settings
    try:
        df = pd.read_parquet(benchmarks_file)
        initial_size = benchmarks_file.stat().st_size / (1024 * 1024)  # MB

        # Sort by timestamp for better compression
        df = df.sort_values("timestamp")

        # Write with optimal compression
        df.to_parquet(
            benchmarks_file,
            compression="snappy",
            index=False,
            engine="pyarrow",
        )

        final_size = benchmarks_file.stat().st_size / (1024 * 1024)  # MB

        logger.info(
            f"Optimized benchmarks file: "
            f"{len(df)} records, "
            f"size {initial_size:.2f} MB -> {final_size:.2f} MB"
        )

    except Exception as e:
        logger.error(f"Failed to optimize benchmarks file: {e}")


def cleanup_logs(**context):
    """Clean up old log files.

    Args:
        **context: Airflow context
    """
    from alpha_bench.config import Config

    logger.info("Starting log cleanup")

    config = Config.load()
    logs_dir = config.project_root / "logs"

    if not logs_dir.exists():
        logger.info("No logs directory found")
        return

    # Delete log files older than 30 days
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    deleted_count = 0

    for log_file in logs_dir.rglob("*.log"):
        if log_file.stat().st_mtime < cutoff_date.timestamp():
            log_file.unlink()
            deleted_count += 1

    logger.info(f"Deleted {deleted_count} old log files")


def health_check(**context):
    """Perform system health checks.

    Args:
        **context: Airflow context
    """
    from alpha_bench.config import Config

    logger.info("Running health checks")

    config = Config.load()
    errors = config.validate()

    if errors:
        logger.error(f"Configuration validation failed: {errors}")
        raise ValueError(f"Configuration errors: {errors}")

    # Check disk space
    results_dir = config.project_root / "results"
    if results_dir.exists():
        total, used, free = shutil.disk_usage(results_dir)
        free_pct = (free / total) * 100

        logger.info(f"Disk space: {free_pct:.1f}% free")

        if free_pct < 10:
            logger.warning(f"Low disk space: {free_pct:.1f}% free")

    logger.info("Health checks passed")


# Define the DAG
with DAG(
    dag_id="maintenance_pipeline",
    default_args=default_args,
    description="Daily maintenance tasks for alpha-bench",
    schedule_interval="0 2 * * *",  # Daily at 2 AM UTC
    start_date=datetime(2025, 11, 10),
    catchup=False,
    tags=["alpha-bench", "maintenance"],
) as dag:

    # Health check task (runs first)
    health_check_task = PythonOperator(
        task_id="health_check",
        python_callable=health_check,
        provide_context=True,
    )

    # Archive old results
    archive_task = PythonOperator(
        task_id="archive_old_results",
        python_callable=archive_old_results,
        provide_context=True,
    )

    # Cleanup cache
    cleanup_cache_task = PythonOperator(
        task_id="cleanup_cache",
        python_callable=cleanup_cache,
        provide_context=True,
    )

    # Optimize benchmarks file
    optimize_task = PythonOperator(
        task_id="optimize_benchmarks",
        python_callable=optimize_benchmarks_file,
        provide_context=True,
    )

    # Cleanup logs
    cleanup_logs_task = PythonOperator(
        task_id="cleanup_logs",
        python_callable=cleanup_logs,
        provide_context=True,
    )

    # Define task dependencies
    health_check_task >> [
        archive_task,
        cleanup_cache_task,
        optimize_task,
        cleanup_logs_task,
    ]
