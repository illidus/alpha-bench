#!/usr/bin/env python
"""Manual benchmark runner for alpha-bench.

This script runs a single benchmark for a specified model and saves results.

Usage:
    python scripts/run_benchmark.py --model claude-code-numeric --lookback 72h --forecast 24h
    python scripts/run_benchmark.py --model all --symbol BTC/USD
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha_bench.config import Config
from alpha_bench.metrics.aggregator import ResultsAggregator
from alpha_bench.metrics.calculator import MetricsCalculator
from alpha_bench.models.registry import ModelRegistry
from alpha_bench.simulation.engine import SimulationEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run alpha-bench manual benchmark",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--model",
        type=str,
        default="claude-code-numeric",
        help="Model ID to benchmark (or 'all' for all enabled models)",
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default="BTC/USD",
        help="Trading symbol",
    )

    parser.add_argument(
        "--lookback",
        type=str,
        default="72h",
        help="Lookback period (e.g., '72h', '7d')",
    )

    parser.add_argument(
        "--forecast",
        type=str,
        default="24h",
        help="Forecast period (e.g., '24h', '1d')",
    )

    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10000.0,
        help="Initial capital in USD",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for results (auto-generated if not specified)",
    )

    return parser.parse_args()


def parse_time_delta(time_str: str) -> timedelta:
    """Parse time delta string (e.g., '72h', '7d') to timedelta.

    Args:
        time_str: Time string (e.g., '72h', '7d', '30m')

    Returns:
        timedelta object
    """
    import re

    match = re.match(r"(\d+)([hdm])", time_str.lower())
    if not match:
        raise ValueError(f"Invalid time format: {time_str}. Use format like '72h' or '7d'")

    value, unit = match.groups()
    value = int(value)

    if unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "m":
        return timedelta(minutes=value)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")


def run_benchmark(
    model_id: str,
    symbol: str,
    lookback: str,
    forecast: str,
    initial_capital: float,
    output_dir: Path,
) -> bool:
    """Run benchmark for a single model.

    Args:
        model_id: Model identifier
        symbol: Trading symbol
        lookback: Lookback period string
        forecast: Forecast period string
        initial_capital: Initial capital
        output_dir: Output directory

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Starting benchmark for model: {model_id}")

        # Load configuration
        config = Config.load()

        # Calculate time range
        end_time = datetime.utcnow()
        lookback_delta = parse_time_delta(lookback)
        start_time = end_time - lookback_delta

        logger.info(f"Time range: {start_time} to {end_time} (lookback: {lookback})")

        # Load model
        registry = ModelRegistry(config)
        model = registry.load_model(model_id)

        logger.info(f"Loaded model: {model}")

        # Initialize simulation engine
        engine = SimulationEngine(
            model=model, config=config, initial_capital=initial_capital
        )

        # Run simulation
        logger.info("Running simulation...")
        results = engine.run(symbol=symbol, start=start_time, end=end_time)

        if results.get("error"):
            logger.error(f"Simulation failed for {model_id}")
            return False

        # Calculate metrics
        logger.info("Calculating metrics...")
        calculator = MetricsCalculator()
        metrics = calculator.calculate_metrics(results)

        # Save results
        model_output_dir = output_dir / model_id
        engine.save_results(results, model_output_dir)

        # Add to aggregated benchmarks
        run_id = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        aggregator = ResultsAggregator()
        aggregator.add_result(
            run_id=run_id,
            model_id=model_id,
            metrics=metrics,
            metadata={
                "symbol": symbol,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "initial_capital": initial_capital,
            },
        )

        # Print summary
        logger.info("=" * 60)
        logger.info(f"Benchmark Results - {model_id}")
        logger.info("=" * 60)
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {start_time} to {end_time}")
        logger.info(f"Initial Capital: ${initial_capital:,.2f}")
        logger.info(f"Final Capital: ${metrics['final_capital']:,.2f}")
        logger.info(f"Total Return: {metrics['total_return_pct']:.2f}%")
        logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        logger.info(f"Sortino Ratio: {metrics['sortino_ratio']:.2f}")
        logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
        logger.info(f"Number of Trades: {metrics['num_trades']}")
        logger.info(f"Win Rate: {metrics['win_rate']:.2%}")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"Error running benchmark for {model_id}: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    args = parse_args()

    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
        output_dir = Path("results") / timestamp

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Determine which models to run
    if args.model.lower() == "all":
        config = Config.load()
        model_ids = [m.id for m in config.get_models(enabled_only=True)]
        logger.info(f"Running benchmarks for {len(model_ids)} enabled models")
    else:
        model_ids = [args.model]

    # Run benchmarks
    success_count = 0
    for model_id in model_ids:
        success = run_benchmark(
            model_id=model_id,
            symbol=args.symbol,
            lookback=args.lookback,
            forecast=args.forecast,
            initial_capital=args.initial_capital,
            output_dir=output_dir,
        )
        if success:
            success_count += 1

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info(f"Benchmark Summary")
    logger.info("=" * 60)
    logger.info(f"Total Models: {len(model_ids)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {len(model_ids) - success_count}")
    logger.info(f"Results saved to: {output_dir.absolute()}")
    logger.info("=" * 60)

    # Exit with error code if any failed
    sys.exit(0 if success_count == len(model_ids) else 1)


if __name__ == "__main__":
    main()
