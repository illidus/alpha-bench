"""Tests for feature engineering module."""

import pytest
import pandas as pd
import numpy as np

from alpha_bench.data.features import FeatureEngineer, create_feature_matrix


class TestFeatureEngineer:
    """Tests for FeatureEngineer class."""

    def test_init(self):
        """Test FeatureEngineer initialization."""
        engineer = FeatureEngineer()
        assert engineer is not None
        assert isinstance(engineer.feature_config, dict)

    def test_generate_features_basic(self, mock_ohlcv_data):
        """Test basic feature generation."""
        engineer = FeatureEngineer()
        feature_list = ["price", "ema_12", "rsi_14"]

        features = engineer.generate_features(mock_ohlcv_data, feature_list)

        assert not features.empty
        assert "price" in features.columns
        assert "ema_12" in features.columns
        assert "rsi_14" in features.columns

    def test_generate_features_all(self, mock_ohlcv_data):
        """Test generating all available features."""
        engineer = FeatureEngineer()

        # Generate all features
        features = engineer.generate_features(mock_ohlcv_data, feature_list=None)

        assert not features.empty
        # Should have many features
        assert len(features.columns) > 10

    def test_ema_calculation(self, mock_ohlcv_data):
        """Test EMA calculation."""
        engineer = FeatureEngineer()

        ema_12 = engineer._ema(mock_ohlcv_data["close"], 12)

        assert len(ema_12) == len(mock_ohlcv_data)
        assert not ema_12.isna().all()
        # EMA should be close to actual prices
        assert ema_12.mean() == pytest.approx(
            mock_ohlcv_data["close"].mean(), rel=0.1
        )

    def test_rsi_calculation(self, mock_ohlcv_data):
        """Test RSI calculation."""
        engineer = FeatureEngineer()

        rsi = engineer._rsi(mock_ohlcv_data["close"], 14)

        assert len(rsi) == len(mock_ohlcv_data)
        # RSI should be between 0 and 100
        assert (rsi[~rsi.isna()] >= 0).all()
        assert (rsi[~rsi.isna()] <= 100).all()

    def test_macd_calculation(self, mock_ohlcv_data):
        """Test MACD calculation."""
        engineer = FeatureEngineer()

        macd_df = engineer._macd(mock_ohlcv_data["close"])

        assert "macd" in macd_df.columns
        assert "signal" in macd_df.columns
        assert "histogram" in macd_df.columns
        assert len(macd_df) == len(mock_ohlcv_data)

    def test_empty_data_raises_error(self):
        """Test that empty data raises error."""
        engineer = FeatureEngineer()

        with pytest.raises(ValueError, match="empty"):
            engineer.generate_features(pd.DataFrame())

    def test_missing_columns_raises_error(self):
        """Test that missing required columns raises error."""
        engineer = FeatureEngineer()

        incomplete_data = pd.DataFrame({"close": [1, 2, 3]})

        with pytest.raises(ValueError, match="Missing required columns"):
            engineer.generate_features(incomplete_data)

    def test_get_available_features(self):
        """Test getting list of available features."""
        features = FeatureEngineer.get_available_features()

        assert isinstance(features, list)
        assert len(features) > 0
        assert "price" in features
        assert "ema_12" in features
        assert "rsi_14" in features


class TestCreateFeatureMatrix:
    """Tests for create_feature_matrix function."""

    def test_create_feature_matrix(self, mock_features):
        """Test creating feature matrix."""
        selected_features = ["price", "ema_12", "rsi_14"]

        matrix = create_feature_matrix(mock_features, selected_features)

        assert len(matrix.columns) == len(selected_features)
        assert all(col in matrix.columns for col in selected_features)

    def test_missing_feature_raises_error(self, mock_features):
        """Test that missing features raise error."""
        selected_features = ["price", "nonexistent_feature"]

        with pytest.raises(ValueError, match="Missing features"):
            create_feature_matrix(mock_features, selected_features)
