"""
🌙 Anarcho Capital's DeFi Event Manager
Handles webhook-driven events and triggers appropriate DeFi actions
Built with love by Anarcho Capital 🚀
"""

import os
import time
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from threading import Thread, Lock

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical, system
from src.scripts.defi.defi_protocol_manager import get_defi_protocol_manager
from src.scripts.defi.defi_risk_manager import get_defi_risk_manager
from src.scripts.defi.yield_optimizer import get_yield_optimizer
from src.scripts.utilities.telegram_bot import get_telegram_bot
from src.config.defi_config import (
    LENDING_EVENT_TRIGGERS, RISK_EVENT_TRIGGERS, WEBHOOK_INTEGRATION,
    get_current_phase_config
)

@dataclass
class DeFiEvent:
    """DeFi event details"""
    event_id: str
    event_type: str  # yield_change, liquidation_risk, new_pool, protocol_alert, market_condition
    protocol: str
    token: str
    severity: str  # low, medium, high, critical
    data: Dict[str, Any]
    timestamp: datetime
    processed: bool
    action_taken: Optional[str]

@dataclass
class EventTrigger:
    """Event trigger configuration"""
    event_type: str
    threshold: float
    action: str
    priority: int
    enabled: bool

class DeFiEventManager:
    """
    Manages DeFi events from webhooks and triggers appropriate actions
    Provides event-driven architecture for DeFi operations
    """
    
    def __init__(self):
        """Initialize the DeFi Event Manager"""
        self.protocol_manager = get_defi_protocol_manager()
        self.risk_manager = get_defi_risk_manager()
        self.yield_optimizer = get_yield_optimizer()
        self.telegram_bot = get_telegram_bot()
        
        # Event tracking
        self.events_history = []
        self.pending_events = []
        self.event_triggers = {}
        
        # Threading and locks
        self.event_thread = None
        self.lock = Lock()
        self.is_running = False
        
        # Initialize event triggers
        self._initialize_event_triggers()
        
        # Event processing configuration
        self.max_events_per_cycle = 10
        self.event_retention_hours = WEBHOOK_INTEGRATION['event_retention_hours']
        
        info("📡 DeFi Event Manager initialized")
    
    def _initialize_event_triggers(self):
        """Initialize event triggers from configuration"""
        try:
            # Lending event triggers
            self.event_triggers.update({
                'yield_change': EventTrigger(
                    event_type='yield_change',
                    threshold=LENDING_EVENT_TRIGGERS['yield_change_threshold'],
                    action='optimize_yields',
                    priority=1,
                    enabled=True
                ),
                'new_opportunity': EventTrigger(
                    event_type='new_opportunity',
                    threshold=LENDING_EVENT_TRIGGERS['new_opportunity_threshold'],
                    action='assess_opportunity',
                    priority=2,
                    enabled=True
                ),
                'risk_threshold_breach': EventTrigger(
                    event_type='risk_threshold_breach',
                    threshold=LENDING_EVENT_TRIGGERS['risk_threshold_breach'],
                    action='risk_assessment',
                    priority=3,
                    enabled=True
                )
            })
            
            # Risk event triggers
            self.event_triggers.update({
                'liquidation_warning': EventTrigger(
                    event_type='liquidation_warning',
                    threshold=RISK_EVENT_TRIGGERS['liquidation_warning_threshold'],
                    action='add_collateral',
                    priority=1,
                    enabled=True
                ),
                'portfolio_loss': EventTrigger(
                    event_type='portfolio_loss',
                    threshold=RISK_EVENT_TRIGGERS['portfolio_loss_threshold'],
                    action='emergency_stop',
                    priority=1,
                    enabled=True
                ),
                'protocol_issue': EventTrigger(
                    event_type='protocol_issue',
                    threshold=RISK_EVENT_TRIGGERS['protocol_issue_threshold'],
                    action='protocol_review',
                    priority=2,
                    enabled=True
                ),
                'market_crash': EventTrigger(
                    event_type='market_crash',
                    threshold=RISK_EVENT_TRIGGERS['market_crash_threshold'],
                    action='reduce_exposure',
                    priority=1,
                    enabled=True
                )
            })
            
            info(f"✅ Initialized {len(self.event_triggers)} event triggers")
            
        except Exception as e:
            error(f"Failed to initialize event triggers: {str(e)}")
    
    def start_event_processing(self):
        """Start event processing in background thread"""
        try:
            if self.is_running:
                warning("Event processing is already running")
                return False
            
            self.is_running = True
            self.event_thread = Thread(target=self._run_event_processing_loop, daemon=True)
            self.event_thread.start()
            
            info("🚀 DeFi Event Manager started successfully")
            return True
            
        except Exception as e:
            error(f"Failed to start event processing: {str(e)}")
            return False
    
    def stop_event_processing(self):
        """Stop event processing"""
        try:
            self.is_running = False
            
            if self.event_thread and self.event_thread.is_alive():
                self.event_thread.join(timeout=10)
            
            info("🛑 DeFi Event Manager stopped")
            
        except Exception as e:
            error(f"Failed to stop event processing: {str(e)}")
    
    def _run_event_processing_loop(self):
        """Main event processing loop"""
        try:
            while self.is_running:
                try:
                    # Process pending events
                    self._process_pending_events()
                    
                    # Clean up old events
                    self._cleanup_old_events()
                    
                    # Sleep between cycles
                    time.sleep(5)  # Process events every 5 seconds
                    
                except Exception as e:
                    error(f"Error in event processing loop: {str(e)}")
                    time.sleep(10)  # Wait longer on error
                    
        except Exception as e:
            error(f"Fatal error in event processing loop: {str(e)}")
        finally:
            self.is_running = False
    
    def process_webhook_event(self, event_data: Dict[str, Any]) -> str:
        """Process webhook event from external sources"""
        try:
            # Extract event information
            event_type = event_data.get('type', 'unknown')
            protocol = event_data.get('protocol', 'unknown')
            token = event_data.get('token', 'unknown')
            severity = event_data.get('severity', 'medium')
            
            # Create DeFi event
            event = DeFiEvent(
                event_id=f"webhook_{int(time.time())}",
                event_type=event_type,
                protocol=protocol,
                token=token,
                severity=severity,
                data=event_data,
                timestamp=datetime.now(),
                processed=False,
                action_taken=None
            )
            
            # Add to pending events
            with self.lock:
                self.pending_events.append(event)
            
            info(f"📡 Webhook event received: {event_type} for {protocol}:{token}")
            return event.event_id
            
        except Exception as e:
            error(f"Failed to process webhook event: {str(e)}")
            return "error"
    
    def trigger_yield_change_event(self, protocol: str, token: str, old_apy: float, 
                                 new_apy: float) -> str:
        """Trigger yield change event"""
        try:
            # Calculate APY change
            apy_change = abs(new_apy - old_apy) / old_apy if old_apy > 0 else 0
            
            # Check if change exceeds threshold
            threshold = LENDING_EVENT_TRIGGERS['yield_change_threshold']
            
            if apy_change >= threshold:
                event = DeFiEvent(
                    event_id=f"yield_change_{int(time.time())}",
                    event_type='yield_change',
                    protocol=protocol,
                    token=token,
                    severity='medium' if apy_change < threshold * 2 else 'high',
                    data={
                        'old_apy': old_apy,
                        'new_apy': new_apy,
                        'apy_change': apy_change,
                        'threshold': threshold
                    },
                    timestamp=datetime.now(),
                    processed=False,
                    action_taken=None
                )
                
                # Add to pending events
                with self.lock:
                    self.pending_events.append(event)
                
                info(f"💰 Yield change event triggered: {protocol}:{token} APY changed by {apy_change*100:.2f}%")
                return event.event_id
            
            return "below_threshold"
            
        except Exception as e:
            error(f"Failed to trigger yield change event: {str(e)}")
            return "error"
    
    def trigger_liquidation_risk_event(self, protocol: str, token: str, 
                                     collateral_ratio: float, liquidation_threshold: float) -> str:
        """Trigger liquidation risk event"""
        try:
            # Calculate buffer above liquidation
            buffer = (collateral_ratio - liquidation_threshold) / liquidation_threshold
            
            # Check if risk exceeds threshold
            threshold = RISK_EVENT_TRIGGERS['liquidation_warning_threshold']
            
            if buffer <= threshold:
                event = DeFiEvent(
                    event_id=f"liquidation_risk_{int(time.time())}",
                    event_type='liquidation_warning',
                    protocol=protocol,
                    token=token,
                    severity='high' if buffer <= threshold * 0.5 else 'medium',
                    data={
                        'collateral_ratio': collateral_ratio,
                        'liquidation_threshold': liquidation_threshold,
                        'buffer': buffer,
                        'threshold': threshold
                    },
                    timestamp=datetime.now(),
                    processed=False,
                    action_taken=None
                )
                
                # Add to pending events
                with self.lock:
                    self.pending_events.append(event)
                
                info(f"⚠️ Liquidation risk event triggered: {protocol}:{token} buffer {buffer*100:.2f}%")
                return event.event_id
            
            return "below_threshold"
            
        except Exception as e:
            error(f"Failed to trigger liquidation risk event: {str(e)}")
            return "error"
    
    def trigger_protocol_issue_event(self, protocol: str, issue_type: str, 
                                   severity_score: float, details: Dict[str, Any]) -> str:
        """Trigger protocol issue event"""
        try:
            # Check if severity exceeds threshold
            threshold = RISK_EVENT_TRIGGERS['protocol_issue_threshold']
            
            if severity_score >= threshold:
                event = DeFiEvent(
                    event_id=f"protocol_issue_{int(time.time())}",
                    event_type='protocol_alert',
                    protocol=protocol,
                    token='protocol',
                    severity='critical' if severity_score >= threshold * 1.5 else 'high',
                    data={
                        'issue_type': issue_type,
                        'severity_score': severity_score,
                        'threshold': threshold,
                        'details': details
                    },
                    timestamp=datetime.now(),
                    processed=False,
                    action_taken=None
                )
                
                # Add to pending events
                with self.lock:
                    self.pending_events.append(event)
                
                info(f"🚨 Protocol issue event triggered: {protocol} - {issue_type} (severity: {severity_score:.2f})")
                return event.event_id
            
            return "below_threshold"
            
        except Exception as e:
            error(f"Failed to trigger protocol issue event: {str(e)}")
            return "error"
    
    def trigger_market_condition_event(self, condition_type: str, severity_score: float,
                                     market_data: Dict[str, Any]) -> str:
        """Trigger market condition event"""
        try:
            # Check if severity exceeds threshold
            threshold = RISK_EVENT_TRIGGERS['market_crash_threshold']
            
            if severity_score >= threshold:
                event = DeFiEvent(
                    event_id=f"market_condition_{int(time.time())}",
                    event_type='market_condition',
                    protocol='market',
                    token='market',
                    severity='critical' if severity_score >= threshold * 1.5 else 'high',
                    data={
                        'condition_type': condition_type,
                        'severity_score': severity_score,
                        'threshold': threshold,
                        'market_data': market_data
                    },
                    timestamp=datetime.now(),
                    processed=False,
                    action_taken=None
                )
                
                # Add to pending events
                with self.lock:
                    self.pending_events.append(event)
                
                info(f"🌊 Market condition event triggered: {condition_type} (severity: {severity_score:.2f})")
                return event.event_id
            
            return "below_threshold"
            
        except Exception as e:
            error(f"Failed to trigger market condition event: {str(e)}")
            return "error"
    
    def _process_pending_events(self):
        """Process pending events"""
        try:
            with self.lock:
                if not self.pending_events:
                    return
                
                # Process events (max per cycle)
                events_to_process = self.pending_events[:self.max_events_per_cycle]
                self.pending_events = self.pending_events[self.max_events_per_cycle:]
            
            for event in events_to_process:
                try:
                    # Process event based on type
                    action_taken = self._process_single_event(event)
                    
                    # Update event
                    event.processed = True
                    event.action_taken = action_taken
                    
                    # Add to history
                    with self.lock:
                        self.events_history.append(event)
                    
                    info(f"✅ Event {event.event_id} processed: {action_taken}")
                    
                except Exception as e:
                    error(f"Failed to process event {event.event_id}: {str(e)}")
                    event.processed = True
                    event.action_taken = f"error: {str(e)}"
                    
        except Exception as e:
            error(f"Failed to process pending events: {str(e)}")
    
    def _process_single_event(self, event: DeFiEvent) -> str:
        """Process a single event"""
        try:
            # Get event trigger configuration
            trigger = self.event_triggers.get(event.event_type)
            
            if not trigger or not trigger.enabled:
                return "no_trigger"
            
            # Execute action based on trigger
            if trigger.action == 'optimize_yields':
                return self._execute_yield_optimization(event)
            elif trigger.action == 'assess_opportunity':
                return self._execute_opportunity_assessment(event)
            elif trigger.action == 'risk_assessment':
                return self._execute_risk_assessment(event)
            elif trigger.action == 'add_collateral':
                return self._execute_collateral_addition(event)
            elif trigger.action == 'emergency_stop':
                return self._execute_emergency_stop(event)
            elif trigger.action == 'protocol_review':
                return self._execute_protocol_review(event)
            elif trigger.action == 'reduce_exposure':
                return self._execute_exposure_reduction(event)
            else:
                return f"unknown_action: {trigger.action}"
                
        except Exception as e:
            error(f"Failed to process event {event.event_id}: {str(e)}")
            return f"error: {str(e)}"
    
    def _execute_yield_optimization(self, event: DeFiEvent) -> str:
        """Execute yield optimization action"""
        try:
            # This would integrate with the yield optimizer
            # For now, just log the action
            
            # Send notification
            if self.telegram_bot.enabled:
                self.telegram_bot.send_notification(
                    'info',
                    f"Yield optimization triggered for {event.protocol}:{event.token} due to {event.event_type}"
                )
            
            return "yield_optimization_triggered"
            
        except Exception as e:
            error(f"Failed to execute yield optimization: {str(e)}")
            return f"error: {str(e)}"
    
    def _execute_opportunity_assessment(self, event: DeFiEvent) -> str:
        """Execute opportunity assessment action"""
        try:
            # This would integrate with the yield optimizer
            # For now, just log the action
            
            return "opportunity_assessment_triggered"
            
        except Exception as e:
            error(f"Failed to execute opportunity assessment: {str(e)}")
            return f"error: {str(e)}"
    
    def _execute_risk_assessment(self, event: DeFiEvent) -> str:
        """Execute risk assessment action"""
        try:
            # This would integrate with the risk manager
            # For now, just log the action
            
            # Send notification
            if self.telegram_bot.enabled:
                self.telegram_bot.send_notification(
                    'warning',
                    f"Risk assessment triggered for {event.protocol}:{event.token} due to {event.event_type}"
                )
            
            return "risk_assessment_triggered"
            
        except Exception as e:
            error(f"Failed to execute risk assessment: {str(e)}")
            return f"error: {str(e)}"
    
    def _execute_collateral_addition(self, event: DeFiEvent) -> str:
        """Execute collateral addition action"""
        try:
            # This would integrate with the protocol manager
            # For now, just log the action
            
            # Send critical notification
            if self.telegram_bot.enabled:
                self.telegram_bot.send_notification(
                    'critical',
                    f"🚨 COLLATERAL ADDITION REQUIRED!\n\nProtocol: {event.protocol}\nToken: {event.token}\nBuffer: {event.data.get('buffer', 0)*100:.2f}%\n\nAction required immediately to prevent liquidation!"
                )
            
            return "collateral_addition_triggered"
            
        except Exception as e:
            error(f"Failed to execute collateral addition: {str(e)}")
            return f"error: {str(e)}"
    
    def _execute_emergency_stop(self, event: DeFiEvent) -> str:
        """Execute emergency stop action"""
        try:
            # This would integrate with the risk manager
            # For now, just log the action
            
            # Send critical notification
            if self.telegram_bot.enabled:
                self.telegram_bot.send_notification(
                    'critical',
                    f"🚨 EMERGENCY STOP TRIGGERED!\n\nEvent: {event.event_type}\nSeverity: {event.severity}\n\nAll DeFi operations suspended immediately!"
                )
            
            return "emergency_stop_triggered"
            
        except Exception as e:
            error(f"Failed to execute emergency stop: {str(e)}")
            return f"error: {str(e)}"
    
    def _execute_protocol_review(self, event: DeFiEvent) -> str:
        """Execute protocol review action"""
        try:
            # This would integrate with the protocol manager
            # For now, just log the action
            
            # Send notification
            if self.telegram_bot.enabled:
                self.telegram_bot.send_notification(
                    'warning',
                    f"Protocol review triggered for {event.protocol} due to {event.data.get('issue_type', 'unknown issue')}"
                )
            
            return "protocol_review_triggered"
            
        except Exception as e:
            error(f"Failed to execute protocol review: {str(e)}")
            return f"error: {str(e)}"
    
    def _execute_exposure_reduction(self, event: DeFiEvent) -> str:
        """Execute exposure reduction action"""
        try:
            # This would integrate with the portfolio manager
            # For now, just log the action
            
            # Send notification
            if self.telegram_bot.enabled:
                self.telegram_bot.send_notification(
                    'warning',
                    f"Exposure reduction triggered due to {event.data.get('condition_type', 'market condition')}"
                )
            
            return "exposure_reduction_triggered"
            
        except Exception as e:
            error(f"Failed to execute exposure reduction: {str(e)}")
            return f"error: {str(e)}"
    
    def _cleanup_old_events(self):
        """Clean up old events from history"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.event_retention_hours)
            
            with self.lock:
                # Remove old events
                original_count = len(self.events_history)
                self.events_history = [
                    event for event in self.events_history
                    if event.timestamp > cutoff_time
                ]
                removed_count = original_count - len(self.events_history)
                
                if removed_count > 0:
                    debug(f"🧹 Cleaned up {removed_count} old events")
                    
        except Exception as e:
            error(f"Failed to cleanup old events: {str(e)}")
    
    def get_event_summary(self) -> Dict[str, Any]:
        """Get summary of events"""
        try:
            with self.lock:
                recent_events = [
                    event for event in self.events_history
                    if (datetime.now() - event.timestamp).days < 1
                ]
                
                pending_count = len(self.pending_events)
                
                # Group by type
                events_by_type = {}
                for event in recent_events:
                    event_type = event.event_type
                    if event_type not in events_by_type:
                        events_by_type[event_type] = []
                    events_by_type[event_type].append(event)
                
                # Calculate processing stats
                processed_events = [event for event in recent_events if event.processed]
                processing_rate = len(processed_events) / len(recent_events) if recent_events else 0
                
                return {
                    'total_events_24h': len(recent_events),
                    'pending_events': pending_count,
                    'events_by_type': {event_type: len(events) for event_type, events in events_by_type.items()},
                    'processing_rate': processing_rate,
                    'recent_events': [
                        {
                            'id': event.event_id,
                            'type': event.event_type,
                            'protocol': event.protocol,
                            'severity': event.severity,
                            'processed': event.processed,
                            'action_taken': event.action_taken,
                            'timestamp': event.timestamp.isoformat()
                        }
                        for event in recent_events[-10:]  # Last 10 events
                    ]
                }
                
        except Exception as e:
            error(f"Failed to get event summary: {str(e)}")
            return {'error': str(e)}
    
    def get_event_manager_status(self) -> Dict[str, Any]:
        """Get event manager status"""
        try:
            return {
                'running': self.is_running,
                'event_triggers': len(self.event_triggers),
                'enabled_triggers': len([t for t in self.event_triggers.values() if t.enabled]),
                'pending_events': len(self.pending_events),
                'total_events_history': len(self.events_history),
                'event_retention_hours': self.event_retention_hours,
                'max_events_per_cycle': self.max_events_per_cycle
            }
            
        except Exception as e:
            error(f"Failed to get event manager status: {str(e)}")
            return {'error': str(e)}

# Global instance
_defi_event_manager = None

def get_defi_event_manager() -> DeFiEventManager:
    """Get global DeFi event manager instance"""
    global _defi_event_manager
    if _defi_event_manager is None:
        _defi_event_manager = DeFiEventManager()
    return _defi_event_manager

# Test function
def test_event_manager():
    """Test the DeFi event manager"""
    try:
        event_manager = get_defi_event_manager()
        
        # Test event manager status
        print("📡 Testing DeFi Event Manager...")
        status = event_manager.get_event_manager_status()
        print(f"Event Manager Status: {json.dumps(status, indent=2)}")
        
        # Test yield change event
        print("\n💰 Testing yield change event...")
        event_id = event_manager.trigger_yield_change_event(
            protocol='solend',
            token='USDC',
            old_apy=8.0,
            new_apy=10.0
        )
        print(f"Yield change event ID: {event_id}")
        
        # Test liquidation risk event
        print("\n⚠️ Testing liquidation risk event...")
        event_id = event_manager.trigger_liquidation_risk_event(
            protocol='mango',
            token='SOL',
            collateral_ratio=1.6,
            liquidation_threshold=1.5
        )
        print(f"Liquidation risk event ID: {event_id}")
        
        # Test event summary
        print("\n📊 Testing event summary...")
        summary = event_manager.get_event_summary()
        print(f"Event Summary: {json.dumps(summary, indent=2)}")
        
        print("\n✅ DeFi Event Manager test completed successfully!")
        
    except Exception as e:
        error(f"DeFi Event Manager test failed: {str(e)}")

if __name__ == "__main__":
    # Run test
    test_event_manager()
