"""
🗄️ ITORO Database Manager
High-level database operations for commerce agents

Provides unified interface for data operations across all commerce agents.
Handles schema management, data validation, and performance optimizations.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Sequence
from dataclasses import dataclass, asdict
import logging

try:
    # Try relative imports first (when used as part of package)
    from core_infrastructure.database import (
        UnifiedTradingSignal,
        WhaleRankingRecord,
        StrategyMetadataRecord,
        ExecutedTradeRecord,
    )
except ImportError:
    # Fall back to absolute imports (when imported directly)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core_infrastructure.database import (
        UnifiedTradingSignal,
        WhaleRankingRecord,
        StrategyMetadataRecord,
        ExecutedTradeRecord,
    )

from .cloud_storage import get_cloud_storage_manager
from .config import (
    SIGNAL_SCHEMA, WHALE_RANKING_SCHEMA, STRATEGY_SCHEMA,
    MAX_SIGNAL_RECORDS, MAX_WHALE_RECORDS, MAX_STRATEGY_RECORDS,
    SIGNAL_HISTORY_RETENTION_DAYS, WHALE_RANKING_RETENTION_DAYS, STRATEGY_METADATA_RETENTION_DAYS
)

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 📋 DATA MODELS
# =============================================================================

@dataclass
class TradingSignal:
    """Trading signal data model"""
    timestamp: datetime
    symbol: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    price: float
    volume: float
    source_agent: str
    metadata: Optional[Dict[str, Any]] = None
    signal_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingSignal':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'signal_id' not in data_copy:
            data_copy['signal_id'] = None
        return cls(**data_copy)

    @classmethod
    def from_core(cls, signal: UnifiedTradingSignal) -> 'TradingSignal':
        """Create from unified core trading signal."""
        metadata = dict(signal.raw_payload) if signal.raw_payload else {}
        if signal.tags:
            metadata.setdefault('tags', signal.tags)
        return cls(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            action=signal.action,
            confidence=signal.confidence or 0.0,
            price=signal.entry_price or metadata.get("price") or 0.0,
            volume=signal.volume or metadata.get("volume") or 0.0,
            source_agent=signal.agent_source or "unknown",
            metadata=metadata or None,
            signal_id=signal.signal_id,
        )

    def to_core(self) -> UnifiedTradingSignal:
        """Convert to unified core trading signal."""
        metadata = self.metadata or {}
        return UnifiedTradingSignal(
            signal_id=self.signal_id or f"signal_{int(self.timestamp.timestamp() * 1_000_000)}",
            ecosystem=metadata.get("ecosystem", "commerce"),
            timestamp=self.timestamp,
            symbol=self.symbol,
            action=self.action,
            signal_type=metadata.get("signal_type", "MARKET"),
            entry_price=self.price,
            stop_loss=metadata.get("stop_loss"),
            take_profit=metadata.get("take_profit"),
            confidence=self.confidence,
            volume=self.volume,
            agent_source=self.source_agent,
            tags=metadata.get("tags", []),
            raw_payload=metadata,
        )

@dataclass
class WhaleRanking:
    """Whale wallet ranking data model"""
    address: str
    twitter_handle: Optional[str]
    pnl_30d: float
    pnl_7d: float
    pnl_1d: float
    winrate_7d: float
    txs_30d: int
    token_active: int
    last_active: datetime
    is_blue_verified: bool
    avg_holding_period_7d: float
    score: float
    rank: int
    last_updated: datetime
    ranking_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['last_active'] = self.last_active.isoformat()
        data['last_updated'] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WhaleRanking':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['last_active'] = datetime.fromisoformat(data['last_active'])
        data_copy['last_updated'] = datetime.fromisoformat(data['last_updated'])
        if 'ranking_id' not in data_copy:
            data_copy['ranking_id'] = None
        return cls(**data_copy)

    @classmethod
    def from_core(cls, ranking: WhaleRankingRecord) -> 'WhaleRanking':
        metadata = dict(ranking.metadata) if ranking.metadata else {}
        twitter_handle = metadata.get("twitter_handle") if metadata else None
        return cls(
            address=ranking.address,
            twitter_handle=twitter_handle,
            pnl_30d=ranking.pnl_30d or 0.0,
            pnl_7d=ranking.pnl_7d or 0.0,
            pnl_1d=ranking.pnl_1d or 0.0,
            winrate_7d=ranking.winrate_7d or 0.0,
            txs_30d=metadata.get("txs_30d", 0),
            token_active=metadata.get("token_active", 0),
            last_active=ranking.last_active,
            is_blue_verified=metadata.get("is_blue_verified", False),
            avg_holding_period_7d=metadata.get("avg_holding_period_7d", 0.0),
            score=ranking.score,
            rank=ranking.rank,
            last_updated=ranking.last_active,
            ranking_id=ranking.ranking_id,
        )

    def to_core(self) -> WhaleRankingRecord:
        metadata = {
            "twitter_handle": self.twitter_handle,
            "txs_30d": self.txs_30d,
            "token_active": self.token_active,
            "is_blue_verified": self.is_blue_verified,
            "avg_holding_period_7d": self.avg_holding_period_7d,
        }
        return WhaleRankingRecord(
            ranking_id=self.ranking_id or f"ranking_{int(self.last_updated.timestamp())}",
            ecosystem="commerce",
            address=self.address,
            rank=self.rank,
            score=self.score,
            pnl_30d=self.pnl_30d,
            pnl_7d=self.pnl_7d,
            pnl_1d=self.pnl_1d,
            winrate_7d=self.winrate_7d,
            last_active=self.last_active,
            is_active=True,
            metadata=metadata,
        )

@dataclass
class StrategyMetadata:
    """Strategy performance metadata model"""
    strategy_id: str
    strategy_name: str
    agent_type: str
    performance_metrics: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    last_updated: datetime
    is_active: bool = True
    metadata_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['last_updated'] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyMetadata':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['last_updated'] = datetime.fromisoformat(data['last_updated'])
        if 'metadata_id' not in data_copy:
            data_copy['metadata_id'] = None
        return cls(**data_copy)

    @classmethod
    def from_core(cls, metadata: StrategyMetadataRecord) -> 'StrategyMetadata':
        metrics = metadata.metrics or {}
        return cls(
            strategy_id=metadata.strategy_id,
            strategy_name=metadata.name,
            agent_type=metadata.agent_source,
            performance_metrics=metrics.get("performance", metrics),
            risk_metrics=metrics.get("risk", {}),
            last_updated=metadata.timestamp,
            is_active=True,
            metadata_id=metrics.get("metadata_id"),
        )

    def to_core(self) -> StrategyMetadataRecord:
        metrics = {
            "performance": self.performance_metrics,
            "risk": self.risk_metrics,
        }
        return StrategyMetadataRecord(
            strategy_id=self.strategy_id,
            ecosystem="commerce",
            name=self.strategy_name,
            agent_source=self.agent_type,
            timestamp=self.last_updated,
            sharpe_ratio=self.performance_metrics.get("sharpe_ratio"),
            win_rate=self.performance_metrics.get("win_rate"),
            drawdown=self.risk_metrics.get("max_drawdown"),
            value_at_risk=self.risk_metrics.get("value_at_risk"),
            metrics=metrics,
        )

@dataclass
class ExecutedTrade:
    """Executed trade data model"""
    timestamp: datetime
    symbol: str
    side: str  # 'BUY', 'SELL'
    quantity: float
    price: float
    value_usd: float
    source_agent: str
    pnl_realized: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    trade_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutedTrade':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'trade_id' not in data_copy:
            data_copy['trade_id'] = None
        return cls(**data_copy)

    @classmethod
    def from_core(cls, trade: ExecutedTradeRecord) -> 'ExecutedTrade':
        metadata = dict(trade.metadata) if trade.metadata else {}
        return cls(
            timestamp=trade.timestamp,
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=trade.price,
            value_usd=metadata.get("value_usd", trade.quantity * trade.price),
            source_agent=metadata.get("source_agent", metadata.get("agent_source", "unknown")),
            pnl_realized=trade.pnl,
            metadata=metadata or None,
            trade_id=trade.trade_id,
        )

    def to_core(self) -> ExecutedTradeRecord:
        metadata = self.metadata or {}
        metadata.setdefault("value_usd", self.value_usd)
        metadata.setdefault("source_agent", self.source_agent)
        return ExecutedTradeRecord(
            trade_id=self.trade_id or f"trade_{int(self.timestamp.timestamp() * 1_000_000)}",
            ecosystem=metadata.get("ecosystem", "commerce"),
            timestamp=self.timestamp,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            price=self.price,
            fees=metadata.get("fees"),
            pnl=self.pnl_realized,
            account_reference=metadata.get("account_reference"),
            metadata=metadata,
        )

# =============================================================================
# 🗄️ DATABASE MANAGER
# =============================================================================

class DatabaseManager:
    """High-level database manager for commerce operations"""

    def __init__(self):
        self.cloud_storage = get_cloud_storage_manager()
        self.connected = False

    def connect(self) -> bool:
        """Establish database connection"""
        self.connected = self.cloud_storage.connect()
        if self.connected:
            logger.info("Database manager connected to cloud storage")
        else:
            logger.error("ERROR: Failed to connect database manager to cloud storage")
        return self.connected

    # =========================================================================
    # 📊 TRADING SIGNALS OPERATIONS
    # =========================================================================

    def store_trading_signals(
        self,
        signals: Sequence[Union[TradingSignal, UnifiedTradingSignal]],
    ) -> bool:
        """Store trading signals with validation and cleanup"""
        if not self.connected:
            logger.error("Database not connected")
            return False

        try:
            normalized_signals = [self._ensure_trading_signal(signal) for signal in signals]

            # Convert to dictionaries
            signal_dicts = []
            for signal in normalized_signals:
                signal_dict = signal.to_dict()
                # Add unique ID if not present
                if not signal.signal_id:
                    signal.signal_id = f"signal_{int(time.time() * 1000000)}"
                signal_dicts.append(signal_dict)

            # Validate signal data
            self._validate_signals(signal_dicts)

            # Store signals
            success = self.cloud_storage.store_trading_signals(signal_dicts)
            if success:
                logger.info(f"SUCCESS: Stored {len(normalized_signals)} trading signals")

                # Cleanup old signals
                self._cleanup_old_signals()
            return success

        except Exception as e:
            logger.error(f"ERROR: Failed to store trading signals: {e}")
            return False

    def get_trading_signals(self, symbol: Optional[str] = None, limit: int = 100,
                          days_back: int = 7) -> List[TradingSignal]:
        """Retrieve trading signals with filtering"""
        if not self.connected:
            return []

        try:
            # Build query
            query = {}
            if symbol:
                query['symbol'] = symbol

            # Add time filter
            cutoff_date = datetime.now() - timedelta(days=days_back)
            query['timestamp'] = {'$gte': cutoff_date.isoformat()}

            # Retrieve data
            signal_dicts = self.cloud_storage.get_trading_signals(query, limit)

            # Convert to TradingSignal objects
            signals = []
            for signal_dict in signal_dicts:
                try:
                    signal = TradingSignal.from_dict(signal_dict)
                    signals.append(signal)
                except Exception as e:
                    logger.warning(f"Failed to parse signal: {e}")
                    continue

            logger.info(f"SUCCESS: Retrieved {len(signals)} trading signals")
            return signals

        except Exception as e:
            logger.error(f"ERROR: Failed to retrieve trading signals: {e}")
            return []

    # =========================================================================
    # 🐋 WHALE RANKINGS OPERATIONS
    # =========================================================================

    def store_whale_rankings(
        self,
        rankings: Sequence[Union[WhaleRanking, WhaleRankingRecord]],
    ) -> bool:
        """Store whale rankings with validation and cleanup"""
        if not self.connected:
            logger.error("Database not connected")
            return False

        try:
            normalized_rankings = [self._ensure_whale_ranking(ranking) for ranking in rankings]

            # Convert to dictionaries
            ranking_dicts = []
            for ranking in normalized_rankings:
                ranking_dict = ranking.to_dict()
                # Add unique ID if not present
                if not ranking.ranking_id:
                    ranking.ranking_id = f"whale_{ranking.address}_{int(time.time())}"
                ranking_dicts.append(ranking_dict)

            # Convert to Supabase whale_data format
            supabase_records = [self._build_supabase_record(r) for r in ranking_dicts]

            # Validate ranking data
            self._validate_whale_rankings(ranking_dicts)

            # Store rankings
            success = self.cloud_storage.store_whale_rankings(supabase_records)
            if success:
                logger.info(f"SUCCESS: Stored {len(normalized_rankings)} whale rankings")

                # Cleanup old rankings
                self._cleanup_old_whale_rankings()
            return success

        except Exception as e:
            logger.error(f"ERROR: Failed to store whale rankings: {e}")
            return False

    def get_whale_rankings(self, limit: int = 100, min_score: float = 0.0) -> List[WhaleRanking]:
        """Retrieve whale rankings with filtering"""
        if not self.connected:
            return []

        try:
            # Build query
            query = {}
            if min_score > 0:
                query['risk_score'] = {'$gte': min_score}

            # Retrieve data
            ranking_dicts = self.cloud_storage.get_whale_rankings(query, limit)

            # Convert to WhaleRanking objects
            rankings = []
            for ranking_dict in ranking_dicts:
                try:
                    normalized = self._normalize_whale_record(ranking_dict)
                    ranking = WhaleRanking.from_dict(normalized)
                    rankings.append(ranking)
                except Exception as e:
                    logger.warning(f"Failed to parse whale ranking: {e}")
                    continue

            # Sort by score descending
            rankings.sort(key=lambda x: x.score, reverse=True)

            logger.info(f"SUCCESS: Retrieved {len(rankings)} whale rankings")
            return rankings

        except Exception as e:
            logger.error(f"ERROR: Failed to retrieve whale rankings: {e}")
            return []

    def _normalize_whale_record(self, ranking_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Supabase whale_data rows for WhaleRanking construction."""
        metadata = ranking_dict.get('metadata') or {}

        def _get(key: str, default=None):
            return metadata.get(key, ranking_dict.get(key, default))

        last_active = _get('last_active') or ranking_dict.get('timestamp') or datetime.now().isoformat()
        last_updated = _get('last_updated') or ranking_dict.get('timestamp') or datetime.now().isoformat()

        normalized = {
            'address': _get('address', ranking_dict.get('wallet_address', 'unknown')),
            'twitter_handle': _get('twitter_handle', ranking_dict.get('wallet_name')),
            'pnl_30d': float(_get('pnl_30d', ranking_dict.get('pnl_30d') or 0.0)),
            'pnl_7d': float(_get('pnl_7d', ranking_dict.get('pnl_7d') or 0.0)),
            'pnl_1d': float(_get('pnl_1d', ranking_dict.get('pnl_1d') or 0.0)),
            'winrate_7d': float(_get('winrate_7d', ranking_dict.get('winrate_7d') or 0.0)),
            'txs_30d': int(_get('txs_30d', ranking_dict.get('txs_30d') or 0)),
            'token_active': int(_get('token_active', ranking_dict.get('token_active') or 0)),
            'last_active': last_active,
            'is_blue_verified': bool(_get('is_blue_verified', ranking_dict.get('is_blue_verified') or False)),
            'avg_holding_period_7d': float(_get('avg_holding_period_7d', ranking_dict.get('avg_holding_period_7d') or 0.0)),
            'score': float(_get('score', ranking_dict.get('risk_score') or 0.0)),
            'rank': int(_get('rank', ranking_dict.get('rank') or 0)),
            'last_updated': last_updated,
            'ranking_id': _get('ranking_id', ranking_dict.get('wallet_address')),
        }

        return normalized

    def _build_supabase_record(self, ranking_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Map WhaleRanking dict to Supabase whale_data schema."""
        metadata_payload = ranking_dict.copy()

        return {
            'wallet_address': ranking_dict.get('address'),
            'wallet_name': ranking_dict.get('twitter_handle') or ranking_dict.get('address', '')[:12],
            'pnl_1d': ranking_dict.get('pnl_1d'),
            'pnl_7d': ranking_dict.get('pnl_7d'),
            'pnl_30d': ranking_dict.get('pnl_30d'),
            'risk_score': ranking_dict.get('score'),
            'is_active': True,
            'metadata': metadata_payload
        }

    # =========================================================================
    # 📈 STRATEGY METADATA OPERATIONS
    # =========================================================================

    def store_strategy_metadata(
        self,
        metadata_list: Sequence[Union[StrategyMetadata, StrategyMetadataRecord]],
    ) -> bool:
        """Store strategy metadata with validation and cleanup"""
        if not self.connected:
            logger.error("Database not connected")
            return False

        try:
            normalized_metadata = [self._ensure_strategy_metadata(item) for item in metadata_list]

            # Convert to dictionaries
            metadata_dicts = []
            for metadata in normalized_metadata:
                metadata_dict = metadata.to_dict()
                # Add unique ID if not present
                if not metadata.metadata_id:
                    metadata.metadata_id = f"strategy_{metadata.strategy_id}_{int(time.time())}"
                metadata_dicts.append(metadata_dict)

            # Validate metadata
            self._validate_strategy_metadata(metadata_dicts)

            # Store metadata
            success = self.cloud_storage.store_strategy_metadata(metadata_dicts)
            if success:
                logger.info(f"SUCCESS: Stored {len(normalized_metadata)} strategy metadata records")

                # Cleanup old metadata
                self._cleanup_old_strategy_metadata()
            return success

        except Exception as e:
            logger.error(f"ERROR: Failed to store strategy metadata: {e}")
            return False

    def get_strategy_metadata(self, agent_type: Optional[str] = None,
                            active_only: bool = True) -> List[StrategyMetadata]:
        """Retrieve strategy metadata with filtering"""
        if not self.connected:
            return []

        try:
            # Build query
            query = {}
            if agent_type:
                query['agent_type'] = agent_type
            if active_only:
                query['is_active'] = True

            # Retrieve data
            metadata_dicts = self.cloud_storage.get_strategy_metadata(query)

            # Convert to StrategyMetadata objects
            metadata_list = []
            for metadata_dict in metadata_dicts:
                try:
                    metadata = StrategyMetadata.from_dict(metadata_dict)
                    metadata_list.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to parse strategy metadata: {e}")
                    continue

            logger.info(f"SUCCESS: Retrieved {len(metadata_list)} strategy metadata records")
            return metadata_list

        except Exception as e:
            logger.error(f"ERROR: Failed to retrieve strategy metadata: {e}")
            return []

    # =========================================================================
    # 💼 EXECUTED TRADES OPERATIONS
    # =========================================================================

    def store_executed_trades(
        self,
        trades: Sequence[Union[ExecutedTrade, ExecutedTradeRecord]],
    ) -> bool:
        """Store executed trades"""
        if not self.connected:
            logger.error("Database not connected")
            return False

        try:
            normalized_trades = [self._ensure_executed_trade(trade) for trade in trades]

            # Convert to dictionaries
            trade_dicts = []
            for trade in normalized_trades:
                trade_dict = trade.to_dict()
                # Add unique ID if not present
                if not trade.trade_id:
                    trade.trade_id = f"trade_{int(time.time() * 1000000)}"
                trade_dicts.append(trade_dict)

            # Store trades
            success = self.cloud_storage.store_executed_trades(trade_dicts)
            if success:
                logger.info(f"SUCCESS: Stored {len(normalized_trades)} executed trades")
            return success

        except Exception as e:
            logger.error(f"ERROR: Failed to store executed trades: {e}")
            return False

    def get_executed_trades(self, symbol: Optional[str] = None, limit: int = 100,
                          days_back: int = 30) -> List[ExecutedTrade]:
        """Retrieve executed trades with filtering"""
        if not self.connected:
            return []

        try:
            # Build query
            query = {}
            if symbol:
                query['symbol'] = symbol

            # Add time filter
            cutoff_date = datetime.now() - timedelta(days=days_back)
            query['timestamp'] = {'$gte': cutoff_date.isoformat()}

            # Retrieve data
            trade_dicts = self.cloud_storage.get_executed_trades(query, limit)

            # Convert to ExecutedTrade objects
            trades = []
            for trade_dict in trade_dicts:
                try:
                    trade = ExecutedTrade.from_dict(trade_dict)
                    trades.append(trade)
                except Exception as e:
                    logger.warning(f"Failed to parse trade: {e}")
                    continue

            logger.info(f"SUCCESS: Retrieved {len(trades)} executed trades")
            return trades

        except Exception as e:
            logger.error(f"ERROR: Failed to retrieve executed trades: {e}")
            return []

    # =========================================================================
    # 🧹 DATA CLEANUP METHODS
    # =========================================================================

    # -------------------------------------------------------------------------
    # Helpers to normalize unified core records into local dataclasses
    # -------------------------------------------------------------------------
    def _ensure_trading_signal(self, signal: Union[TradingSignal, UnifiedTradingSignal]) -> TradingSignal:
        if isinstance(signal, TradingSignal):
            return signal
        if isinstance(signal, UnifiedTradingSignal):
            return TradingSignal.from_core(signal)
        raise TypeError(f"Unsupported trading signal type: {type(signal)}")

    def _ensure_whale_ranking(self, ranking: Union[WhaleRanking, WhaleRankingRecord]) -> WhaleRanking:
        if isinstance(ranking, WhaleRanking):
            return ranking
        if isinstance(ranking, WhaleRankingRecord):
            return WhaleRanking.from_core(ranking)
        raise TypeError(f"Unsupported whale ranking type: {type(ranking)}")

    def _ensure_strategy_metadata(
        self,
        metadata: Union[StrategyMetadata, StrategyMetadataRecord],
    ) -> StrategyMetadata:
        if isinstance(metadata, StrategyMetadata):
            return metadata
        if isinstance(metadata, StrategyMetadataRecord):
            return StrategyMetadata.from_core(metadata)
        raise TypeError(f"Unsupported strategy metadata type: {type(metadata)}")

    def _ensure_executed_trade(
        self,
        trade: Union[ExecutedTrade, ExecutedTradeRecord],
    ) -> ExecutedTrade:
        if isinstance(trade, ExecutedTrade):
            return trade
        if isinstance(trade, ExecutedTradeRecord):
            return ExecutedTrade.from_core(trade)
        raise TypeError(f"Unsupported executed trade type: {type(trade)}")

    def _cleanup_old_signals(self):
        """Remove signals older than retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=SIGNAL_HISTORY_RETENTION_DAYS)
            # Note: Actual cleanup would depend on cloud storage provider capabilities
            # This is a placeholder for more sophisticated cleanup logic
            logger.info(f"Signal cleanup: would remove data older than {cutoff_date}")
        except Exception as e:
            logger.warning(f"Signal cleanup failed: {e}")

    def _cleanup_old_whale_rankings(self):
        """Remove whale rankings older than retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=WHALE_RANKING_RETENTION_DAYS)
            logger.info(f"Whale ranking cleanup: would remove data older than {cutoff_date}")
        except Exception as e:
            logger.warning(f"Whale ranking cleanup failed: {e}")

    def _cleanup_old_strategy_metadata(self):
        """Remove strategy metadata older than retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=STRATEGY_METADATA_RETENTION_DAYS)
            logger.info(f"Strategy metadata cleanup: would remove data older than {cutoff_date}")
        except Exception as e:
            logger.warning(f"Strategy metadata cleanup failed: {e}")

    # =========================================================================
    # SUCCESS: VALIDATION METHODS
    # =========================================================================

    def _validate_signals(self, signals: List[Dict[str, Any]]):
        """Validate trading signal data"""
        required_fields = ['timestamp', 'symbol', 'action', 'confidence', 'price', 'source_agent']

        for signal in signals:
            for field in required_fields:
                if field not in signal:
                    raise ValueError(f"Missing required field '{field}' in signal data")

            # Validate action
            if signal['action'] not in ['BUY', 'SELL', 'HOLD']:
                raise ValueError(f"Invalid action '{signal['action']}' in signal data")

            # Validate confidence range
            if not 0 <= signal['confidence'] <= 1:
                raise ValueError(f"Confidence must be between 0 and 1, got {signal['confidence']}")

    def _validate_whale_rankings(self, rankings: List[Dict[str, Any]]):
        """Validate whale ranking data"""
        required_fields = ['address', 'score', 'rank', 'last_updated']

        for ranking in rankings:
            for field in required_fields:
                if field not in ranking:
                    raise ValueError(f"Missing required field '{field}' in whale ranking data")

            # Validate score range
            if not 0 <= ranking['score'] <= 1:
                raise ValueError(f"Score must be between 0 and 1, got {ranking['score']}")

    def _validate_strategy_metadata(self, metadata_list: List[Dict[str, Any]]):
        """Validate strategy metadata"""
        required_fields = ['strategy_id', 'strategy_name', 'agent_type', 'performance_metrics', 'last_updated']

        for metadata in metadata_list:
            for field in required_fields:
                if field not in metadata:
                    raise ValueError(f"Missing required field '{field}' in strategy metadata")

            # Validate required nested fields
            if 'performance_metrics' in metadata:
                perf_metrics = metadata['performance_metrics']
                if not isinstance(perf_metrics, dict):
                    raise ValueError("performance_metrics must be a dictionary")

    # =========================================================================
    # 📊 ANALYTICS METHODS
    # =========================================================================

    def get_signal_stats(self, days_back: int = 7) -> Dict[str, Any]:
        """Get trading signal statistics"""
        signals = self.get_trading_signals(days_back=days_back)

        if not signals:
            return {'total_signals': 0, 'avg_confidence': 0, 'signal_distribution': {}}

        total_signals = len(signals)
        avg_confidence = sum(s.confidence for s in signals) / total_signals

        # Action distribution
        actions = {}
        for signal in signals:
            actions[signal.action] = actions.get(signal.action, 0) + 1

        return {
            'total_signals': total_signals,
            'avg_confidence': round(avg_confidence, 3),
            'signal_distribution': actions,
            'period_days': days_back
        }

    def get_whale_stats(self) -> Dict[str, Any]:
        """Get whale ranking statistics"""
        rankings = self.get_whale_rankings(limit=1000)

        if not rankings:
            return {'total_whales': 0, 'avg_score': 0, 'verified_percentage': 0}

        total_whales = len(rankings)
        avg_score = sum(r.score for r in rankings) / total_whales
        verified_count = sum(1 for r in rankings if r.is_blue_verified)
        verified_percentage = (verified_count / total_whales) * 100

        return {
            'total_whales': total_whales,
            'avg_score': round(avg_score, 3),
            'verified_percentage': round(verified_percentage, 1),
            'top_whale_score': max(r.score for r in rankings)
        }

    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy performance statistics"""
        metadata_list = self.get_strategy_metadata()

        if not metadata_list:
            return {'total_strategies': 0, 'active_strategies': 0, 'agent_types': []}

        total_strategies = len(metadata_list)
        active_strategies = sum(1 for m in metadata_list if m.is_active)

        # Agent type distribution
        agent_types = {}
        for metadata in metadata_list:
            agent_types[metadata.agent_type] = agent_types.get(metadata.agent_type, 0) + 1

        return {
            'total_strategies': total_strategies,
            'active_strategies': active_strategies,
            'agent_types': list(agent_types.keys()),
            'agent_distribution': agent_types
        }

    # =========================================================================
    # 🔍 SEARCH METHODS
    # =========================================================================

    def search_signals(self, query: str, limit: int = 50) -> List[TradingSignal]:
        """Search trading signals by various criteria"""
        # Note: This is a basic implementation. More sophisticated search
        # would depend on the cloud storage provider's search capabilities
        all_signals = self.get_trading_signals(limit=limit * 2)

        # Simple text search
        query_lower = query.lower()
        filtered_signals = []

        for signal in all_signals:
            if (query_lower in signal.symbol.lower() or
                query_lower in signal.source_agent.lower() or
                query_lower in signal.action.lower()):
                filtered_signals.append(signal)

            if len(filtered_signals) >= limit:
                break

        return filtered_signals

    def get_top_performing_whales(self, limit: int = 10) -> List[WhaleRanking]:
        """Get top performing whales by score"""
        rankings = self.get_whale_rankings(limit=limit * 2)
        return sorted(rankings, key=lambda x: x.score, reverse=True)[:limit]

    def get_recent_signals_by_agent(self, agent_name: str, limit: int = 20) -> List[TradingSignal]:
        """Get recent signals from specific agent"""
        all_signals = self.get_trading_signals(limit=limit * 3)

        agent_signals = [s for s in all_signals if s.source_agent == agent_name]
        return agent_signals[:limit]

# =============================================================================
# 🏭 FACTORY FUNCTION
# =============================================================================

def get_database_manager() -> DatabaseManager:
    """
    Factory function to create database manager

    Returns:
        Configured DatabaseManager instance
    """
    return DatabaseManager()

# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_database_operations():
    """Test database operations"""
    try:
        db = get_database_manager()
        connected = db.connect()

        if connected:
            print("SUCCESS: Database connection successful")

            # Test signal operations
            test_signal = TradingSignal(
                timestamp=datetime.now(),
                symbol="SOL/USD",
                action="BUY",
                confidence=0.85,
                price=150.50,
                volume=1000.0,
                source_agent="test_agent"
            )

            success = db.store_trading_signals([test_signal])
            if success:
                print("SUCCESS: Signal storage successful")

                # Retrieve signals
                signals = db.get_trading_signals(limit=5)
                print(f"SUCCESS: Retrieved {len(signals)} signals")

                # Test stats
                stats = db.get_signal_stats()
                print(f"SUCCESS: Signal stats: {stats}")

            # Test whale operations
            test_whale = WhaleRanking(
                address="test_wallet_address",
                twitter_handle="test_handle",
                pnl_30d=0.25,
                pnl_7d=0.15,
                pnl_1d=0.05,
                winrate_7d=0.75,
                txs_30d=1500,
                token_active=50,
                last_active=datetime.now(),
                is_blue_verified=True,
                avg_holding_period_7d=3600.0,
                score=0.85,
                rank=1,
                last_updated=datetime.now()
            )

            success = db.store_whale_rankings([test_whale])
            if success:
                print("SUCCESS: Whale ranking storage successful")

                rankings = db.get_whale_rankings(limit=5)
                print(f"SUCCESS: Retrieved {len(rankings)} whale rankings")

        else:
            print("ERROR: Database connection failed")

    except Exception as e:
        print(f"ERROR: Database test failed: {e}")

if __name__ == "__main__":
    test_database_operations()
