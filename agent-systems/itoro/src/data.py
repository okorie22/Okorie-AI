"""
🌙 Anarcho Capital's AI Trading System
Multi-Agent Scheduler with Concurrent Execution
"""

import os
import sys
import signal
import threading
import time
import logging
import socket
import subprocess
from datetime import datetime, timedelta
from typing import Dict
import traceback
import concurrent.futures

# Hacker/AI Theme Colors
class ColorTheme:
    # ANSI Color Codes
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Primary Theme Colors (Green-Black)
    GREEN = '\033[92m'
    GREEN_BRIGHT = '\033[1;92m'
    GREEN_DARK = '\033[32m'
    
    # Accent Colors
    CYAN = '\033[96m'
    CYAN_BRIGHT = '\033[1;96m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    RED = '\033[91m'
    GRAY = '\033[90m'
    
    # Special Effects
    BLINK = '\033[5m'
    UNDERLINE = '\033[4m'
    
    @classmethod
    def print_banner(cls):
        """Print the Data Farm banner with glitch effect"""
        banner = f"""{cls.GREEN_BRIGHT}
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║  {cls.CYAN_BRIGHT}█████╗  █████╗ ████████╗ █████╗             ║
║  {cls.CYAN_BRIGHT}██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗            ║
║  {cls.CYAN_BRIGHT}██║  ██║███████║   ██║   ███████║            ║
║  {cls.CYAN_BRIGHT}██║  ██║██╔══██║   ██║   ██╔══██║            ║
║  {cls.CYAN_BRIGHT}██████╔╝██║  ██║   ██║   ██║  ██║            ║
║  {cls.CYAN_BRIGHT}╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝            ║
║                                                       ║
║  {cls.CYAN_BRIGHT}███████╗ █████╗ ██████╗ ███╗   ███╗             ║
║  {cls.CYAN_BRIGHT}██╔════╝██╔══██╗██╔══██╗████╗ ████║             ║
║  {cls.CYAN_BRIGHT}█████╗  ███████║██████╔╝██╔████╔██║             ║
║  {cls.CYAN_BRIGHT}██╔══╝  ██╔══██║██╔══██╗██║╚██╔╝██║             ║
║  {cls.CYAN_BRIGHT}██║     ██║  ██║██║  ██║██║ ╚═╝ ██║             ║
║  {cls.CYAN_BRIGHT}╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝             ║
║                                                       ║
║  {cls.YELLOW}╔═══════════════════════════════════════════════╗{cls.RESET}  ║
║  {cls.YELLOW}║ {cls.GREEN_BRIGHT}◄◄◄ SOL COLLECTOR v2.0 ►►►{cls.YELLOW}            ║{cls.RESET}  ║
║  {cls.YELLOW}╚═══════════════════════════════════════════════╝{cls.RESET}  ║
╚═══════════════════════════════════════════════════════╝{cls.RESET}
"""
        print(banner)
    
    @classmethod
    def print_loading(cls, step: str, status: str = "OK"):
        """Print loading step with hacker theme"""
        print(f"{cls.GREEN}[→]{cls.RESET} {cls.CYAN}{step:<50}{cls.GRAY}... {cls.GREEN_BRIGHT}{status}{cls.RESET}")
    
    @classmethod
    def print_system_msg(cls, msg: str, icon: str = "▶"):
        """Print system message with theme"""
        print(f"{cls.GREEN}{icon}{cls.RESET} {cls.CYAN}{msg}{cls.RESET}")
    
    @classmethod
    def print_error(cls, msg: str):
        """Print error with theme"""
        print(f"{cls.RED}[✗]{cls.RESET} {cls.YELLOW}{msg}{cls.RESET}")
    
    @classmethod
    def print_success(cls, msg: str):
        """Print success with theme"""
        print(f"{cls.GREEN_BRIGHT}[✓]{cls.RESET} {cls.GREEN}{msg}{cls.RESET}")

def ensure_redis_running(redis_path=None, port=6379):
    """Ensure Redis is running, start it if not"""
    # Check if Redis is already running
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        if result == 0:
            ColorTheme.print_success(f"Redis already running on port {port}")
            return True
    except:
        pass

    # Find Redis executable
    if redis_path is None:
        # Look in common locations
        possible_paths = [
            r"C:\Temp\redis\redis-server.exe",  # Where we installed it
            r"C:\Redis\redis-server.exe",
            r"C:\Program Files\Redis\redis-server.exe"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                redis_path = path
                break

    if not redis_path or not os.path.exists(redis_path):
        ColorTheme.print_error("Redis executable not found. Please install Redis or specify path.")
        print("   Download: https://github.com/microsoftarchive/redis/releases/download/win-3.0.504/Redis-x64-3.0.504.zip")
        return False

    try:
        ColorTheme.print_system_msg(f"Starting Redis server from: {redis_path}", "🚀")
        # Start Redis as background process
        subprocess.Popen(
            [redis_path, "--port", str(port)],
            creationflags=subprocess.CREATE_NO_WINDOW,  # Hide console window
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for Redis to start
        for i in range(10):  # Wait up to 10 seconds
            time.sleep(1)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                if result == 0:
                    ColorTheme.print_success(f"Redis started successfully on port {port}")
                    return True
            except:
                continue

        ColorTheme.print_error("Redis failed to start within timeout")
        return False

    except Exception as e:
        ColorTheme.print_error(f"Failed to start Redis: {e}")
        return False

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Add parent directory to access core module
parent_dir = os.path.dirname(project_root)
sys.path.append(parent_dir)

# Suppress verbose logging during initialization BEFORE any imports
logging.basicConfig(
    level=logging.ERROR, 
    handlers=[],
    force=True
)

# Load environment variables first
from dotenv import load_dotenv
# .env file is in the main ITORO root directory (parent of agent-systems)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Import configuration
from src.config import (
    CHART_ANALYSIS_INTERVAL_MINUTES,
    WHALE_UPDATE_INTERVAL_HOURS,
    TOKEN_ONCHAIN_UPDATE_INTERVAL_MINUTES,
    TOKEN_ONCHAIN_ENABLED,
    OI_CHECK_INTERVAL_HOURS,
    FUNDING_CHECK_INTERVAL_MINUTES
)

# Import agents
from src.agents.chartanalysis_agent import ChartAnalysisAgent
from src.agents.whale_agent import WhaleAgent
from src.agents.oi_agent import OIAgent
from src.agents.funding_agent import FundingAgent

# Get logger for this module
logger = logging.getLogger(__name__)

class MultiAgentScheduler:
    """
    Robust multi-agent scheduler with sequential execution.
    Agents run in order: OnChain → Chart Analysis → Whale, ensuring organized execution.
    """
    
    def __init__(self, silent_init=False):
        self.running = False
        self.agents = {}
        self.agent_locks = {}
        self.agent_status = {}
        self.shutdown_event = threading.Event()
        self.silent_init = silent_init
        
        # Initialize agents
        self._initialize_agents()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        if not silent_init:
            ColorTheme.print_success("Neural network initialization complete")
    
    def _initialize_agents(self):
        """Initialize all agents with their execution methods and intervals"""
        try:
            # Define agent execution order: OI -> Funding -> OnChain -> Chart Analysis -> Whale
            if TOKEN_ONCHAIN_ENABLED:
                self.agent_execution_order = ['oi', 'funding', 'onchain', 'chartanalysis', 'whale']
            else:
                self.agent_execution_order = ['oi', 'funding', 'chartanalysis', 'whale']
            
            # OnChain Agent - runs every hour (THIRD)
            if TOKEN_ONCHAIN_ENABLED:
                from src.agents.onchain_agent import OnChainAgent
                onchain_agent = OnChainAgent()
                self.agents['onchain'] = {
                    'instance': onchain_agent,
                    'interval_minutes': TOKEN_ONCHAIN_UPDATE_INTERVAL_MINUTES,
                    'last_run': None,
                    'next_run': datetime.now() + timedelta(minutes=30),  # Start 30 minutes after launch
                    'execution_method': self._execute_onchain_analysis,
                    'status': 'idle',
                    'error_count': 0,
                    'max_retries': 3,
                    'max_runtime_minutes': 10,
                    'order': 3
                }
            
            # Chart Analysis Agent - runs every hour (FOURTH)
            chart_agent = ChartAnalysisAgent()
            self.agents['chartanalysis'] = {
                'instance': chart_agent,
                'interval_minutes': CHART_ANALYSIS_INTERVAL_MINUTES,
                'last_run': None,
                'next_run': datetime.now() + timedelta(minutes=45),  # Start 45 minutes after launch
                'execution_method': self._execute_chart_analysis,
                'status': 'idle',
                'error_count': 0,
                'max_retries': 3,
                'max_runtime_minutes': 5,  # 5 minutes timeout
                'order': 4
            }
            
            # Whale Agent - runs every 48 hours (FIFTH)
            whale_agent = WhaleAgent()
            self.agents['whale'] = {
                'instance': whale_agent,
                'interval_minutes': WHALE_UPDATE_INTERVAL_HOURS * 60,  # Convert hours to minutes
                'last_run': None,
                'next_run': datetime.now() + timedelta(minutes=60),  # Start 60 minutes after launch
                'execution_method': self._execute_whale_analysis,
                'status': 'idle',
                'error_count': 0,
                'max_retries': 3,
                'max_runtime_minutes': 15,  # 15 minutes timeout
                'order': 5
            }
            
            # OI Agent - runs every 4 hours (FIRST)
            oi_agent = OIAgent()
            self.agents['oi'] = {
                'instance': oi_agent,
                'interval_minutes': OI_CHECK_INTERVAL_HOURS * 60,  # Convert hours to minutes
                'last_run': None,
                'next_run': datetime.now(),  # Start immediately
                'execution_method': self._execute_oi_analysis,
                'status': 'idle',
                'error_count': 0,
                'max_retries': 3,
                'max_runtime_minutes': 10,  # 10 minutes timeout
                'order': 1
            }
            
            # Funding Agent - runs every 2 hours (SECOND)
            funding_agent = FundingAgent()
            self.agents['funding'] = {
                'instance': funding_agent,
                'interval_minutes': FUNDING_CHECK_INTERVAL_MINUTES,  # Already in minutes
                'last_run': None,
                'next_run': datetime.now() + timedelta(minutes=15),  # Start 15 minutes after OI
                'execution_method': self._execute_funding_analysis,
                'status': 'idle',
                'error_count': 0,
                'max_retries': 3,
                'max_runtime_minutes': 10,  # 10 minutes timeout
                'order': 2
            }
            
            # Initialize locks for each agent
            for agent_name in self.agents:
                self.agent_locks[agent_name] = threading.Lock()
                self.agent_status[agent_name] = 'idle'
            
            if not self.silent_init:
                ColorTheme.print_system_msg(f"Initialized {len(self.agents)} neural agents", "✓")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize agents: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _execute_chart_analysis(self, agent_info: Dict) -> bool:
        """Execute chart analysis agent with proper error handling"""
        try:
            logger.info("📊 Starting Chart Analysis Agent execution...")
            start_time = time.time()
            
            # Execute single cycle instead of continuous run
            success = agent_info['instance'].run_single_cycle()
            
            execution_time = time.time() - start_time
            if success:
                logger.info(f"✅ Chart Analysis Agent completed successfully in {execution_time:.2f} seconds")
            else:
                logger.error(f"❌ Chart Analysis Agent failed in {execution_time:.2f} seconds")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Chart Analysis Agent execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _execute_whale_analysis(self, agent_info: Dict) -> bool:
        """Execute whale analysis agent with proper error handling"""
        try:
            logger.info("🐋 Starting Whale Analysis Agent execution...")
            start_time = time.time()
            
            # Execute the agent (whale agent has async run method)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Use execute_now() for single execution instead of run() which loops indefinitely
                success = loop.run_until_complete(agent_info['instance'].execute_now())
            finally:
                loop.close()
            
            execution_time = time.time() - start_time
            if success:
                logger.info(f"✅ Whale Analysis Agent completed successfully in {execution_time:.2f} seconds")
            else:
                logger.error(f"❌ Whale Analysis Agent failed in {execution_time:.2f} seconds")
            return success
            
        except Exception as e:
            logger.error(f"❌ Whale Analysis Agent execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _execute_oi_analysis(self, agent_info: Dict) -> bool:
        """Execute OI agent with proper error handling"""
        try:
            logger.info("📊 Starting OI Agent execution...")
            start_time = time.time()
            
            # Execute single monitoring cycle
            agent_info['instance'].run_monitoring_cycle()
            
            execution_time = time.time() - start_time
            logger.info(f"✅ OI Agent completed successfully in {execution_time:.2f} seconds")
            return True
            
        except Exception as e:
            logger.error(f"❌ OI Agent execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _execute_funding_analysis(self, agent_info: Dict) -> bool:
        """Execute Funding agent with proper error handling"""
        try:
            logger.info("💰 Starting Funding Agent execution...")
            start_time = time.time()
            
            # Execute single monitoring cycle
            agent_info['instance'].run_monitoring_cycle()
            
            execution_time = time.time() - start_time
            logger.info(f"✅ Funding Agent completed successfully in {execution_time:.2f} seconds")
            return True
            
        except Exception as e:
            logger.error(f"❌ Funding Agent execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _execute_onchain_analysis(self, agent_info: Dict) -> bool:
        """Execute on-chain data agent"""
        try:
            logger.info("\033[0;34m🔗 Starting OnChain Agent execution...\033[0m")
            start_time = time.time()
            
            agent_info['instance'].run_single_cycle()
            
            execution_time = time.time() - start_time
            logger.info(f"\033[0;34m✅ OnChain Agent completed in {execution_time:.2f}s\033[0m")
            return True
            
        except Exception as e:
            logger.error(f"\033[0;34m❌ OnChain Agent failed: {str(e)}\033[0m")
            logger.error(traceback.format_exc())
            return False
    
    def _should_run_agent(self, agent_name: str, agent_info: Dict) -> bool:
        """Check if an agent should run based on its schedule"""
        now = datetime.now()
        
        # Check if it's time to run
        if now >= agent_info['next_run']:
            # Check if agent is not currently running
            if agent_info['status'] == 'idle':
                return True
            # If agent is running but has been running too long, force timeout
            elif agent_info['status'] == 'running':
                if 'start_time' in agent_info:
                    running_time = (now - agent_info['start_time']).total_seconds()
                    max_runtime = agent_info.get('max_runtime_minutes', 15) * 60  # Default 15 minutes
                    if running_time > max_runtime:
                        logger.warning(f"⚠️ {agent_name} has been running for {running_time/60:.1f} minutes, forcing timeout")
                        agent_info['status'] = 'idle'
                        agent_info['error_count'] = agent_info.get('error_count', 0) + 1
                        return True
                else:
                    # If no start_time recorded, assume it's been running too long
                    logger.warning(f"⚠️ {agent_name} has been running without start_time, forcing timeout")
                    agent_info['status'] = 'idle'
                    agent_info['error_count'] = agent_info.get('error_count', 0) + 1
                    return True
        
        return False
    
    def _update_agent_schedule(self, agent_name: str, agent_info: Dict, success: bool):
        """Update agent schedule and status after execution"""
        now = datetime.now()
        
        # Update last run time
        agent_info['last_run'] = now
        
        # Calculate next run time
        interval_minutes = agent_info['interval_minutes']
        agent_info['next_run'] = now + timedelta(minutes=interval_minutes)
        
        # Update status and clear start time
        agent_info['status'] = 'idle'
        if 'start_time' in agent_info:
            del agent_info['start_time']
        
        # Update error count
        if success:
            agent_info['error_count'] = 0
        else:
            agent_info['error_count'] += 1
            
            # If too many errors, delay next run
            if agent_info['error_count'] >= agent_info['max_retries']:
                delay_minutes = min(interval_minutes * 2, 60)  # Max 1 hour delay
                agent_info['next_run'] = now + timedelta(minutes=delay_minutes)
                logger.warning(f"⚠️ {agent_name} has failed {agent_info['error_count']} times. "
                             f"Delaying next run by {delay_minutes} minutes")
        
        logger.debug(f"📅 {agent_name} next run scheduled for {agent_info['next_run'].strftime('%H:%M:%S')}")
    
    def _execute_agent_safely(self, agent_name: str, agent_info: Dict):
        """Execute an agent sequentially with proper error handling and timeout"""
        # Check if agent is already running
        if agent_info['status'] == 'running':
            logger.warning(f"⚠️ {agent_name} is already running, skipping this execution")
            return
        
        try:
            # Update status and track start time
            agent_info['status'] = 'running'
            agent_info['start_time'] = datetime.now()
            logger.info(f"🚀 Starting {agent_name} execution...")
            
            # Execute the agent with timeout protection
            max_runtime = agent_info.get('max_runtime_minutes', 15) * 60  # Convert to seconds
            
            def execute_with_timeout():
                return agent_info['execution_method'](agent_info)
            
            # Use threading with timeout to prevent infinite loops
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(execute_with_timeout)
                try:
                    success = future.result(timeout=max_runtime)
                except concurrent.futures.TimeoutError:
                    logger.error(f"⏰ {agent_name} execution timed out after {max_runtime/60:.1f} minutes")
                    success = False
                except Exception as e:
                    logger.error(f"❌ {agent_name} execution failed: {str(e)}")
                    success = False
            
            # Update schedule
            self._update_agent_schedule(agent_name, agent_info, success)
            
            # Print status after agent completes
            self._print_status()
            
        except Exception as e:
            logger.error(f"❌ Unexpected error in {agent_name} execution: {str(e)}")
            logger.error(traceback.format_exc())
            self._update_agent_schedule(agent_name, agent_info, False)
            
            # Print status even on error
            self._print_status()
    

    
    def _monitor_agents(self):
        """Monitor and schedule agent executions sequentially"""
        while not self.shutdown_event.is_set():
            try:
                # Check agents in order: chartanalysis -> sentiment -> whale
                for agent_name in self.agent_execution_order:
                    if self.shutdown_event.is_set():
                        break
                        
                    agent_info = self.agents[agent_name]
                    
                    logger.debug(f"🔍 Checking {agent_name}: status={agent_info['status']}, next_run={agent_info['next_run']}")
                    
                    if self._should_run_agent(agent_name, agent_info):
                        logger.info(f"🔄 Starting sequential execution: {agent_name}")
                        self._execute_agent_safely(agent_name, agent_info)
                        
                        # Wait a moment between agents for clean separation
                        time.sleep(2)
                
                # Sleep for a short interval to prevent excessive CPU usage
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in agent monitoring: {str(e)}")
                time.sleep(30)  # Wait longer on error
    
    def _print_status(self):
        """Print current agent status with hacker theme"""
        C = ColorTheme
        now = datetime.now()
        width = 55  # Match banner width
        
        # Header
        print(f"\n{C.GREEN_BRIGHT}╔{'═'*width}╗{C.RESET}")
        print(f"{C.GREEN_BRIGHT}║{C.CYAN} ◄► DATA FARM - NEURAL LINK ◄►{' '*(width-27)}║{C.RESET}")
        print(f"{C.GREEN_BRIGHT}╠{'═'*width}╣{C.RESET}")
        print(f"{C.GREEN_BRIGHT}║{C.GRAY} [●] TIME: {C.CYAN}{now.strftime('%H:%M:%S')}{' '*(width-22)}║{C.RESET}")
        
        # System Status Bar
        status_bar = "█" * 35 if self.running else "░" * 35
        remaining_space = width - (13 + 35)  # 13 for "[⚠] STATUS: ", 35 for bar
        print(f"{C.GREEN_BRIGHT}║{C.GRAY} [⚠] STATUS: {C.GREEN_BRIGHT}{status_bar}{' '*remaining_space}║{C.RESET}")
        
        # Agent Count
        active_count = sum(1 for name in self.agent_execution_order if self.agents[name]['status'] == 'running')
        agent_text = f"[🔗] NODES: {C.YELLOW}{len(self.agents)}{C.RESET} ({C.GREEN}{active_count}{C.RESET})"
        remaining_space = width - (len(agent_text) - len(C.YELLOW) - len(C.GREEN) - len(C.RESET) - len(C.RESET)) - 2
        print(f"{C.GREEN_BRIGHT}║{C.GRAY} {agent_text}{' '*remaining_space}║{C.RESET}")
        print(f"{C.GREEN_BRIGHT}╠{'═'*width}╣{C.RESET}")
        print(f"{C.GREEN_BRIGHT}║{C.YELLOW} ▶ NEURAL EXECUTION QUEUE{' '*(width-28)}║{C.RESET}")
        print(f"{C.GREEN_BRIGHT}╠{'═'*width}╣{C.RESET}")
        
        # Agent Status Display
        for agent_name in self.agent_execution_order:
            agent_info = self.agents[agent_name]
            
            # Status icon and color
            if agent_info['status'] == 'idle':
                status_icon = "🟢"
                status_color = C.GREEN
                status_text = "IDLE"
            elif agent_info['status'] == 'running':
                status_icon = "🟡"
                status_color = C.YELLOW
                status_text = "RUN"
            else:
                status_icon = "🔴"
                status_color = C.RED
                status_text = "ERR"
            
            # Format next run time
            if agent_info['next_run']:
                time_until = agent_info['next_run'] - now
                if time_until.total_seconds() > 0:
                    time_str = str(time_until).split('.')[0]
                    hours = time_str.split(':')[0]
                    mins = time_str.split(':')[1]
                    next_run_str = f"{hours}:{mins}"
                else:
                    next_run_str = "NOW"
                    status_color = C.RED
            else:
                next_run_str = "N/A"
            
            # Execution order
            order_num = agent_info.get('order', 0)
            
            # Error count (compact)
            error_str = f" {C.RED}({agent_info['error_count']}){C.RESET}" if agent_info['error_count'] > 0 else ""
            
            # Print formatted line (compact layout)
            line = f"{C.GREEN_BRIGHT}║{C.RESET} {status_icon} {C.CYAN}[{order_num}]{C.RESET}{C.YELLOW}{agent_name[:8].upper():>8}{C.RESET} {status_color}{status_text:>4}{C.RESET} {C.GREEN}{next_run_str:>5}{C.RESET}{error_str}"
            # Pad to width
            actual_length = len(line) - (len(C.GREEN_BRIGHT) + len(C.RESET) + len(C.CYAN) + len(C.YELLOW) + len(C.GREEN)) + 4  # Account for ANSI codes
            print(line + ' ' * (width - actual_length - 2) + f"{C.GREEN_BRIGHT}║{C.RESET}")
        
        print(f"{C.GREEN_BRIGHT}╚{'═'*width}╝{C.RESET}")
        print(f"{C.GRAY}💡 {C.YELLOW}'s'{C.GRAY} status | {C.YELLOW}'q'{C.GRAY} quit | {C.YELLOW}'h'{C.GRAY} help{C.RESET}\n")
    
    def _status_monitor(self):
        """Background monitor thread (status now prints after each agent completes)"""
        while not self.shutdown_event.is_set():
            try:
                # Status is now printed after each agent completes
                # This thread just keeps running in case we need it for other monitoring
                time.sleep(60)

            except Exception as e:
                logger.error(f"❌ Error in status monitor: {str(e)}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
        self.shutdown()
    
    def start(self):
        """Start the multi-agent scheduler"""
        if self.running:
            logger.warning("⚠️ Scheduler is already running")
            return
        
        try:
            self.running = True
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self._monitor_agents,
                name="AgentMonitor",
                daemon=True
            )
            monitor_thread.start()
            
            # Start status monitor thread
            status_thread = threading.Thread(
                target=self._status_monitor,
                name="StatusMonitor",
                daemon=True
            )
            status_thread.start()
            
            # Print initial status with theme
            self._print_status()
            
            # Main loop with user input handling
            self._main_loop()
            
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _main_loop(self):
        """Main loop for user interaction and system monitoring"""
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Check for user input (non-blocking)
                    import msvcrt
                    if msvcrt.kbhit():
                        user_input = msvcrt.getch().decode('utf-8').lower()
                        
                        if user_input == 'q':
                            print(f"\n{ColorTheme.YELLOW}[👋] User requested shutdown{ColorTheme.RESET}")
                            break
                        elif user_input == 's':
                            self._print_status()
                        elif user_input == 'h':
                            C = ColorTheme
                            width = 55
                            print(f"\n{C.CYAN}╔{'═'*width}╗{C.RESET}")
                            print(f"{C.CYAN}║{C.YELLOW} 💡 COMMANDS{' '*(width-13)}║{C.RESET}")
                            print(f"{C.CYAN}╠{'═'*width}╣{C.RESET}")
                            print(f"{C.CYAN}║  {C.GREEN}'s'{C.RESET} - status{' '*(width-14)}║{C.RESET}")
                            print(f"{C.CYAN}║  {C.GREEN}'q'{C.RESET} - quit{' '*(width-13)}║{C.RESET}")
                            print(f"{C.CYAN}║  {C.GREEN}'h'{C.RESET} - help{' '*(width-13)}║{C.RESET}")
                            print(f"{C.CYAN}╚{'═'*width}╝{C.RESET}\n")
                    
                    # Sleep briefly to prevent excessive CPU usage
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {str(e)}")
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("👋 Keyboard interrupt received")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown the scheduler and all agents"""
        if not self.running:
            return
        
        logger.info("🔄 Initiating graceful shutdown...")
        self.running = False
        self.shutdown_event.set()
        
        try:
            # Wait for any running agent to complete
            logger.info("⏳ Waiting for running agents to complete...")
            
            # Wait up to 30 seconds for agents to finish
            shutdown_timeout = 30
            start_time = time.time()
            
            while time.time() - start_time < shutdown_timeout:
                running_agents = [
                    name for name, info in self.agents.items() 
                    if info['status'] == 'running'
                ]
                
                if not running_agents:
                    break
                
                logger.info(f"⏳ Waiting for agents to complete: {', '.join(running_agents)}")
                time.sleep(2)
            
            logger.info("✅ Multi-Agent Scheduler shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {str(e)}")
    
    def get_agent_status(self) -> Dict:
        """Get current status of all agents"""
        status = {}
        for agent_name, agent_info in self.agents.items():
            status[agent_name] = {
                'status': agent_info['status'],
                'last_run': agent_info['last_run'],
                'next_run': agent_info['next_run'],
                'error_count': agent_info['error_count'],
                'interval_minutes': agent_info['interval_minutes']
            }
        return status

def main():
    """Main entry point with hacker theme"""
    try:
        # Clear screen for clean start
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Print the banner
        ColorTheme.print_banner()

        # Ensure Redis is running before starting data collection
        print(f"\n{ColorTheme.CYAN_BRIGHT}Checking Redis infrastructure...{ColorTheme.RESET}")
        if not ensure_redis_running():
            ColorTheme.print_error("Cannot start Data Farm without Redis. Please install Redis and try again.")
            print(f"{ColorTheme.GRAY}Redis is required for real-time agent communication.{ColorTheme.RESET}")
            sys.exit(1)
        print()

        # Animated loading sequence
        print(f"\n{ColorTheme.YELLOW}Initializing Data Farm Neural Network...{ColorTheme.RESET}\n")
        time.sleep(0.3)
        
        ColorTheme.print_loading("Loading neural drivers", "OK")
        time.sleep(0.2)
        
        ColorTheme.print_loading("Connecting to data streams", "OK")
        time.sleep(0.2)
        
        ColorTheme.print_loading("Syncing agent modules", "OK")
        time.sleep(0.2)
        
        ColorTheme.print_loading("Building execution queue", "OK")
        time.sleep(0.2)
        
        # Create scheduler silently
        scheduler = MultiAgentScheduler(silent_init=True)
        time.sleep(0.2)
        
        ColorTheme.print_loading("Activating neural nodes", "OK")
        time.sleep(0.2)
        
        print(f"\n{ColorTheme.GREEN_BRIGHT}[✓] Farm ready! Starting neural harness...{ColorTheme.RESET}\n")
        time.sleep(0.5)
        
        # Start the scheduler
        scheduler.start()
        
    except KeyboardInterrupt:
        print(f"\n{ColorTheme.YELLOW}[!] User interrupt detected. Shutting down...{ColorTheme.RESET}")
        sys.exit(0)
    except Exception as e:
        ColorTheme.print_error(f"Fatal error in main: {str(e)}")
        print(f"{ColorTheme.GRAY}{traceback.format_exc()}{ColorTheme.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
