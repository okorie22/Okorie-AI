"""
Agent Reporter
Bridge between agents and the anomaly dashboard
Built with love by Anarcho Capital 🚀
"""

import queue
from datetime import datetime
from typing import Dict, Any, Optional


class AgentReporter:
    """
    Non-blocking reporter for sending agent status to dashboard
    Thread-safe communication using queue
    """
    
    def __init__(self, agent_name: str, event_queue: queue.Queue):
        """
        Initialize reporter for a specific agent
        
        Args:
            agent_name: Name of the agent ('oi', 'funding', 'liquidation', 'collector')
            event_queue: Shared queue for sending events to dashboard
        """
        self.agent_name = agent_name
        self.event_queue = event_queue
    
    def report_cycle_start(self, next_run_time: Optional[datetime] = None):
        """
        Report that an agent cycle has started
        
        Args:
            next_run_time: When the next cycle will run
        """
        try:
            self.event_queue.put_nowait({
                'type': 'cycle_start',
                'agent': self.agent_name,
                'timestamp': datetime.now(),
                'next_run': next_run_time
            })
        except queue.Full:
            pass  # Non-blocking - drop event if queue is full
    
    def report_cycle_complete(self, metrics: Dict[str, Any] = None, symbols: Dict[str, str] = None):
        """
        Report that an agent cycle has completed
        
        Args:
            metrics: Dictionary of metrics from the cycle
            symbols: Dictionary of symbol-specific data (e.g., {'BTC': '+2.1%'})
        """
        try:
            event = {
                'type': 'cycle_complete',
                'agent': self.agent_name,
                'timestamp': datetime.now(),
                'metrics': metrics or {}
            }
            
            if symbols:
                event['symbols'] = symbols
            
            self.event_queue.put_nowait(event)
        except queue.Full:
            pass
    
    def report_alert(self, message: str, level: str = 'ALERT', alert_data: Dict[str, Any] = None):
        """
        Report an alert/anomaly detection
        
        Args:
            message: Alert message
            level: Alert level ('INFO', 'ALERT', 'WARNING', 'ERROR')
            alert_data: Additional data about the alert
        """
        try:
            event = {
                'type': 'alert',
                'agent': self.agent_name,
                'timestamp': datetime.now(),
                'message': message,
                'level': level
            }
            
            if alert_data:
                event['data'] = alert_data
            
            self.event_queue.put_nowait(event)
        except queue.Full:
            pass
    
    def report_error(self, error_message: str, exception: Exception = None):
        """
        Report an error
        
        Args:
            error_message: Description of the error
            exception: Exception object if available
        """
        try:
            event = {
                'type': 'error',
                'agent': self.agent_name,
                'timestamp': datetime.now(),
                'message': error_message
            }
            
            if exception:
                event['exception'] = str(exception)
            
            self.event_queue.put_nowait(event)
        except queue.Full:
            pass
    
    def report_status(self, status: str, **kwargs):
        """
        Report general status update
        
        Args:
            status: Status message
            **kwargs: Additional status data
        """
        try:
            event = {
                'type': 'status',
                'agent': self.agent_name,
                'timestamp': datetime.now(),
                'status': status
            }
            event.update(kwargs)
            
            self.event_queue.put_nowait(event)
        except queue.Full:
            pass
    
    def report_collector_status(self, connected: bool, data_points: int = 0, exchanges: list = None):
        """
        Report liquidation collector status (special case)
        
        Args:
            connected: Whether collector is connected to exchanges
            data_points: Number of data points collected
            exchanges: List of connected exchanges
        """
        try:
            event = {
                'type': 'collector_status',
                'agent': self.agent_name,
                'timestamp': datetime.now(),
                'connected': connected,
                'data_points': data_points
            }
            
            if exchanges:
                event['exchanges'] = exchanges
            
            self.event_queue.put_nowait(event)
        except queue.Full:
            pass


class NullReporter(AgentReporter):
    """
    Null reporter for standalone agent execution
    Does nothing - allows agents to run without dashboard
    """
    
    def __init__(self):
        """Initialize null reporter (no queue needed)"""
        self.agent_name = 'standalone'
        self.event_queue = None
    
    def report_cycle_start(self, next_run_time: Optional[datetime] = None):
        pass
    
    def report_cycle_complete(self, metrics: Dict[str, Any] = None, symbols: Dict[str, str] = None):
        pass
    
    def report_alert(self, message: str, level: str = 'ALERT', alert_data: Dict[str, Any] = None):
        pass
    
    def report_error(self, error_message: str, exception: Exception = None):
        pass
    
    def report_status(self, status: str, **kwargs):
        pass
    
    def report_collector_status(self, connected: bool, data_points: int = 0, exchanges: list = None):
        pass


if __name__ == "__main__":
    # Test reporter
    import time
    
    test_queue = queue.Queue()
    reporter = AgentReporter('test_agent', test_queue)
    
    # Send some events
    reporter.report_cycle_start(next_run_time=datetime.now())
    reporter.report_cycle_complete(
        metrics={'records': 10, 'anomalies': 2},
        symbols={'BTC': '+5.2%', 'ETH': '-3.1%'}
    )
    reporter.report_alert("Test alert detected!", level='ALERT')
    reporter.report_error("Test error occurred")
    
    # Check queue
    print(f"Queue size: {test_queue.qsize()}")
    while not test_queue.empty():
        event = test_queue.get()
        print(f"Event: {event['type']} from {event['agent']}")
    
    print("Reporter test completed")

