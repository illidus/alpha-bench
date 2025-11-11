"""Feature engineering for alpha-bench.

This module generates technical indicators and features from OHLCV market data.
Features include moving averages, momentum indicators, volatility measures, and
optional text sentiment features.

Usage:
    from alpha_bench.data.features import FeatureEngineer

    engineer = FeatureEngineer()
    features_df = engineer.generate_features(ohlcv_df)
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Generates technical features from OHLCV data.

    Supports a wide range of technical indicators including trend, momentum,
    volatility, and volume-based features.

    Attributes:
        feature_config: Configuration for feature generation
    """

    def __init__(self, feature_config: Optional[Dict] = None):
        """Initialize feature engineer.

        Args:
            feature_config: Feature configuration dictionary (from config.yaml)
        """
        self.feature_config = feature_config or {}

    def generate_features(
        self, data: pd.DataFrame, feature_list: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Generate features from OHLCV data.

        Args:
            data: DataFrame with OHLCV columns (open, high, low, close, volume)
            feature_list: List of features to generate (if None, generate all)

        Returns:
            DataFrame with original data plus generated features

        Raises:
            ValueError: If input data is invalid
        """
        if data.empty:
            raise ValueError("Cannot generate features from empty DataFrame")

        # Validate required columns
        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Copy data to avoid modifying original
        df = data.copy()

        # Determine which features to generate
        if feature_list is None:
            # Generate all available features
            feature_list = [
                "price",
                "ema_12",
                "ema_26",
                "sma_20",
                "sma_50",
                "macd",
                "macd_signal",
                "macd_hist",
                "rsi_14",
                "rsi_7",
                "rsi_28",
                "volume_sma_20",
                "volume_ratio",
                "atr_14",
                "bbands_upper",
                "bbands_middle",
                "bbands_lower",
                "returns",
                "log_returns",
                "volatility",
            ]

        logger.debug(f"Generating {len(feature_list)} features")

        # Generate features
        for feature in feature_list:
            try:
                if feature == "price":
                    df["price"] = df["close"]

                elif feature.startswith("ema_"):
                    period = int(feature.split("_")[1])
                    df[feature] = self._ema(df["close"], period)

                elif feature.startswith("sma_"):
                    period = int(feature.split("_")[1])
                    df[feature] = self._sma(df["close"], period)

                elif feature == "macd":
                    macd_df = self._macd(df["close"])
                    df["macd"] = macd_df["macd"]
                    df["macd_signal"] = macd_df["signal"]
                    df["macd_hist"] = macd_df["histogram"]

                elif feature.startswith("rsi_"):
                    period = int(feature.split("_")[1])
                    df[feature] = self._rsi(df["close"], period)

                elif feature.startswith("volume_sma_"):
                    period = int(feature.split("_")[2])
                    df[feature] = self._sma(df["volume"], period)

                elif feature == "volume_ratio":
                    volume_sma = self._sma(df["volume"], 20)
                    df["volume_ratio"] = df["volume"] / volume_sma

                elif feature.startswith("atr_"):
                    period = int(feature.split("_")[1])
                    df[feature] = self._atr(df, period)

                elif feature.startswith("bbands_"):
                    bbands = self._bollinger_bands(df["close"])
                    df["bbands_upper"] = bbands["upper"]
                    df["bbands_middle"] = bbands["middle"]
                    df["bbands_lower"] = bbands["lower"]

                elif feature == "returns":
                    df["returns"] = df["close"].pct_change()

                elif feature == "log_returns":
                    df["log_returns"] = np.log(df["close"] / df["close"].shift(1))

                elif feature == "volatility":
                    df["volatility"] = df["returns"].rolling(20).std()

                elif feature in ["sentiment_news", "sentiment_social"]:
                    # Placeholder for text features (requires external API)
                    logger.warning(f"Text feature {feature} not yet implemented")
                    df[feature] = 0.0

                else:
                    logger.warning(f"Unknown feature: {feature}")

            except Exception as e:
                logger.error(f"Error generating feature {feature}: {e}")
                df[feature] = np.nan

        # Drop rows with NaN (from indicators that need warmup period)
        initial_rows = len(df)
        df = df.dropna()
        dropped_rows = initial_rows - len(df)

        if dropped_rows > 0:
            logger.debug(f"Dropped {dropped_rows} rows with NaN values")

        logger.info(f"Generated {len(feature_list)} features, {len(df)} rows remaining")
        return df

    @staticmethod
    def _ema(series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average.

        Args:
            series: Price series
            period: EMA period

        Returns:
            EMA series
        """
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _sma(series: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average.

        Args:
            series: Price series
            period: SMA period

        Returns:
            SMA series
        """
        return series.rolling(window=period).mean()

    def _macd(
        self, series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """Calculate MACD (Moving Average Convergence Divergence).

        Args:
            series: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            DataFrame with macd, signal, and histogram columns
        """
        ema_fast = self._ema(series, fast)
        ema_slow = self._ema(series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        histogram = macd_line - signal_line

        return pd.DataFrame(
            {"macd": macd_line, "signal": signal_line, "histogram": histogram},
            index=series.index,
        )

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index.

        Args:
            series: Price series
            period: RSI period

        Returns:
            RSI series (0-100)
        """
        # Calculate price changes
        delta = series.diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)

        # Calculate average gains and losses
        avg_gains = gains.ewm(span=period, adjust=False).mean()
        avg_losses = losses.ewm(span=period, adjust=False).mean()

        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range.

        Args:
            data: DataFrame with high, low, close columns
            period: ATR period

        Returns:
            ATR series
        """
        high = data["high"]
        low = data["low"]
        close = data["close"]

        # Calculate True Range components
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        # True Range is the maximum of the three
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR is the EMA of True Range
        atr = self._ema(tr, period)

        return atr

    def _bollinger_bands(
        self, series: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> pd.DataFrame:
        """Calculate Bollinger Bands.

        Args:
            series: Price series
            period: Moving average period
            std_dev: Number of standard deviations

        Returns:
            DataFrame with upper, middle, lower bands
        """
        middle = self._sma(series, period)
        std = series.rolling(window=period).std()

        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        return pd.DataFrame(
            {"upper": upper, "middle": middle, "lower": lower}, index=series.index
        )

    def generate_and_save(
        self,
        data: pd.DataFrame,
        output_path: str,
        feature_list: Optional[List[str]] = None,
    ) -> None:
        """Generate features and save to Parquet file.

        Args:
            data: Input OHLCV DataFrame
            output_path: Path to save features
            feature_list: List of features to generate
        """
        features = self.generate_features(data, feature_list)
        features.to_parquet(output_path, compression="snappy")
        logger.info(f"Saved {len(features)} rows to {output_path}")

    @staticmethod
    def get_available_features() -> List[str]:
        """Get list of all available feature names.

        Returns:
            List of feature names
        """
        return [
            "price",
            "ema_12",
            "ema_26",
            "sma_20",
            "sma_50",
            "macd",
            "macd_signal",
            "macd_hist",
            "rsi_14",
            "rsi_7",
            "rsi_28",
            "volume_sma_20",
            "volume_ratio",
            "atr_14",
            "bbands_upper",
            "bbands_middle",
            "bbands_lower",
            "returns",
            "log_returns",
            "volatility",
            "sentiment_news",  # Placeholder
            "sentiment_social",  # Placeholder
        ]

    def validate_features(self, feature_list: List[str]) -> List[str]:
        """Validate that requested features are available.

        Args:
            feature_list: List of feature names to validate

        Returns:
            List of invalid feature names (empty if all valid)
        """
        available = self.get_available_features()
        invalid = [f for f in feature_list if f not in available]

        if invalid:
            logger.warning(f"Invalid features requested: {invalid}")

        return invalid


def create_feature_matrix(
    data: pd.DataFrame, features: List[str]
) -> pd.DataFrame:
    """Create feature matrix with only specified columns.

    Args:
        data: DataFrame with all features
        features: List of feature column names to include

    Returns:
        DataFrame with only specified features

    Raises:
        ValueError: If any requested features are missing
    """
    missing = [f for f in features if f not in data.columns]
    if missing:
        raise ValueError(f"Missing features in data: {missing}")

    return data[features].copy()
