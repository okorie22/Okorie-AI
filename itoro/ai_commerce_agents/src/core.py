"""
Stub core module for commerce agents testing.
Provides minimal implementations of core database models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class UnifiedTradingSignal:
    """Stub implementation for testing"""
    signal_id: str
    ecosystem: str
    timestamp: datetime
    symbol: str
    action: str
    signal_type: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: Optional[float] = None
    volume: Optional[float] = None
    agent_source: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    raw_payload: Optional[Dict[str, Any]] = None


@dataclass
class WhaleRankingRecord:
    """Stub implementation for testing"""
    ranking_id: str
    ecosystem: str
    address: str
    rank: int
    score: float
    pnl_30d: float
    pnl_7d: float
    pnl_1d: float
    winrate_7d: float
    last_active: datetime
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StrategyMetadataRecord:
    """Stub implementation for testing"""
    strategy_id: str
    ecosystem: str
    name: str
    agent_source: str
    timestamp: datetime
    metrics: Dict[str, Any]
    is_active: bool = True


@dataclass
class ExecutedTradeRecord:
    """Stub implementation for testing"""
    trade_id: str
    ecosystem: str
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: float
    pnl: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
