"""Market data loader for alpha-bench.

This module handles fetching OHLCV (Open, High, Low, Close, Volume) market data
from external APIs with caching, retry logic, and error handling.

Usage:
    from alpha_bench.data.loader import MarketDataLoader

    loader = MarketDataLoader()
    data = loader.fetch_ohlcv('BTC/USD', start_time, end_time)
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Raised when API request fails."""

    pass


class MarketDataLoader:
    """Fetches market data from external APIs with caching and retry logic.

    Attributes:
        api_key: API key for market data provider
        base_url: Base URL for API requests
        provider: Data provider name (e.g., 'alphavantage', 'yahoo', 'coinapi')
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: str = "coinapi",
        timeout: int = 30,
    ):
        """Initialize market data loader.

        Args:
            api_key: API key (defaults to MARKET_DATA_API_KEY env var)
            base_url: Base URL (defaults to MARKET_DATA_BASE_URL env var)
            provider: Data provider name
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("MARKET_DATA_API_KEY")
        self.base_url = base_url or os.getenv(
            "MARKET_DATA_BASE_URL", "https://rest.coinapi.io/v1"
        )
        self.provider = provider
        self.timeout = timeout

        if not self.api_key:
            logger.warning(
                "No API key provided. Set MARKET_DATA_API_KEY environment variable."
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def fetch_ohlcv(
        self,
        symbol: str,
        start: Union[datetime, str],
        end: Union[datetime, str],
        timeframe: str = "1h",
    ) -> pd.DataFrame:
        """Fetch OHLCV market data for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'BTC/USD', 'BTCUSD', 'BTC-USD')
            start: Start datetime (inclusive)
            end: End datetime (exclusive)
            timeframe: Timeframe (e.g., '1h', '1d', '5m')

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            Index is DatetimeIndex

        Raises:
            APIError: If data source is unavailable
            ValueError: If date range is invalid
        """
        # Normalize inputs
        start_dt = self._parse_datetime(start)
        end_dt = self._parse_datetime(end)

        if start_dt >= end_dt:
            raise ValueError(f"Invalid date range: {start_dt} >= {end_dt}")

        # Normalize symbol for provider
        normalized_symbol = self._normalize_symbol(symbol)

        logger.info(
            f"Fetching {normalized_symbol} data from {start_dt} to {end_dt} ({timeframe})"
        )

        # Fetch from appropriate provider
        if self.provider == "coinapi":
            data = self._fetch_coinapi(normalized_symbol, start_dt, end_dt, timeframe)
        elif self.provider == "alphavantage":
            data = self._fetch_alphavantage(
                normalized_symbol, start_dt, end_dt, timeframe
            )
        elif self.provider == "yahoo":
            data = self._fetch_yahoo(normalized_symbol, start_dt, end_dt, timeframe)
        elif self.provider == "mock":
            # Mock provider for testing
            data = self._generate_mock_data(normalized_symbol, start_dt, end_dt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        # Validate and clean data
        data = self._validate_ohlcv(data)

        logger.info(f"Fetched {len(data)} rows for {normalized_symbol}")
        return data

    def fetch_latest(
        self, symbol: str = "BTC/USD", lookback_hours: int = 72
    ) -> pd.DataFrame:
        """Fetch latest market data for a symbol.

        Args:
            symbol: Trading symbol
            lookback_hours: Hours of historical data to fetch

        Returns:
            DataFrame with OHLCV data
        """
        end = datetime.utcnow()
        start = end - timedelta(hours=lookback_hours)
        return self.fetch_ohlcv(symbol, start, end)

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        start: Union[datetime, str],
        end: Union[datetime, str],
        timeframe: str = "1h",
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols.

        Args:
            symbols: List of trading symbols
            start: Start datetime
            end: End datetime
            timeframe: Timeframe

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        results = {}

        for symbol in symbols:
            try:
                data = self.fetch_ohlcv(symbol, start, end, timeframe)
                results[symbol] = data
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                results[symbol] = None

        return results

    def _fetch_coinapi(
        self, symbol: str, start: datetime, end: datetime, timeframe: str
    ) -> pd.DataFrame:
        """Fetch data from CoinAPI.

        Args:
            symbol: Normalized symbol (e.g., 'BITSTAMP_SPOT_BTC_USD')
            start: Start datetime
            end: End datetime
            timeframe: Timeframe

        Returns:
            DataFrame with OHLCV data
        """
        # Map timeframe to CoinAPI period
        period_map = {
            "1m": "1MIN",
            "5m": "5MIN",
            "15m": "15MIN",
            "1h": "1HRS",
            "4h": "4HRS",
            "1d": "1DAY",
        }
        period = period_map.get(timeframe, "1HRS")

        url = f"{self.base_url}/ohlcv/{symbol}/history"
        params = {
            "period_id": period,
            "time_start": start.isoformat(),
            "time_end": end.isoformat(),
            "limit": 10000,
        }
        headers = {"X-CoinAPI-Key": self.api_key}

        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                logger.warning(f"No data returned for {symbol}")
                return self._empty_dataframe()

            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["time_period_start"])
            df = df.rename(
                columns={
                    "price_open": "open",
                    "price_high": "high",
                    "price_low": "low",
                    "price_close": "close",
                    "volume_traded": "volume",
                }
            )
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            df = df.set_index("timestamp")
            return df

        except requests.exceptions.RequestException as e:
            raise APIError(f"CoinAPI request failed: {e}")

    def _fetch_alphavantage(
        self, symbol: str, start: datetime, end: datetime, timeframe: str
    ) -> pd.DataFrame:
        """Fetch data from Alpha Vantage.

        Args:
            symbol: Symbol (e.g., 'BTC')
            start: Start datetime
            end: End datetime
            timeframe: Timeframe

        Returns:
            DataFrame with OHLCV data
        """
        # Alpha Vantage has different endpoints for different timeframes
        function_map = {
            "1m": "TIME_SERIES_INTRADAY",
            "5m": "TIME_SERIES_INTRADAY",
            "15m": "TIME_SERIES_INTRADAY",
            "1h": "TIME_SERIES_INTRADAY",
            "1d": "TIME_SERIES_DAILY",
        }
        function = function_map.get(timeframe, "TIME_SERIES_INTRADAY")

        url = f"{self.base_url}/query"
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": self.api_key,
            "outputsize": "full",
            "datatype": "json",
        }

        if "INTRADAY" in function:
            params["interval"] = timeframe

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # Parse Alpha Vantage response
            time_series_key = [k for k in data.keys() if "Time Series" in k][0]
            time_series = data[time_series_key]

            records = []
            for timestamp_str, values in time_series.items():
                timestamp = pd.to_datetime(timestamp_str)
                if start <= timestamp < end:
                    records.append(
                        {
                            "timestamp": timestamp,
                            "open": float(values["1. open"]),
                            "high": float(values["2. high"]),
                            "low": float(values["3. low"]),
                            "close": float(values["4. close"]),
                            "volume": float(values["5. volume"]),
                        }
                    )

            df = pd.DataFrame(records)
            df = df.set_index("timestamp").sort_index()
            return df

        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            raise APIError(f"Alpha Vantage request failed: {e}")

    def _fetch_yahoo(
        self, symbol: str, start: datetime, end: datetime, timeframe: str
    ) -> pd.DataFrame:
        """Fetch data from Yahoo Finance (via yfinance library).

        Note: This requires yfinance to be installed.

        Args:
            symbol: Symbol (e.g., 'BTC-USD')
            start: Start datetime
            end: End datetime
            timeframe: Timeframe

        Returns:
            DataFrame with OHLCV data
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError(
                "yfinance library required for Yahoo provider. Install with: pip install yfinance"
            )

        # Map timeframe to yfinance interval
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "1d": "1d",
        }
        interval = interval_map.get(timeframe, "1h")

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=interval)

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return self._empty_dataframe()

            df = df.reset_index()
            df = df.rename(
                columns={
                    "Date": "timestamp",
                    "Datetime": "timestamp",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            df = df.set_index("timestamp")
            return df

        except Exception as e:
            raise APIError(f"Yahoo Finance request failed: {e}")

    def _generate_mock_data(
        self, symbol: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Generate mock market data for testing.

        Args:
            symbol: Symbol
            start: Start datetime
            end: End datetime

        Returns:
            DataFrame with synthetic OHLCV data
        """
        import numpy as np

        # Generate hourly timestamps
        timestamps = pd.date_range(start=start, end=end, freq="1H")

        # Generate random walk price data
        np.random.seed(hash(symbol) % (2**32))
        returns = np.random.normal(0.0001, 0.02, len(timestamps))
        price = 50000 * np.exp(np.cumsum(returns))

        # Generate OHLCV
        data = {
            "timestamp": timestamps,
            "open": price * (1 + np.random.uniform(-0.005, 0.005, len(timestamps))),
            "high": price * (1 + np.random.uniform(0.001, 0.01, len(timestamps))),
            "low": price * (1 - np.random.uniform(0.001, 0.01, len(timestamps))),
            "close": price,
            "volume": np.random.uniform(100, 1000, len(timestamps)),
        }

        df = pd.DataFrame(data)
        df = df.set_index("timestamp")
        return df

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for provider.

        Args:
            symbol: Input symbol (e.g., 'BTC/USD', 'BTC-USD', 'BTCUSD')

        Returns:
            Normalized symbol for provider
        """
        if self.provider == "coinapi":
            # CoinAPI uses format: EXCHANGE_TYPE_BASE_QUOTE
            # For simplicity, use Bitstamp for BTC/USD
            symbol = symbol.replace("/", "_").replace("-", "_")
            if symbol == "BTC_USD":
                return "BITSTAMP_SPOT_BTC_USD"
            elif symbol == "ETH_USD":
                return "BITSTAMP_SPOT_ETH_USD"
            return f"BITSTAMP_SPOT_{symbol}"

        elif self.provider == "alphavantage":
            # Alpha Vantage uses simple symbols
            return symbol.replace("/", "").replace("-", "")

        elif self.provider == "yahoo":
            # Yahoo uses hyphen format
            return symbol.replace("/", "-")

        elif self.provider == "mock":
            return symbol

        return symbol

    @staticmethod
    def _parse_datetime(dt: Union[datetime, str]) -> datetime:
        """Parse datetime from various formats.

        Args:
            dt: Datetime object or ISO format string

        Returns:
            Datetime object
        """
        if isinstance(dt, datetime):
            return dt
        return pd.to_datetime(dt).to_pydatetime()

    @staticmethod
    def _empty_dataframe() -> pd.DataFrame:
        """Create empty DataFrame with correct schema.

        Returns:
            Empty DataFrame with OHLCV columns
        """
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            index=pd.DatetimeIndex([], name="timestamp"),
        )

    @staticmethod
    def _validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean OHLCV data.

        Args:
            df: Input DataFrame

        Returns:
            Cleaned DataFrame

        Raises:
            ValueError: If data is invalid
        """
        required_cols = ["open", "high", "low", "close", "volume"]

        # Check required columns
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Remove NaN rows
        df = df.dropna()

        # Ensure positive prices
        for col in ["open", "high", "low", "close"]:
            if (df[col] <= 0).any():
                logger.warning(f"Found non-positive prices in {col}, removing rows")
                df = df[df[col] > 0]

        # Validate OHLC relationship
        invalid_ohlc = (df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"]) | (df["low"] > df["open"]) | (df["low"] > df["close"])
        if invalid_ohlc.any():
            logger.warning(f"Found {invalid_ohlc.sum()} invalid OHLC relationships")
            df = df[~invalid_ohlc]

        # Sort by index (timestamp)
        df = df.sort_index()

        return df
