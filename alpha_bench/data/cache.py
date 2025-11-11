"""Data caching for alpha-bench.

This module handles caching of market data and features to disk using Parquet format
with automatic expiration and cache management.

Usage:
    from alpha_bench.data.cache import DataCache

    cache = DataCache()
    cache.put('BTC_USD_2025-11-10', dataframe)
    df = cache.get('BTC_USD_2025-11-10')
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


class DataCache:
    """Manages local caching of market data and features.

    Uses Parquet format for efficient storage and retrieval.
    Implements TTL (time-to-live) for automatic cache expiration.

    Attributes:
        cache_dir: Directory for cache storage
        default_ttl: Default cache TTL in seconds
    """

    def __init__(
        self,
        cache_dir: Optional[Union[str, Path]] = None,
        default_ttl: int = 7 * 24 * 3600,  # 7 days
    ):
        """Initialize data cache.

        Args:
            cache_dir: Cache directory path (defaults to ./data/cache/)
            default_ttl: Default TTL in seconds (default 7 days)
        """
        if cache_dir is None:
            # Auto-detect project root and use data/cache
            from alpha_bench.config import Config

            config = Config.load()
            cache_dir = config.project_root / "data" / "cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

        logger.debug(f"DataCache initialized: {self.cache_dir}")

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """Retrieve data from cache.

        Args:
            key: Cache key (used as filename)

        Returns:
            DataFrame if found and not expired, None otherwise
        """
        filepath = self._get_filepath(key)

        if not filepath.exists():
            logger.debug(f"Cache miss: {key}")
            return None

        # Check if expired
        if self._is_expired(filepath):
            logger.debug(f"Cache expired: {key}")
            self._delete(filepath)
            return None

        try:
            df = pd.read_parquet(filepath)
            logger.debug(f"Cache hit: {key} ({len(df)} rows)")
            return df
        except Exception as e:
            logger.error(f"Error reading cache {key}: {e}")
            self._delete(filepath)
            return None

    def put(self, key: str, data: pd.DataFrame, ttl: Optional[int] = None) -> None:
        """Store data in cache.

        Args:
            key: Cache key (used as filename)
            data: DataFrame to cache
            ttl: Time-to-live in seconds (defaults to default_ttl)
        """
        if data is None or data.empty:
            logger.warning(f"Attempted to cache empty data: {key}")
            return

        filepath = self._get_filepath(key)

        try:
            data.to_parquet(
                filepath,
                engine="pyarrow",
                compression="snappy",
                index=True,
            )
            logger.debug(f"Cached {len(data)} rows: {key}")

            # Store metadata for TTL tracking
            metadata_path = filepath.with_suffix(".meta")
            ttl_seconds = ttl or self.default_ttl
            expiry = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            with open(metadata_path, "w") as f:
                f.write(expiry.isoformat())

        except Exception as e:
            logger.error(f"Error caching {key}: {e}")

    def exists(self, key: str) -> bool:
        """Check if key exists in cache and is not expired.

        Args:
            key: Cache key

        Returns:
            True if cached and not expired, False otherwise
        """
        filepath = self._get_filepath(key)

        if not filepath.exists():
            return False

        if self._is_expired(filepath):
            self._delete(filepath)
            return False

        return True

    def delete(self, key: str) -> None:
        """Delete data from cache.

        Args:
            key: Cache key
        """
        filepath = self._get_filepath(key)
        self._delete(filepath)

    def clear_all(self) -> int:
        """Clear all cached data.

        Returns:
            Number of files deleted
        """
        count = 0
        for filepath in self.cache_dir.glob("*.parquet"):
            self._delete(filepath)
            count += 1
        logger.info(f"Cleared {count} cached files")
        return count

    def clear_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of expired files deleted
        """
        count = 0
        for filepath in self.cache_dir.glob("*.parquet"):
            if self._is_expired(filepath):
                self._delete(filepath)
                count += 1

        if count > 0:
            logger.info(f"Cleared {count} expired cache files")
        return count

    def get_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Total size of all cached files in bytes
        """
        total_size = 0
        for filepath in self.cache_dir.glob("*.parquet"):
            total_size += filepath.stat().st_size
        return total_size

    def get_count(self) -> int:
        """Get number of cached files.

        Returns:
            Number of .parquet files in cache
        """
        return len(list(self.cache_dir.glob("*.parquet")))

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats (count, size, expired_count)
        """
        files = list(self.cache_dir.glob("*.parquet"))
        total_size = sum(f.stat().st_size for f in files)
        expired_count = sum(1 for f in files if self._is_expired(f))

        return {
            "count": len(files),
            "size_bytes": total_size,
            "size_mb": total_size / (1024 * 1024),
            "expired_count": expired_count,
            "cache_dir": str(self.cache_dir),
        }

    def _get_filepath(self, key: str) -> Path:
        """Get filepath for cache key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Sanitize key to make it filesystem-safe
        safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_key}.parquet"

    def _is_expired(self, filepath: Path) -> bool:
        """Check if cache file is expired.

        Args:
            filepath: Path to cache file

        Returns:
            True if expired, False otherwise
        """
        metadata_path = filepath.with_suffix(".meta")

        # If no metadata, use file modification time + default TTL
        if not metadata_path.exists():
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            expiry = mtime + timedelta(seconds=self.default_ttl)
            return datetime.utcnow() > expiry

        # Read expiry from metadata
        try:
            with open(metadata_path, "r") as f:
                expiry_str = f.read().strip()
                expiry = datetime.fromisoformat(expiry_str)
                return datetime.utcnow() > expiry
        except Exception as e:
            logger.warning(f"Error reading metadata for {filepath}: {e}")
            # If metadata is corrupted, consider it expired
            return True

    def _delete(self, filepath: Path) -> None:
        """Delete cache file and its metadata.

        Args:
            filepath: Path to cache file
        """
        try:
            if filepath.exists():
                filepath.unlink()
            metadata_path = filepath.with_suffix(".meta")
            if metadata_path.exists():
                metadata_path.unlink()
            logger.debug(f"Deleted cache file: {filepath.name}")
        except Exception as e:
            logger.error(f"Error deleting cache file {filepath}: {e}")

    def __repr__(self) -> str:
        """String representation of cache."""
        stats = self.get_stats()
        return (
            f"DataCache(dir={self.cache_dir}, "
            f"files={stats['count']}, "
            f"size={stats['size_mb']:.2f}MB, "
            f"expired={stats['expired_count']})"
        )


def create_cache_key(
    symbol: str,
    start: datetime,
    end: datetime,
    data_type: str = "ohlcv",
) -> str:
    """Create a standardized cache key.

    Args:
        symbol: Trading symbol
        start: Start datetime
        end: End datetime
        data_type: Type of data (e.g., 'ohlcv', 'features')

    Returns:
        Cache key string

    Example:
        >>> create_cache_key('BTC/USD', datetime(2025, 11, 10), datetime(2025, 11, 11))
        'BTC_USD_ohlcv_2025-11-10_2025-11-11'
    """
    symbol_clean = symbol.replace("/", "_").replace("-", "_")
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    return f"{symbol_clean}_{data_type}_{start_str}_{end_str}"
