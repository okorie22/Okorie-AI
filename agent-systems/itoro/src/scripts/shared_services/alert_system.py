"""
🌙 Anarcho Capital's Alert System
Data structures and utilities for inter-agent alerts
Built with love by Anarcho Capital 🚀
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
import json

class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class AlertType(Enum):
    """Types of market alerts that agents can generate"""
    OI_SIGNIFICANT_CHANGE = "oi_change"
    FUNDING_RATE_EXTREME = "funding_extreme"
    LIQUIDATION_SPIKE = "liquidation_spike"
    SENTIMENT_SHIFT = "sentiment_shift"
    PRICE_BREAKOUT = "price_breakout"
    VOLUME_SPIKE = "volume_spike"
    WHALE_ACTIVITY = "whale_activity"
    MARKET_REGIME_CHANGE = "regime_change"
    WHALE_CONCENTRATION = "whale_concentration"
    LIQUIDITY_CHANGE = "liquidity_change"
    HOLDER_GROWTH = "holder_growth"
    ONCHAIN_ACTIVITY = "onchain_activity"

@dataclass
class MarketAlert:
    """
    Market alert data structure for inter-agent communication
    """
    agent_source: str
    alert_type: AlertType
    symbol: str
    severity: AlertSeverity
    confidence: float  # 0.0 to 1.0
    data: Dict[str, Any]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization"""
        return {
            'agent_source': self.agent_source,
            'alert_type': self.alert_type.value,
            'symbol': self.symbol,
            'severity': self.severity.value,
            'confidence': self.confidence,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketAlert':
        """Create alert from dictionary"""
        # Convert string values back to enums
        alert_type = AlertType(data['alert_type'])
        severity = AlertSeverity(data['severity'])
        timestamp = datetime.fromisoformat(data['timestamp'])

        return cls(
            agent_source=data['agent_source'],
            alert_type=alert_type,
            symbol=data['symbol'],
            severity=severity,
            confidence=data['confidence'],
            data=data['data'],
            timestamp=timestamp,
            metadata=data.get('metadata', {})
        )

    def get_priority_score(self) -> float:
        """
        Calculate priority score based on severity, confidence, and recency

        Returns:
            float: Priority score (higher = more important)
        """
        # Base score from severity
        severity_score = self.severity.value * 25  # 25, 50, 75, 100

        # Confidence multiplier (0-100 points)
        confidence_score = self.confidence * 100

        # Recency bonus (newer alerts get slight preference)
        age_hours = (datetime.now() - self.timestamp).total_seconds() / 3600
        recency_score = max(0, 10 - age_hours)  # 10 points max, decays over time

        return severity_score + confidence_score + recency_score

    def should_trigger_strategy(self) -> bool:
        """
        Determine if this alert should trigger strategy generation

        Returns:
            bool: True if alert meets strategy trigger criteria
        """
        # Must be at least MEDIUM severity
        if self.severity.value < AlertSeverity.MEDIUM.value:
            return False

        # Must have reasonable confidence
        if self.confidence < 0.6:
            return False

        # Must be recent (within last 2 hours)
        age_hours = (datetime.now() - self.timestamp).total_seconds() / 3600
        if age_hours > 2:
            return False

        return True

    def get_description(self) -> str:
        """Get human-readable description of the alert"""
        descriptions = {
            AlertType.OI_SIGNIFICANT_CHANGE: f"OI change: {self.data.get('oi_change_pct', 0):+.1f}%",
            AlertType.FUNDING_RATE_EXTREME: f"Funding rate: {self.data.get('funding_rate', 0):.2f}%",
            AlertType.LIQUIDATION_SPIKE: f"Liquidations: ${self.data.get('total_liquidations', 0):,.0f}",
            AlertType.SENTIMENT_SHIFT: f"Sentiment: {self.data.get('sentiment', 'unknown')}",
            AlertType.PRICE_BREAKOUT: f"Price breakout: {self.data.get('direction', 'unknown')}",
            AlertType.VOLUME_SPIKE: f"Volume spike: {self.data.get('volume_change_pct', 0):+.1f}%",
            AlertType.WHALE_ACTIVITY: f"Whale activity: {self.data.get('action', 'unknown')}",
            AlertType.MARKET_REGIME_CHANGE: f"Regime change: {self.data.get('new_regime', 'unknown')}",
            AlertType.WHALE_CONCENTRATION: f"Whale concentration: {self.data.get('top_holder_pct', 0):.1f}%",
            AlertType.LIQUIDITY_CHANGE: f"Liquidity change: {self.data.get('liquidity_change_pct', 0):+.1f}%",
            AlertType.HOLDER_GROWTH: f"Holder growth: {self.data.get('holder_change_pct', 0):+.1f}%",
            AlertType.ONCHAIN_ACTIVITY: f"On-chain activity: {self.data.get('trend_signal', 'unknown')}"
        }

        base_desc = descriptions.get(self.alert_type, f"Alert: {self.alert_type.value}")
        return f"[{self.symbol}] {base_desc} ({self.confidence:.1%} confidence)"

class AlertManager:
    """
    Manager for handling alert lifecycle and prioritization
    """

    def __init__(self):
        self.active_alerts: Dict[str, MarketAlert] = {}
        self.alert_history: list[MarketAlert] = []
        self.max_history_size = 1000

    def add_alert(self, alert: MarketAlert) -> bool:
        """
        Add new alert to active alerts

        Args:
            alert: The alert to add

        Returns:
            bool: True if alert was added/accepted
        """
        alert_key = f"{alert.symbol}_{alert.alert_type.value}"

        # Check if we already have a similar recent alert
        if alert_key in self.active_alerts:
            existing = self.active_alerts[alert_key]

            # If new alert has higher priority, replace the old one
            if alert.get_priority_score() > existing.get_priority_score():
                self.active_alerts[alert_key] = alert
                self._add_to_history(existing)
                return True
            else:
                # Keep existing alert, add new one to history only
                self._add_to_history(alert)
                return False

        # Add new alert
        self.active_alerts[alert_key] = alert
        return True

    def get_alerts_for_symbol(self, symbol: str) -> list[MarketAlert]:
        """Get all active alerts for a specific symbol"""
        return [
            alert for alert in self.active_alerts.values()
            if alert.symbol == symbol
        ]

    def get_high_priority_alerts(self, min_priority: float = 150) -> list[MarketAlert]:
        """Get alerts above a certain priority threshold"""
        return [
            alert for alert in self.active_alerts.values()
            if alert.get_priority_score() >= min_priority
        ]

    def get_strategy_trigger_alerts(self) -> list[MarketAlert]:
        """Get alerts that should trigger strategy generation"""
        return [
            alert for alert in self.active_alerts.values()
            if alert.should_trigger_strategy()
        ]

    def cleanup_expired_alerts(self, max_age_hours: int = 24):
        """Remove alerts older than specified hours"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        expired_keys = []
        for key, alert in self.active_alerts.items():
            if alert.timestamp.timestamp() < cutoff_time:
                expired_keys.append(key)
                self._add_to_history(alert)

        for key in expired_keys:
            del self.active_alerts[key]

        return len(expired_keys)

    def _add_to_history(self, alert: MarketAlert):
        """Add alert to history, maintaining max size"""
        self.alert_history.append(alert)

        # Maintain history size limit
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]

    def get_stats(self) -> Dict[str, Any]:
        """Get alert system statistics"""
        return {
            'active_alerts': len(self.active_alerts),
            'total_history': len(self.alert_history),
            'alerts_by_type': self._count_alerts_by_type(),
            'alerts_by_symbol': self._count_alerts_by_symbol(),
            'high_priority_count': len(self.get_high_priority_alerts()),
            'strategy_triggers': len(self.get_strategy_trigger_alerts())
        }

    def _count_alerts_by_type(self) -> Dict[str, int]:
        """Count alerts by type"""
        counts = {}
        for alert in self.active_alerts.values():
            alert_type = alert.alert_type.value
            counts[alert_type] = counts.get(alert_type, 0) + 1
        return counts

    def _count_alerts_by_symbol(self) -> Dict[str, int]:
        """Count alerts by symbol"""
        counts = {}
        for alert in self.active_alerts.values():
            counts[alert.symbol] = counts.get(alert.symbol, 0) + 1
        return counts

# Global alert manager instance
_alert_manager_instance: Optional[AlertManager] = None

def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance"""
    global _alert_manager_instance

    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager()

    return _alert_manager_instance
