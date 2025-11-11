"""Pytest configuration and shared fixtures for alpha-bench tests.

This module provides fixtures for mock data, configurations, and test utilities.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path


@pytest.fixture
def mock_ohlcv_data():
    """Generate realistic mock OHLCV data for testing.

    Returns:
        DataFrame with OHLCV columns
    """
    # Generate 100 hourly data points
    timestamps = pd.date_range("2025-11-01", periods=100, freq="1H")

    # Generate random walk price
    np.random.seed(42)
    returns = np.random.normal(0.0001, 0.02, len(timestamps))
    price = 50000 * np.exp(np.cumsum(returns))

    data = pd.DataFrame(
        {
            "open": price * (1 + np.random.uniform(-0.005, 0.005, len(timestamps))),
            "high": price * (1 + np.random.uniform(0.001, 0.01, len(timestamps))),
            "low": price * (1 - np.random.uniform(0.001, 0.01, len(timestamps))),
            "close": price,
            "volume": np.random.uniform(100, 1000, len(timestamps)),
        },
        index=timestamps,
    )

    return data


@pytest.fixture
def mock_features():
    """Generate mock features DataFrame.

    Returns:
        DataFrame with feature columns
    """
    timestamps = pd.date_range("2025-11-01", periods=50, freq="1H")

    data = pd.DataFrame(
        {
            "price": np.random.uniform(49000, 51000, len(timestamps)),
            "ema_12": np.random.uniform(49500, 50500, len(timestamps)),
            "ema_26": np.random.uniform(49500, 50500, len(timestamps)),
            "macd": np.random.uniform(-100, 100, len(timestamps)),
            "macd_signal": np.random.uniform(-100, 100, len(timestamps)),
            "macd_hist": np.random.uniform(-50, 50, len(timestamps)),
            "rsi_14": np.random.uniform(30, 70, len(timestamps)),
            "volume": np.random.uniform(100, 1000, len(timestamps)),
            "volume_sma_20": np.random.uniform(400, 600, len(timestamps)),
        },
        index=timestamps,
    )

    return data


@pytest.fixture
def mock_model_config():
    """Generate mock model configuration.

    Returns:
        Dictionary with model config
    """
    return {
        "id": "test-model",
        "description": "Test model for unit tests",
        "provider": "baseline",
        "strategy": "random",
        "system_prompt": "sys_numeric.txt",
        "features": ["price", "ema_12", "ema_26", "rsi_14"],
        "schedule": "6h",
        "risk_cap": 0.01,
        "temperature": 0.2,
        "enabled": True,
    }


@pytest.fixture
def mock_trading_decision():
    """Generate mock trading decision.

    Returns:
        TradingDecision object
    """
    from alpha_bench.models.base import TradingDecision

    return TradingDecision(
        action="buy",
        symbol="BTC/USD",
        size=0.01,
        confidence=0.75,
        rationale="Test decision for unit testing",
        metadata={"test": True},
    )


@pytest.fixture
def mock_portfolio():
    """Generate mock portfolio.

    Returns:
        Portfolio object
    """
    from alpha_bench.simulation.risk import Portfolio

    return Portfolio(
        capital=10000.0,
        cash=8000.0,
        positions={"BTC/USD": 2000.0},
        equity_curve=[10000.0, 10100.0, 10050.0],
        peak_equity=10100.0,
    )


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create temporary project directory structure.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path to temporary project directory
    """
    project_dir = tmp_path / "alpha-bench"
    project_dir.mkdir()

    # Create subdirectories
    (project_dir / "configs").mkdir()
    (project_dir / "prompts").mkdir()
    (project_dir / "data" / "cache").mkdir(parents=True)
    (project_dir / "results").mkdir()

    # Create minimal config files
    models_yaml = """
models:
  - id: test-model
    description: Test model
    provider: baseline
    strategy: random
    system_prompt: sys_test.txt
    features: [price]
    schedule: 6h
    risk_cap: 0.01
    enabled: true
"""
    (project_dir / "configs" / "models.yaml").write_text(models_yaml)

    strategies_yaml = """
position_sizing:
  default_method: fixed_fractional
  fixed_fractional:
    risk_fraction: 0.01
    max_position_size: 0.25

risk_management:
  max_total_exposure: 1.0
  max_drawdown: 0.20

execution:
  slippage:
    enabled: true
    model: proportional
    proportional_rate: 0.0005
  fees:
    maker_fee: 0.001
    taker_fee: 0.001
"""
    (project_dir / "configs" / "strategies.yaml").write_text(strategies_yaml)

    # Create test prompt
    (project_dir / "prompts" / "sys_test.txt").write_text("Test system prompt")

    return project_dir
