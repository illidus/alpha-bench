"""Tests for baseline models."""

import pytest

from alpha_bench.models.baseline import RandomBaselineModel, TrendFollowingModel
from alpha_bench.models.base import TradingDecision


class TestRandomBaselineModel:
    """Tests for RandomBaselineModel."""

    def test_init(self, mock_model_config):
        """Test initialization."""
        config = {**mock_model_config, "strategy": "random"}
        model = RandomBaselineModel("test-random", config)

        assert model.model_id == "test-random"
        assert model.strategy == "random"
        assert model.position_size > 0

    def test_generate_decision(self, mock_model_config, mock_features):
        """Test generating random decision."""
        config = {**mock_model_config, "strategy": "random"}
        model = RandomBaselineModel("test-random", config)

        context = {"symbol": "BTC/USD", "capital": 10000.0}
        decision = model.generate_decision(mock_features, context)

        assert isinstance(decision, TradingDecision)
        assert decision.action in ["buy", "sell", "hold"]
        assert decision.symbol == "BTC/USD"
        assert 0 <= decision.confidence <= 1

    def test_multiple_decisions_vary(self, mock_model_config, mock_features):
        """Test that random decisions vary."""
        config = {**mock_model_config, "strategy": "random"}
        model = RandomBaselineModel("test-random", config)

        context = {"symbol": "BTC/USD", "capital": 10000.0}

        # Generate multiple decisions
        actions = [
            model.generate_decision(mock_features, context).action for _ in range(20)
        ]

        # Should have some variety (not all the same)
        assert len(set(actions)) > 1


class TestTrendFollowingModel:
    """Tests for TrendFollowingModel."""

    def test_init(self, mock_model_config):
        """Test initialization."""
        config = {**mock_model_config, "strategy": "ema_crossover"}
        model = TrendFollowingModel("test-trend", config)

        assert model.model_id == "test-trend"
        assert model.strategy == "ema_crossover"
        assert model.fast_ema == 12
        assert model.slow_ema == 26

    def test_generate_decision_bullish(self, mock_model_config, mock_features):
        """Test bullish crossover generates buy signal."""
        config = {**mock_model_config, "strategy": "ema_crossover"}
        model = TrendFollowingModel("test-trend", config)

        # Modify features to ensure bullish crossover
        mock_features["ema_12"] = 50500  # Fast EMA higher
        mock_features["ema_26"] = 50000  # Slow EMA lower

        context = {"symbol": "BTC/USD", "capital": 10000.0}
        decision = model.generate_decision(mock_features, context)

        assert isinstance(decision, TradingDecision)
        assert decision.action == "buy"
        assert decision.confidence > 0.5

    def test_generate_decision_bearish(self, mock_model_config, mock_features):
        """Test bearish crossover generates sell signal."""
        config = {**mock_model_config, "strategy": "ema_crossover"}
        model = TrendFollowingModel("test-trend", config)

        # Modify features to ensure bearish crossover
        mock_features["ema_12"] = 50000  # Fast EMA lower
        mock_features["ema_26"] = 50500  # Slow EMA higher

        context = {"symbol": "BTC/USD", "capital": 10000.0}
        decision = model.generate_decision(mock_features, context)

        assert isinstance(decision, TradingDecision)
        assert decision.action == "sell"
        assert decision.confidence > 0.5

    def test_missing_ema_returns_hold(self, mock_model_config):
        """Test that missing EMA features returns hold."""
        config = {**mock_model_config, "strategy": "ema_crossover"}
        model = TrendFollowingModel("test-trend", config)

        # Features without EMA columns
        import pandas as pd

        incomplete_features = pd.DataFrame({"price": [50000, 50100, 50050]})

        context = {"symbol": "BTC/USD", "capital": 10000.0}
        decision = model.generate_decision(incomplete_features, context)

        assert decision.action == "hold"
