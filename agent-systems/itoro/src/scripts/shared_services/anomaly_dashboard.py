"""
Anomaly Detection Dashboard
Event-driven visual dashboard for monitoring multiple anomaly detection agents
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import queue
import threading
from datetime import datetime
from collections import deque
from typing import Dict, Any, Optional

from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console, Group
from rich.text import Text
from rich import box

console = Console()


class AnomalyDashboard:
    """
    Event-driven dashboard for anomaly detection agents
    Updates only when agents report events
    """
    
    def __init__(self, event_queue: queue.Queue):
        """Initialize dashboard with event queue"""
        self.event_queue = event_queue
        self.running = False
        self.last_update = datetime.now()
        
        # Agent status tracking
        self.agent_status = {
            'oi': {
                'last_run': None,
                'next_run': None,
                'status': 'STARTING',
                'metrics': {},
                'symbols': {'BTC': '0.0%', 'ETH': '0.0%', 'SOL': '0.0%'}
            },
            'funding': {
                'last_run': None,
                'next_run': None,
                'status': 'STARTING',
                'metrics': {},
                'symbols': {'BTC': '0.0%', 'ETH': '0.0%', 'SOL': '0.0%'}
            },
            'liquidation': {
                'last_run': None,
                'next_run': None,
                'status': 'STARTING',
                'metrics': {},
                'symbols': {'BTC': 'NORMAL', 'ETH': 'NORMAL', 'SOL': 'NORMAL'}
            },
            'collector': {
                'status': 'STARTING',
                'data_points': 0,
                'connected': False
            }
        }
        
        # Alert log (last 10 events)
        self.alert_log = deque(maxlen=10)
        self.alert_count_today = 0
        
        # System stats
        self.system_start_time = datetime.now()
        self.total_scans = 0
        
    def update_agent_status(self, agent_name: str, status_data: Dict[str, Any]):
        """Update status for a specific agent"""
        if agent_name in self.agent_status:
            self.agent_status[agent_name].update(status_data)
            self.last_update = datetime.now()
    
    def add_alert(self, message: str, level: str = 'INFO'):
        """Add message to alert log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.alert_log.append(f"{timestamp} | {message}")
        
        if level in ['ALERT', 'WARNING']:
            self.alert_count_today += 1
        
        self.last_update = datetime.now()
    
    def render_dashboard(self):
        """Render the complete dashboard using rich"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create header
        header = Text(f"🌐 Anomaly Detection Hub v2.0", style="bold cyan")
        header_panel = Panel(
            Text(f"Last Update: {current_time}", style="dim"),
            title=header,
            border_style="cyan"
        )
        
        # Create agent grid
        agent_grid = self._render_agent_grid_rich()
        
        # Create system status
        system_status = self._render_system_status_rich()
        
        # Create alert log
        alert_log = self._render_alert_log_rich()
        
        # Create footer
        footer = self._render_footer_rich()
        
        # Combine all elements
        dashboard = Group(
            header_panel,
            agent_grid,
            system_status,
            alert_log,
            footer
        )
        
        return dashboard
    
    def _render_agent_grid_rich(self):
        """Render the 3-column agent status grid using rich"""
        # Get status for each agent
        oi = self.agent_status['oi']
        funding = self.agent_status['funding']
        liq = self.agent_status['liquidation']
        
        # Create table
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
        table.add_column("OI MONITOR", style="cyan", justify="left")
        table.add_column("FUNDING MONITOR", style="green", justify="left")
        table.add_column("LIQUIDATION MONITOR", style="yellow", justify="left")
        
        # Symbol rows
        symbols = ['BTC', 'ETH', 'SOL']
        icons = {'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎'}
        
        for symbol in symbols:
            oi_val = oi['symbols'].get(symbol, '0.0%')
            funding_val = funding['symbols'].get(symbol, '0.0%')
            liq_val = liq['symbols'].get(symbol, 'NORMAL')
            
            # Color code liquidation status
            liq_style = "green" if liq_val == 'NORMAL' else ("yellow" if liq_val == 'WARNING' else "red")
            
            table.add_row(
                f"{icons[symbol]} {symbol}: {oi_val}",
                f"{icons[symbol]} {symbol}: {funding_val}",
                Text(f"{icons[symbol]} {symbol}: {liq_val}", style=liq_style)
            )
        
        # Next check times
        oi_next = oi['next_run'].strftime('%H:%M:%S') if oi['next_run'] else 'Pending'
        funding_next = funding['next_run'].strftime('%H:%M:%S') if funding['next_run'] else 'Pending'
        liq_next = liq['next_run'].strftime('%H:%M:%S') if liq['next_run'] else 'Pending'
        
        table.add_row(
            f"Next: {oi_next}",
            f"Next: {funding_next}",
            f"Next: {liq_next}",
            style="dim"
        )
        
        return table
    
    def _render_system_status_rich(self):
        """Render system status bar using rich"""
        collector = self.agent_status['collector']
        collector_status = Text("🟢 RUNNING", style="green") if collector['connected'] else Text("🔴 OFFLINE", style="red")
        
        # Check if any agent is active
        agents_active = any(
            self.agent_status[agent]['status'] == 'ACTIVE' 
            for agent in ['oi', 'funding', 'liquidation']
        )
        agent_status = Text("🟢 ACTIVE", style="green") if agents_active else Text("🟡 STARTING", style="yellow")
        
        # Create status content
        status_text = Text()
        status_text.append("Collector: ")
        status_text.append(collector_status)
        status_text.append(" | Agents: ")
        status_text.append(agent_status)
        status_text.append(f" | Alerts Today: {self.alert_count_today}\n")
        status_text.append(f"Data Quality: ")
        status_text.append(Text("🟢 EXCELLENT", style="green"))
        status_text.append(f" | Scans: {self.total_scans}")
        
        return Panel(status_text, title="SYSTEM STATUS", border_style="blue")
    
    def _render_alert_log_rich(self):
        """Render alert log using rich"""
        if self.alert_log:
            alerts = "\n".join(list(self.alert_log)[-5:])  # Show last 5
        else:
            alerts = "No alerts yet"
        
        return Panel(Text(alerts, style="dim"), title="ALERT LOG", border_style="magenta")
    
    def _render_footer_rich(self):
        """Render footer with system status using rich"""
        uptime = datetime.now() - self.system_start_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        footer = Text()
        footer.append("[🟢] ", style="green bold")
        footer.append(f"All Systems Monitoring... | Uptime: {uptime_str} | Press Ctrl+C to stop", style="dim")
        
        return footer
    
    def process_event(self, event: Dict[str, Any]):
        """Process an event from the queue"""
        event_type = event.get('type')
        agent_name = event.get('agent')
        
        if event_type == 'cycle_start':
            self.agent_status[agent_name]['status'] = 'RUNNING'
            self.agent_status[agent_name]['last_run'] = datetime.now()
            self.agent_status[agent_name]['next_run'] = event.get('next_run')
            self.add_alert(f"{agent_name.upper()} Agent: Cycle started")
            
        elif event_type == 'cycle_complete':
            self.agent_status[agent_name]['status'] = 'ACTIVE'
            self.agent_status[agent_name]['metrics'] = event.get('metrics', {})
            
            # Update symbol data
            if 'symbols' in event:
                self.agent_status[agent_name]['symbols'] = event['symbols']
            
            self.total_scans += 1
            self.add_alert(f"{agent_name.upper()} Agent: Cycle completed successfully")
            
        elif event_type == 'alert':
            alert_msg = event.get('message', 'Unknown alert')
            level = event.get('level', 'INFO')
            self.add_alert(f"🚨 {agent_name.upper()}: {alert_msg}", level)
            
        elif event_type == 'error':
            error_msg = event.get('message', 'Unknown error')
            self.add_alert(f"❌ {agent_name.upper()}: {error_msg}", 'ERROR')
            self.agent_status[agent_name]['status'] = 'ERROR'
            
        elif event_type == 'collector_status':
            self.agent_status['collector']['connected'] = event.get('connected', False)
            self.agent_status['collector']['data_points'] = event.get('data_points', 0)
            
            if event.get('connected'):
                self.add_alert("Liquidation Collector: Connected to exchanges")
    
    def run(self):
        """Main dashboard loop - event-driven with fallback refresh using rich.Live"""
        self.running = True
        self.add_alert("System initialized successfully")
        
        # Use rich.Live for persistent display
        with Live(self.render_dashboard(), refresh_per_second=1, screen=False) as live:
            while self.running:
                try:
                    # Wait for event with 5s timeout (frequent refresh for smooth updates)
                    try:
                        event = self.event_queue.get(timeout=5)
                        self.process_event(event)
                    except queue.Empty:
                        pass  # Just refresh on timeout
                    
                    # Update the live display
                    live.update(self.render_dashboard())
                    
                except KeyboardInterrupt:
                    self.running = False
                    break
                except Exception as e:
                    self.add_alert(f"Dashboard error: {str(e)}", 'ERROR')
                    time.sleep(1)
        
        # Cleanup
        console.print("\n[yellow]Dashboard shutting down...[/yellow]")


if __name__ == "__main__":
    # Test dashboard with mock data
    test_queue = queue.Queue()
    dashboard = AnomalyDashboard(test_queue)
    
    # Simulate some events
    def mock_events():
        time.sleep(2)
        test_queue.put({
            'type': 'cycle_start',
            'agent': 'oi',
            'next_run': datetime.now()
        })
        
        time.sleep(3)
        test_queue.put({
            'type': 'cycle_complete',
            'agent': 'oi',
            'metrics': {'records': 10},
            'symbols': {'BTC': '+2.1%', 'ETH': '-1.8%', 'SOL': '+0.5%'}
        })
    
    # Start mock events in background
    threading.Thread(target=mock_events, daemon=True).start()
    
    # Run dashboard
    try:
        dashboard.run()
    except KeyboardInterrupt:
        print("\nTest completed")

