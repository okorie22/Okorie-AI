#!/usr/bin/env python3
"""
🧪 Anarcho Capital's DeFi Lab
Leverage Loops & Yield Optimization Automation
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import signal
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from termcolor import colored, cprint

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.agents.defi_agent import get_defi_agent
    from src.agents.staking_agent import StakingAgent
    from src.scripts.defi.defi_event_manager import get_defi_event_manager
    from src.scripts.utilities.telegram_bot import get_telegram_bot
    
    # Import from config/defi_config.py (note the path)
    import importlib.util
    defi_config_path = project_root / "src" / "config" / "defi_config.py"
    spec = importlib.util.spec_from_file_location("defi_config", defi_config_path)
    defi_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(defi_config)
    validate_telegram_config = defi_config.validate_telegram_config
    get_current_phase_config = defi_config.get_current_phase_config
    
    from src.scripts.shared_services.logger import info, warning, error, critical, system
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    print("Please ensure all dependencies are installed and the src directory is accessible")
    sys.exit(1)

class DeFiSystemLauncher:
    """Launcher for the complete DeFi automation system"""
    
    def __init__(self):
        """Initialize the launcher"""
        self.defi_agent = None
        self.staking_agent = None
        self.staking_thread = None
        self.event_manager = None
        self.telegram_bot = None
        self.is_running = False
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        info("🚀 DeFi System Launcher initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        info(f"📡 Received signal {signum}, shutting down gracefully...")
        self.shutdown()
        sys.exit(0)
    
    def validate_system(self) -> bool:
        """Validate system configuration and dependencies"""
        try:
            print()
            print_section("🔍", "Validating System Configuration")
            
            # Check Telegram configuration
            if not validate_telegram_config():
                cprint("   ⚠️  Telegram bot configuration incomplete", 'yellow', attrs=['bold'])
                cprint("      Some features will be disabled", 'yellow')
            else:
                cprint("   ✅ Telegram configuration valid", 'green', attrs=['bold'])
            
            # Check current phase configuration
            current_phase = get_current_phase_config()
            cprint(f"   📊 Phase: {current_phase['allocation_percentage']*100:.1f}% allocation", 'cyan', attrs=['bold'])
            cprint(f"   🔒 Protocols: {', '.join(current_phase['protocols'])}", 'cyan', attrs=['bold'])
            
            # Check environment variables
            required_vars = ['TELEGRAM_BOT_API']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                cprint(f"   ⚠️  Missing: {', '.join(missing_vars)}", 'yellow', attrs=['bold'])
            else:
                cprint("   ✅ Environment variables configured", 'green', attrs=['bold'])
            
            print()
            cprint("   ✅ System validation completed", 'green', attrs=['bold'])
            time.sleep(0.5)
            print()
            
            return True
            
        except Exception as e:
            cprint(f"❌ System validation failed: {str(e)}", 'red', attrs=['bold'])
            return False
    
    def start_system(self) -> bool:
        """Start the complete DeFi system"""
        try:
            if self.is_running:
                warning("System is already running")
                return False
            
            # PHASE 1: Initialize Staking Agent
            print_section("💎", "Module 1 • Staking Engine")
            self.staking_agent = StakingAgent()
            # Start the staking agent in a background thread
            self.staking_thread = threading.Thread(target=self.staking_agent.run, daemon=True)
            self.staking_thread.start()
            time.sleep(1.5)  # Allow initialization messages to complete
            cprint("      ✅ Staking engine online", 'green', attrs=['bold'])
            time.sleep(0.3)
            print()
            
            # PHASE 2: Initialize Event Manager
            print_section("🌊", "Module 2 • Event Manager")
            self.event_manager = get_defi_event_manager()
            time.sleep(1.5)  # Allow initialization messages to complete
            cprint("      ✅ Communication array active", 'green', attrs=['bold'])
            time.sleep(0.3)
            print()
            
            # PHASE 3: Initialize Telegram Bot
            print_section("📱", "Module 3 • Command Center")
            self.telegram_bot = get_telegram_bot()
            time.sleep(1.5)  # Allow initialization messages to complete
            cprint("      ✅ Bridge established", 'green', attrs=['bold'])
            time.sleep(0.3)
            print()
            
            # PHASE 4: Initialize DeFi Agent
            print_section("🤖", "Module 4 • DeFi Core")
            self.defi_agent = get_defi_agent()
            time.sleep(2.0)  # Allow initialization messages to complete
            cprint("      ✅ AI navigation systems ready", 'green', attrs=['bold'])
            time.sleep(0.3)
            print()
            
            # PHASE 5: Set up coordination
            print_section("⚡", "Module 5 • Coordinated Systems")
            from src.scripts.defi.staking_defi_coordinator import get_staking_defi_coordinator
            coordinator = get_staking_defi_coordinator()
            coordinator.register_defi_agent(self.defi_agent)
            time.sleep(0.5)  # Allow initialization messages to complete
            cprint("      ✅ All systems interconnected", 'green', attrs=['bold'])
            time.sleep(0.3)
            print()
            
            print()
            cprint("╔══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
            cprint("║    🌴 Engaging Vice City Mode • Strap In! 🔥                 ║", 'yellow', attrs=['bold'])
            cprint("╚══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
            print()
            
            # Start event manager first
            cprint("   🌊 Powering communication array...", 'cyan', attrs=['bold'])
            self.event_manager.start_event_processing()
            time.sleep(0.5)  # Allow messages to complete
            cprint("      ✅ Signal active • Listening for events", 'green', attrs=['bold'])
            print()
            
            # Start DeFi agent  
            cprint("   🚀 Activating DeFi core...", 'cyan', attrs=['bold'])
            self.defi_agent.start()
            time.sleep(0.5)  # Allow messages to complete
            cprint("      ✅ AI navigation online • Autopilot engaged", 'green', attrs=['bold'])
            print()
            
            # Start Telegram bot if enabled
            if self.telegram_bot.enabled:
                cprint("   📱 Opening command channel...", 'cyan', attrs=['bold'])
                self.telegram_bot.start_bot()
                time.sleep(0.5)  # Allow messages to complete
                cprint("      ✅ Bridge connected • Command center ready", 'green', attrs=['bold'])
                print()
            
            self.is_running = True
            
            print()
            cprint("╔══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
            cprint("║    💜 Funk lab Operational • Systems Nominal 🔥              ║", 'cyan', attrs=['bold'])
            cprint("╚══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
            print()
            
            # Display system status
            self._display_system_status()
            
            return True
            
        except Exception as e:
            error(f"❌ Failed to start DeFi system: {str(e)}")
            return False
    
    def _display_system_status(self):
        """Display current system status"""
        try:
            print()
            cprint("╔══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
            cprint("║    🏙️ Funk lab Dashboard • Vice City 🏙️           ║", 'cyan', attrs=['bold'])
            cprint("╚══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
            print()
            
            # Agent status
            if self.defi_agent:
                agent_status = self.defi_agent.get_agent_status()
                status_icon = '✅' if agent_status.get('running') else '❌'
                cprint(f"   {status_icon} DeFi Core: {'Online' if agent_status.get('running') else 'Offline'}", 'cyan', attrs=['bold'])
                cprint(f"      Power: {agent_status.get('current_phase', {}).get('allocation_percentage', 0)*100:.1f}% active", 'magenta', attrs=['bold'])
                em_stop = '🔴 EMERGENCY' if agent_status.get('emergency_stop_active') else '🟢 Nominal'
                cprint(f"      Status: {em_stop}", 'yellow', attrs=['bold'])
                print()
            
            # Staking agent status
            cprint(f"   💎 Staking Module: Docked", 'cyan', attrs=['bold'])
            cprint(f"      Schedule: 3-day intervals • Ready for deployment", 'magenta', attrs=['bold'])
            print()
            
            # Event manager status
            if self.event_manager:
                try:
                    event_status = self.event_manager.get_event_manager_status()
                    status_icon = '🌊' if event_status.get('running') else '📵'
                    cprint(f"   {status_icon} Communication: {'Active' if event_status.get('running') else 'Offline'}", 'cyan', attrs=['bold'])
                    cprint(f"      Sensors: {event_status.get('enabled_triggers', 0)}/{event_status.get('event_triggers', 0)} online", 'magenta', attrs=['bold'])
                except:
                    cprint("   ⚠️  Communication: Status unknown", 'yellow', attrs=['bold'])
                print()
            
            # Coordination status
            cprint(f"   ⚡ Mission Control: Active", 'cyan', attrs=['bold'])
            cprint(f"      Navigation → stSOL → Leverage systems engaged", 'magenta', attrs=['bold'])
            cprint(f"      Scan frequency: 3x daily (8am • 4pm • midnight)", 'magenta', attrs=['bold'])
            print()
            
            cprint("╔══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
            cprint("║  💜 Press Ctrl+C for emergency exit • Cruise mode active ⚡ ║", 'cyan', attrs=['bold'])
            cprint("╚══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
            print()
            
        except Exception as e:
            error(f"Failed to display system status: {str(e)}")
    
    def run_system(self):
        """Run the system in the main loop"""
        try:
            if not self.start_system():
                error("Failed to start system")
                return False
            
            cprint("🔄 Funk lab in cruise mode • Scanning for yield opportunities...", 'cyan', attrs=['bold'])
            print()
            
            # Main loop
            while self.is_running:
                try:
                    # Check system health every 30 seconds
                    time.sleep(30)
                    
                    # Display periodic status
                    if self.is_running:
                        self._display_periodic_status()
                    
                except KeyboardInterrupt:
                    cprint("\n🛑 Emergency exit initiated", 'yellow', attrs=['bold'])
                    break
                except Exception as e:
                    error(f"Error in main loop: {str(e)}")
                    time.sleep(10)
            
            return True
            
        except Exception as e:
            error(f"System run failed: {str(e)}")
            return False
        finally:
            self.shutdown()
    
    def _display_periodic_status(self):
        """Display periodic system status"""
        try:
            # Get recent operations
            if self.defi_agent:
                operations_summary = self.defi_agent.get_operations_summary()
                if 'total_operations' in operations_summary:
                    total_ops = operations_summary['total_operations']
                    if total_ops > 0:
                        info(f"📈 Operations: {total_ops} total operations performed")
            
            # Get recent events
            if self.event_manager:
                event_summary = self.event_manager.get_event_summary()
                if 'total_events_24h' in event_summary:
                    total_events = event_summary['total_events_24h']
                    if total_events > 0:
                        info(f"📡 Events: {total_events} events processed in last 24h")
            
        except Exception as e:
            error(f"Failed to display periodic status: {str(e)}")
    
    def shutdown(self):
        """Shutdown the system gracefully"""
        try:
            print()
            cprint("╔══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
            cprint("║        🌴 Initiating shutdown • Saving data 🌴               ║", 'yellow', attrs=['bold'])
            cprint("╚══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
            print()
            
            # Stop components in reverse order
            if self.defi_agent:
                cprint("   🤖 Powering down DeFi core...", 'cyan', attrs=['bold'])
                self.defi_agent.stop()
                cprint("      ✅ AI systems offline", 'green', attrs=['bold'])
            
            if self.staking_agent:
                cprint("   💎 Docking staking engine...", 'cyan', attrs=['bold'])
                self.staking_agent.stop()
                # Wait for the thread to finish
                if self.staking_thread and self.staking_thread.is_alive():
                    self.staking_thread.join(timeout=10)
                cprint("      ✅ Module secured", 'green', attrs=['bold'])
            
            if self.event_manager:
                cprint("   🌊 Closing communication channels...", 'cyan', attrs=['bold'])
                self.event_manager.stop_event_processing()
                cprint("      ✅ Signals terminated", 'green', attrs=['bold'])
            
            if self.telegram_bot:
                cprint("   📱 Disconnecting command center...", 'cyan', attrs=['bold'])
                self.telegram_bot.stop_bot()
                cprint("      ✅ Bridge offline", 'green', attrs=['bold'])
            
            self.is_running = False
            
            print()
            cprint("╔══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
            cprint("║      💜 Shutdown Complete • Mission Data Saved 💜           ║", 'cyan', attrs=['bold'])
            cprint("╚══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
            print()
            
        except Exception as e:
            error(f"Error during shutdown: {str(e)}")

def print_banner():
    """Print Vice City Funk lab banner"""
    # Hot pink/purple themed banner
    print()
    cprint("╔═══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
    cprint("║                                                                ║", 'magenta', attrs=['bold'])
    cprint("║   ", 'magenta', attrs=['bold'], end='')
    cprint("███████╗██╗   ██╗███╗   ██╗██╗  ██╗   ██╗     █████╗ ██████╗ ", 'cyan', attrs=['bold'], end='')
    cprint("║", 'magenta', attrs=['bold'])
    cprint("║   ", 'magenta', attrs=['bold'], end='')
    cprint("██╔════╝██║   ██║████╗  ██║██║ ██╔╝   ██║    ██╔══██╗██╔══██╗", 'cyan', attrs=['bold'], end='')
    cprint("💜", 'magenta', attrs=['bold'], end='')
    cprint(" ║", 'magenta', attrs=['bold'])
    cprint("║   ", 'magenta', attrs=['bold'], end='')
    cprint("█████╗  ██║   ██║██╔██╗ ██║█████╔╝    ██║    ███████║██████╔╝", 'cyan', attrs=['bold'], end='')
    cprint("🏙️", 'yellow', attrs=['bold'], end='')
    cprint(" ║", 'magenta', attrs=['bold'])
    cprint("║   ", 'magenta', attrs=['bold'], end='')
    cprint("██╔══╝  ██║   ██║██║╚██╗██║██╔═██╗    ██║    ██╔══██║██╔══██╗", 'cyan', attrs=['bold'], end='')
    cprint("⚡", 'yellow', attrs=['bold'], end='')
    cprint(" ║", 'magenta', attrs=['bold'])
    cprint("║   ", 'magenta', attrs=['bold'], end='')
    cprint("██║     ╚██████╔╝██║ ╚████║██║  ██╗    ███████╗██║  ██║██████╔╝", 'cyan', attrs=['bold'], end='')
    cprint("🔥", 'yellow', attrs=['bold'], end='')
    cprint(" ║", 'magenta', attrs=['bold'])
    cprint("║                                                                ║", 'magenta', attrs=['bold'])
    cprint("╚═══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
    print()
    cprint("            " + colored("╔══════════════════════════════════════╗", 'yellow', attrs=['bold']), 'white')
    cprint("            " + colored("║", 'yellow', attrs=['bold']) + "  " + colored("💜 Funk lab 💜", 'magenta', attrs=['bold', 'blink']) + "  " + colored("║", 'yellow', attrs=['bold']) + "     w/ love Okem", 'cyan')
    cprint("            " + colored("╚══════════════════════════════════════╝", 'yellow', attrs=['bold']), 'white')
    print()
    cprint("                    🌴 Vice City Edition  🌴", 'cyan', attrs=['bold'])
    cprint("      " + colored("⬡", 'magenta', attrs=['bold']) + " Leverage Loops • AI Trading • Yield Maximization " + colored("⬡", 'magenta', attrs=['bold']), 'cyan', attrs=['bold'])
    print()
    
def print_init_header():
    """Print initialization header"""
    print()
    cprint("╔══════════════════════════════════════════════════════════════╗", 'magenta', attrs=['bold'])
    cprint("║      🌴 Funk lab • Vice City Edition • Loading 🌴           ║", 'cyan', attrs=['bold'])
    cprint("╚══════════════════════════════════════════════════════════════╝", 'magenta', attrs=['bold'])
    print()

def print_section(emoji, title):
    """Print section header"""
    cprint(f"   {emoji}  ", 'yellow', attrs=['bold'], end='')
    cprint(f"{title}", 'magenta', attrs=['bold'])

def main():
    """Main entry point"""
    try:
        # Clear screen and print banner
        os.system('cls' if os.name == 'nt' else 'clear')
        print_banner()
        print_init_header()
        
        # Create and run launcher
        launcher = DeFiSystemLauncher()
        
        # Validate system
        if not launcher.validate_system():
            cprint("🛑 System validation failed - exiting", 'red', attrs=['bold'])
            sys.exit(1)
        
        # Run system
        if not launcher.run_system():
            cprint("🛑 System run failed - exiting", 'red', attrs=['bold'])
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n🌴 Shutdown requested by user")
    except Exception as e:
        error(f"🛑 Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
