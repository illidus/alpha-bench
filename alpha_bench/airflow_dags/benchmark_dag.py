"""Main benchmark DAG for alpha-bench.

This DAG runs automated recurring benchmarks every 6 hours for all enabled models.
It fetches latest market data, runs simulations, calculates metrics, and aggregates
results into the longitudinal benchmarks.parquet file.

Schedule: Every 6 hours (0 */6 * * *)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Configure logging
logger = logging.getLogger(__name__)


# Default arguments for the DAG
default_args = {
    "owner": "alpha-bench",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def fetch_market_data(**context):
    """Task: Fetch latest market data for configured symbols.

    Args:
        **context: Airflow context
    """
    from alpha_bench.config import Config
    from alpha_bench.data.cache import DataCache, create_cache_key
    from alpha_bench.data.loader import MarketDataLoader

    logger.info("Starting market data fetch task")

    # Load config
    config = Config.load()

    # Get symbols from config (or use defaults)
    symbols = ["BTC/USD", "ETH/USD"]  # TODO: Make this configurable

    # Initialize loader and cache
    loader = MarketDataLoader(provider="mock")  # Change to real provider in production
    cache = DataCache()

    # Calculate time range (last 72 hours)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=72)

    # Fetch data for each symbol
    fetched_data = {}
    for symbol in symbols:
        try:
            logger.info(f"Fetching data for {symbol}")
            data = loader.fetch_ohlcv(symbol, start_time, end_time)

            # Cache the data
            cache_key = create_cache_key(symbol, start_time, end_time)
            cache.put(cache_key, data, ttl=7 * 24 * 3600)  # 7 days

            fetched_data[symbol] = {
                "cache_key": cache_key,
                "rows": len(data),
            }

            logger.info(f"Fetched {len(data)} rows for {symbol}")

        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")

    # Store metadata in XCom
    context["ti"].xcom_push(key="market_data", value=fetched_data)
    context["ti"].xcom_push(key="start_time", value=start_time.isoformat())
    context["ti"].xcom_push(key="end_time", value=end_time.isoformat())

    logger.info(f"Market data fetch complete: {len(fetched_data)} symbols")


def run_benchmarks(**context):
    """Task: Run benchmarks for all enabled models.

    Args:
        **context: Airflow context
    """
    from alpha_bench.config import Config
    from alpha_bench.metrics.aggregator import ResultsAggregator
    from alpha_bench.metrics.calculator import MetricsCalculator
    from alpha_bench.models.registry import ModelRegistry
    from alpha_bench.simulation.engine import SimulationEngine

    logger.info("Starting benchmark runs")

    # Get market data info from previous task
    market_data = context["ti"].xcom_pull(key="market_data", task_ids="fetch_data")
    start_time = datetime.fromisoformat(
        context["ti"].xcom_pull(key="start_time", task_ids="fetch_data")
    )
    end_time = datetime.fromisoformat(
        context["ti"].xcom_pull(key="end_time", task_ids="fetch_data")
    )

    # Load config
    config = Config.load()

    # Load all enabled models
    registry = ModelRegistry(config)
    models = registry.load_all_enabled()

    logger.info(f"Running benchmarks for {len(models)} models")

    # Initialize calculators
    metrics_calculator = MetricsCalculator()
    aggregator = ResultsAggregator()

    # Run ID for this execution
    run_id = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Results directory
    results_dir = Path("results") / run_id

    # Run benchmark for each model
    results_summary = []
    for model_id, model in models.items():
        try:
            logger.info(f"Running benchmark for {model_id}")

            # Initialize simulation engine
            engine = SimulationEngine(model=model, config=config, initial_capital=10000.0)

            # Run simulation (default to BTC/USD for now)
            symbol = "BTC/USD"
            results = engine.run(
                symbol=symbol, start=start_time, end=end_time, timeframe="1h"
            )

            if results.get("error"):
                logger.error(f"Simulation failed for {model_id}")
                continue

            # Calculate metrics
            metrics = metrics_calculator.calculate_metrics(results)

            # Save results
            model_output_dir = results_dir / model_id
            engine.save_results(results, model_output_dir)

            # Add to aggregated benchmarks
            aggregator.add_result(
                run_id=run_id,
                model_id=model_id,
                metrics=metrics,
                metadata={
                    "symbol": symbol,
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
            )

            # Track summary
            results_summary.append(
                {
                    "model_id": model_id,
                    "return_pct": metrics["total_return_pct"],
                    "sharpe": metrics["sharpe_ratio"],
                    "trades": metrics["num_trades"],
                }
            )

            logger.info(
                f"Completed {model_id}: "
                f"Return={metrics['total_return_pct']:.2f}%, "
                f"Sharpe={metrics['sharpe_ratio']:.2f}"
            )

        except Exception as e:
            logger.error(f"Error running benchmark for {model_id}: {e}", exc_info=True)

    # Store summary in XCom
    context["ti"].xcom_push(key="results_summary", value=results_summary)

    logger.info(f"Benchmark runs complete: {len(results_summary)} successful")


def cleanup_expired_cache(**context):
    """Task: Clean up expired cache files.

    Args:
        **context: Airflow context
    """
    from alpha_bench.data.cache import DataCache

    logger.info("Starting cache cleanup")

    cache = DataCache()
    deleted_count = cache.clear_expired()

    logger.info(f"Cache cleanup complete: {deleted_count} expired files deleted")


def send_summary_notification(**context):
    """Task: Send summary notification (optional).

    Args:
        **context: Airflow context
    """
    results_summary = context["ti"].xcom_pull(
        key="results_summary", task_ids="run_benchmarks"
    )

    if not results_summary:
        logger.warning("No results to summarize")
        return

    # Log summary
    logger.info("=" * 60)
    logger.info("Benchmark Run Summary")
    logger.info("=" * 60)
    for result in results_summary:
        logger.info(
            f"  {result['model_id']}: "
            f"Return={result['return_pct']:.2f}%, "
            f"Sharpe={result['sharpe']:.2f}, "
            f"Trades={result['trades']}"
        )
    logger.info("=" * 60)

    # TODO: Send email/Slack notification if configured


# Define the DAG
with DAG(
    dag_id="benchmark_pipeline",
    default_args=default_args,
    description="Automated recurring benchmark pipeline for alpha-bench",
    schedule_interval="0 */6 * * *",  # Every 6 hours
    start_date=datetime(2025, 11, 10),
    catchup=False,
    tags=["alpha-bench", "benchmark", "trading"],
) as dag:

    # Task 1: Fetch market data
    fetch_data_task = PythonOperator(
        task_id="fetch_data",
        python_callable=fetch_market_data,
        provide_context=True,
    )

    # Task 2: Run benchmarks for all models
    run_benchmarks_task = PythonOperator(
        task_id="run_benchmarks",
        python_callable=run_benchmarks,
        provide_context=True,
    )

    # Task 3: Cleanup expired cache
    cleanup_cache_task = PythonOperator(
        task_id="cleanup_cache",
        python_callable=cleanup_expired_cache,
        provide_context=True,
    )

    # Task 4: Send summary notification
    notify_task = PythonOperator(
        task_id="send_notification",
        python_callable=send_summary_notification,
        provide_context=True,
        trigger_rule="all_done",  # Run even if previous tasks failed
    )

    # Define task dependencies
    fetch_data_task >> run_benchmarks_task >> cleanup_cache_task >> notify_task
