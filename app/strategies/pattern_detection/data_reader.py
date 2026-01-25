"""
Data Reader Service
Reads market data collected by data.py agents (OI, Funding, Chart Analysis)
"""
import redis
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataReader:
    """
    Reads market data from Redis and Parquet files that data.py agents write.
    Provides market context for pattern detection strategies.
    """
    
    def __init__(self, redis_host='localhost', redis_port=6379, parquet_base_path='data/parquet'):
        """
        Initialize data reader.
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            parquet_base_path: Base directory for Parquet data files
        """
        try:
            self.redis_client = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self.redis_available = True
            logger.info(f"[DATA READER] Connected to Redis at {redis_host}:{redis_port}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            self.redis_available = False
            logger.warning(f"[DATA READER] Redis not available: {e}. Will use Parquet files only.")
        
        self.parquet_path = Path(parquet_base_path)
        self.cache = {}
        self.cache_duration = timedelta(seconds=30)
        
        logger.info("[DATA READER] Data Reader initialized")
    
    def get_latest_oi_data(self, symbol: str) -> Optional[Dict]:
        """
        Get latest OI (Open Interest) data for symbol from Redis.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            Dict with OI data or None if not available
        """
        # Check cache first
        cache_key = f"oi:{symbol}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data
        
        # Try Redis if available
        if self.redis_available:
            try:
                redis_key = f"oi:latest:{symbol}"
                data = self.redis_client.get(redis_key)
                if data:
                    parsed_data = json.loads(data)
                    self.cache[cache_key] = (parsed_data, datetime.now())
                    return parsed_data
            except Exception as e:
                logger.warning(f"[DATA READER] Failed to get OI data from Redis for {symbol}: {e}")
        
        # Fallback to Parquet file
        return self._get_latest_from_parquet('oi', symbol)
    
    def get_latest_funding_data(self, symbol: str) -> Optional[Dict]:
        """
        Get latest funding rate data for symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            Dict with funding data or None if not available
        """
        # Check cache first
        cache_key = f"funding:{symbol}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data
        
        # Try Redis if available
        if self.redis_available:
            try:
                redis_key = f"funding:latest:{symbol}"
                data = self.redis_client.get(redis_key)
                if data:
                    parsed_data = json.loads(data)
                    self.cache[cache_key] = (parsed_data, datetime.now())
                    return parsed_data
            except Exception as e:
                logger.warning(f"[DATA READER] Failed to get funding data from Redis for {symbol}: {e}")
        
        # Fallback to Parquet file
        return self._get_latest_from_parquet('funding', symbol)
    
    def get_latest_chart_analysis(self, symbol: str) -> Optional[Dict]:
        """
        Get latest technical analysis data for symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            Dict with chart analysis or None if not available
        """
        # Check cache first
        cache_key = f"chart:{symbol}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data
        
        # Try Redis if available
        if self.redis_available:
            try:
                redis_key = f"chart:latest:{symbol}"
                data = self.redis_client.get(redis_key)
                if data:
                    parsed_data = json.loads(data)
                    self.cache[cache_key] = (parsed_data, datetime.now())
                    return parsed_data
            except Exception as e:
                logger.warning(f"[DATA READER] Failed to get chart data from Redis for {symbol}: {e}")
        
        # Fallback to Parquet file
        return self._get_latest_from_parquet('chart', symbol)
    
    def get_historical_oi(self, symbol: str, days: int = 7) -> pd.DataFrame:
        """
        Load historical OI data from Parquet files.
        
        Args:
            symbol: Trading symbol
            days: Number of days of history to load
            
        Returns:
            DataFrame with historical OI data
        """
        file_path = self.parquet_path / "oi" / f"{symbol}_oi.parquet"
        if file_path.exists():
            try:
                df = pd.read_parquet(file_path)
                if 'timestamp' in df.columns:
                    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
                    return df[df['timestamp'] > cutoff]
                return df.tail(days * 24)  # Rough estimate
            except Exception as e:
                logger.error(f"[DATA READER] Failed to read OI parquet for {symbol}: {e}")
        return pd.DataFrame()
    
    def get_historical_funding(self, symbol: str, days: int = 7) -> pd.DataFrame:
        """
        Load historical funding rate data from Parquet files.
        
        Args:
            symbol: Trading symbol
            days: Number of days of history to load
            
        Returns:
            DataFrame with historical funding data
        """
        file_path = self.parquet_path / "funding" / f"{symbol}_funding.parquet"
        if file_path.exists():
            try:
                df = pd.read_parquet(file_path)
                if 'timestamp' in df.columns:
                    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
                    return df[df['timestamp'] > cutoff]
                return df.tail(days * 8)  # Funding every 8 hours typically
            except Exception as e:
                logger.error(f"[DATA READER] Failed to read funding parquet for {symbol}: {e}")
        return pd.DataFrame()
    
    def _get_latest_from_parquet(self, data_type: str, symbol: str) -> Optional[Dict]:
        """
        Fallback method to get latest data from Parquet files.
        
        Args:
            data_type: Type of data ('oi', 'funding', 'chart')
            symbol: Trading symbol
            
        Returns:
            Dict with latest data or None
        """
        file_path = self.parquet_path / data_type / f"{symbol}_{data_type}.parquet"
        if file_path.exists():
            try:
                df = pd.read_parquet(file_path)
                if not df.empty:
                    # Get most recent row
                    latest = df.iloc[-1].to_dict()
                    return latest
            except Exception as e:
                logger.error(f"[DATA READER] Failed to read parquet for {symbol} ({data_type}): {e}")
        return None
    
    def get_all_market_context(self, symbol: str) -> Dict:
        """
        Get all available market data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict with all available market data
        """
        return {
            'oi': self.get_latest_oi_data(symbol),
            'funding': self.get_latest_funding_data(symbol),
            'chart': self.get_latest_chart_analysis(symbol)
        }
    
    def is_connected(self) -> bool:
        """Check if data reader has active connections"""
        return self.redis_available or self.parquet_path.exists()

