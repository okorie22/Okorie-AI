"""
🌊 Liquidation Agent - Clean Dashboard Version
Simple visual dashboard that clears and redraws
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.liquidation_agent import LiquidationAgent
from src import config


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def create_dashboard_text(agent, last_check_time, next_check_time, cycle_count, alert_count):
    """Create the dashboard as plain text"""
    
    lines = []
    lines.append("╔═══════════════════════════════════════════════════════════════════╗")
    lines.append("║               🌊 LIQUIDATION MONITOR DASHBOARD 🌊                 ║")
    lines.append("╚═══════════════════════════════════════════════════════════════════╝")
    lines.append("")
    
    # Symbol status
    lines.append("┌─────────────────────────────────────────────────────────────────┐")
    lines.append("│  Symbol  │      Status      │  Last Activity  │                  │")
    lines.append("├─────────────────────────────────────────────────────────────────┤")
    
    symbols = ['BTC', 'ETH', 'SOL']
    icons = {'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎'}
    
    for symbol in symbols:
        symbol_key = f"{symbol}_{config.LIQUIDATION_CHECK_INTERVAL // 60}m"
        
        if symbol_key in agent.previous_values:
            prev_data = agent.previous_values[symbol_key]
            longs = prev_data.get('longs', 0)
            shorts = prev_data.get('shorts', 0)
            timestamp = prev_data.get('timestamp', datetime.now())
            
            if longs > 0 or shorts > 0:
                status = "🟢 ACTIVE"
                activity = timestamp.strftime("%H:%M:%S")
            else:
                status = "🟡 WAITING"
                activity = "No data"
        else:
            status = "🟡 WAITING"
            activity = "No data"
        
        lines.append(f"│ {icons[symbol]} {symbol:<6} │  {status:<14}  │   {activity:<11}   │                  │")
    
    lines.append("└─────────────────────────────────────────────────────────────────┘")
    lines.append("")
    
    # Status info
    lines.append("┌─────────────────────────────────────────────────────────────────┐")
    lines.append("│                        SYSTEM STATUS                            │")
    lines.append("├─────────────────────────────────────────────────────────────────┤")
    
    last_str = last_check_time.strftime("%H:%M:%S") if last_check_time else "N/A"
    next_str = next_check_time.strftime("%H:%M:%S") if next_check_time else "N/A"
    
    lines.append(f"│  Last Check: {last_str}  │  Next Check: {next_str}             │")
    lines.append(f"│  Cycles: {cycle_count:<3}  │  Alerts: {alert_count:<3}  │  Interval: {config.LIQUIDATION_CHECK_INTERVAL}s          │")
    lines.append("└─────────────────────────────────────────────────────────────────┘")
    lines.append("")
    lines.append("         [🟢] Monitoring... Press Ctrl+C to stop")
    lines.append("")
    
    return "\n".join(lines)


def main():
    """Main entry point for liquidation launcher"""
    
    # Wait for imports to complete, then clear
    time.sleep(2)
    clear_screen()
    
    print("🌊 Initializing Liquidation Monitor...")
    print("Please wait...")
    
    # Initialize agent
    agent = LiquidationAgent()
    
    check_interval = config.LIQUIDATION_CHECK_INTERVAL
    last_check_time = None
    next_check_time = datetime.now()
    cycle_count = 0
    alert_count = 0
    
    # Clear and start monitoring
    clear_screen()
    
    try:
        while True:
            # Display dashboard
            clear_screen()
            dashboard = create_dashboard_text(agent, last_check_time, next_check_time, cycle_count, alert_count)
            print(dashboard)
            
            # Run monitoring cycle if it's time
            if datetime.now() >= next_check_time:
                # Run cycle
                last_check_time = datetime.now()
                next_check_time = last_check_time + timedelta(seconds=check_interval)
                
                # The agent will print its logs, which will scroll up
                agent.run_monitoring_cycle()
                cycle_count += 1
                
                # Wait a bit then redraw dashboard
                time.sleep(2)
            
            # Update every 5 seconds instead of every second (less flashing)
            time.sleep(5)
            
    except KeyboardInterrupt:
        clear_screen()
        print("\n[SHUTDOWN] Liquidation Monitor stopped\n")


if __name__ == "__main__":
    main()
