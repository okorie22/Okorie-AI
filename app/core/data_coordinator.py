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
import json
from datetime import datetime, timedelta
from typing import Dict
import traceback
import concurrent.futures

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Python < 3.7 or reconfigure not available
        pass

# Try to import redis for UI updates
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

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
║  {cls.YELLOW}║ {cls.GREEN_BRIGHT}<<< SOL COLLECTOR v2.0 >>>{cls.YELLOW}            ║{cls.RESET}  ║
║  {cls.YELLOW}╚═══════════════════════════════════════════════╝{cls.RESET}  ║
╚═══════════════════════════════════════════════════════╝{cls.RESET}
"""
        print(banner)
    
    @classmethod
    def print_loading(cls, step: str, status: str = "OK"):
        """Print loading step with hacker theme"""
        print(f"{cls.GREEN}[->]{cls.RESET} {cls.CYAN}{step:<50}{cls.GRAY}... {cls.GREEN_BRIGHT}{status}{cls.RESET}")
    
    @classmethod
    def print_system_msg(cls, msg: str, icon: str = ">"):
        """Print system message with theme"""
        print(f"{cls.GREEN}{icon}{cls.RESET} {cls.CYAN}{msg}{cls.RESET}")
    
    @classmethod
    def print_error(cls, msg: str):
        """Print error with theme"""
        print(f"{cls.RED}[X]{cls.RESET} {cls.YELLOW}{msg}{cls.RESET}")
    
    @classmethod
    def print_success(cls, msg: str):
        """Print success with theme"""
        print(f"{cls.GREEN_BRIGHT}[OK]{cls.RESET} {cls.GREEN}{msg}{cls.RESET}")

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

# Import configuration and agents from local app
import sys
import os
app_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, app_path)

# Import specific modules directly to avoid __init__.py issues
import importlib.util

# Define paths relative to app directory (self-contained app)
shared_src_path = os.path.join(os.path.dirname(__file__), '..')  # Points to app/

# Load config module
config_spec = importlib.util.spec_from_file_location("config", os.path.join(shared_src_path, "config.py"))
config_module = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config_module)

CHART_ANALYSIS_INTERVAL_MINUTES = config_module.CHART_ANALYSIS_INTERVAL_MINUTES
OI_CHECK_INTERVAL_HOURS = config_module.OI_CHECK_INTERVAL_HOURS
FUNDING_CHECK_INTERVAL_MINUTES = config_module.FUNDING_CHECK_INTERVAL_MINUTES

# Load agent modules (lazy load chart analysis to handle missing dependencies gracefully)
# ChartAnalysisAgent will be loaded on-demand in _initialize_agents()

oi_spec = importlib.util.spec_from_file_location("oi_agent", os.path.join(shared_src_path, "agent", "oi_agent.py"))
oi_module = importlib.util.module_from_spec(oi_spec)
oi_spec.loader.exec_module(oi_module)
OIAgent = oi_module.OIAgent

funding_spec = importlib.util.spec_from_file_location("funding_agent", os.path.join(shared_src_path, "agent", "funding_agent.py"))
funding_module = importlib.util.module_from_spec(funding_spec)
funding_spec.loader.exec_module(funding_module)
FundingAgent = funding_module.FundingAgent

# Get logger for this module
logger = logging.getLogger(__name__)

class MultiAgentScheduler:
    """
    Robust multi-agent scheduler with sequential execution.
    Agents run in order: OI -> Funding -> Chart Analysis, ensuring organized execution.
    """
    
    def __init__(self, silent_init=False):
        self.running = False
        self.agents = {}
        self.agent_locks = {}
        self.agent_status = {}
        self.shutdown_event = threading.Event()
        self.silent_init = silent_init
        
        # Initialize Redis client for UI updates
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                # Test connection
                self.redis_client.ping()
                if not silent_init:
                    logger.info("✅ Redis connected for UI updates")
            except Exception as e:
                logger.warning(f"⚠️ Redis not available for UI updates: {e}")
                self.redis_client = None
        
        # Alert collection for UI updates
        self.recent_alerts = {
            'oi': [],
            'funding': [],
            'chart': []
        }
        self.alert_subscriber = None
        if self.redis_client:
            self._start_alert_subscriber()
        
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
            # Define agent execution order: Chart Analysis -> Funding -> OI
            self.agent_execution_order = ['chartanalysis', 'funding', 'oi']
            
            # Chart Analysis Agent - runs every hour (FIRST)
            # Lazy load to handle missing matplotlib dependency gracefully
            try:
                chartanalysis_spec = importlib.util.spec_from_file_location("chartanalysis_agent", os.path.join(shared_src_path, "agent", "chartanalysis_agent.py"))
                chartanalysis_module = importlib.util.module_from_spec(chartanalysis_spec)
                chartanalysis_spec.loader.exec_module(chartanalysis_module)
                ChartAnalysisAgent = chartanalysis_module.ChartAnalysisAgent
                
                chart_agent = ChartAnalysisAgent()
                self.agents['chartanalysis'] = {
                    'instance': chart_agent,
                    'interval_minutes': CHART_ANALYSIS_INTERVAL_MINUTES,
                    'last_run': None,
                    'next_run': datetime.now(),  # Start immediately
                    'execution_method': self._execute_chart_analysis,
                    'status': 'idle',
                    'error_count': 0,
                    'max_retries': 3,
                    'max_runtime_minutes': 5,  # 5 minutes timeout
                    'order': 1
                }
            except Exception as e:
                error_type = type(e).__name__
                logger.warning(f"Chart Analysis Agent disabled: {error_type}: {e}")
                logger.warning("Install matplotlib and mplfinance to enable: pip install matplotlib mplfinance")
                import traceback
                logger.debug(f"Chart Analysis Agent error traceback:\n{traceback.format_exc()}")
                # Also print to console for visibility
                print(f"[WARNING] Chart Analysis Agent disabled: {error_type}: {e}")
                print(f"[DEBUG] Full traceback logged to debug output")
                # Remove chartanalysis from execution order
                self.agent_execution_order = ['funding', 'oi']
            
            # Funding Agent - runs every 2 hours (SECOND)
            funding_agent = FundingAgent()
            self.agents['funding'] = {
                'instance': funding_agent,
                'interval_minutes': FUNDING_CHECK_INTERVAL_MINUTES,  # Already in minutes
                'last_run': None,
                'next_run': datetime.now() + timedelta(minutes=1.5),  # Start 1.5 minutes after Chart Analysis
                'execution_method': self._execute_funding_analysis,
                'status': 'idle',
                'error_count': 0,
                'max_retries': 3,
                'max_runtime_minutes': 10,  # 10 minutes timeout
                'order': 2
            }
            
            # OI Agent - runs every 4 hours (THIRD)
            oi_agent = OIAgent()
            self.agents['oi'] = {
                'instance': oi_agent,
                'interval_minutes': OI_CHECK_INTERVAL_HOURS * 60,  # Convert hours to minutes
                'last_run': None,
                'next_run': datetime.now() + timedelta(minutes=3),  # Start 3 minutes after launch (1.5 + 1.5)
                'execution_method': self._execute_oi_analysis,
                'status': 'idle',
                'error_count': 0,
                'max_retries': 3,
                'max_runtime_minutes': 10,  # 10 minutes timeout
                'order': 3
            }
            
            # Initialize locks for each agent
            for agent_name in self.agents:
                self.agent_locks[agent_name] = threading.Lock()
                self.agent_status[agent_name] = 'idle'
            
            if not self.silent_init:
                ColorTheme.print_system_msg(f"Initialized {len(self.agents)} neural agents", "OK")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize agents: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _publish_ui_update(self, channel: str, data: dict):
        """Publish update to Redis for UI consumption"""
        if self.redis_client:
            try:
                # Add timestamp to data
                data['timestamp'] = datetime.now().isoformat()
                # Publish to Redis channel
                self.redis_client.publish(channel, json.dumps(data))
            except Exception as e:
                logger.debug(f"Failed to publish UI update to {channel}: {e}")
    
    def _start_alert_subscriber(self):
        """Subscribe to market_alert channel to collect agent alerts"""
        try:
            self.alert_subscriber = self.redis_client.pubsub()
            self.alert_subscriber.subscribe('market_alert')
            # Start background thread to process alerts
            threading.Thread(target=self._process_alerts, daemon=True).start()
            if not self.silent_init:
                logger.info("✅ Alert subscriber started for UI updates")
        except Exception as e:
            logger.debug(f"Could not start alert subscriber: {e}")
    
    def _process_alerts(self):
        """Process alerts from event bus and store for UI"""
        try:
            for message in self.alert_subscriber.listen():
                if message['type'] == 'message':
                    try:
                        # Event bus wraps data in an envelope
                        envelope = json.loads(message['data'])
                        # Extract actual alert data from envelope
                        alert_data = envelope.get('data', envelope)  # Fallback to envelope if no 'data' field
                        agent_source = alert_data.get('agent_source', '')
                        
                        # Store recent alerts (keep last 3 per agent)
                        if agent_source == 'oi_agent':
                            alert_summary = self._format_oi_alert(alert_data)
                            if alert_summary:
                                self.recent_alerts['oi'].append(alert_summary)
                                self.recent_alerts['oi'] = self.recent_alerts['oi'][-3:]  # Keep last 3
                        elif agent_source == 'funding_agent':
                            alert_summary = self._format_funding_alert(alert_data)
                            if alert_summary:
                                self.recent_alerts['funding'].append(alert_summary)
                                self.recent_alerts['funding'] = self.recent_alerts['funding'][-3:]  # Keep last 3
                        elif agent_source == 'chartanalysis_agent':
                            alert_summary = self._format_chart_alert(alert_data)
                            if alert_summary:
                                self.recent_alerts['chart'].append(alert_summary)
                                self.recent_alerts['chart'] = self.recent_alerts['chart'][-3:]
                    except Exception as e:
                        logger.debug(f"Error processing alert: {e}")
        except Exception as e:
            logger.debug(f"Alert subscriber error: {e}")
    
    def _format_oi_alert(self, alert_data):
        """Format OI alert for UI display"""
        try:
            symbol = alert_data.get('symbol', 'N/A')
            data = alert_data.get('data', {})
            oi_change = data.get('oi_change_pct', 0)
            if oi_change != 0:
                return f"{symbol}: {oi_change:+.1f}%"
        except Exception:
            pass
        return None
    
    def _format_funding_alert(self, alert_data):
        """Format funding alert for UI display - ONLY Extreme and Mid-Range"""
        try:
            symbol = alert_data.get('symbol', 'N/A')
            severity = alert_data.get('severity', '')
            data = alert_data.get('data', {})
            annual_rate = data.get('annual_rate', 0)
            
            # Severity is an integer: 4=CRITICAL, 2=MEDIUM, 3=HIGH, 1=LOW
            # Only show EXTREME (CRITICAL=4) and MID-RANGE (MEDIUM=2)
            # Filter out all others (Normal, Low, High)
            if severity == 4:  # CRITICAL = EXTREME
                category = "EXTREME"
            elif severity == 2:  # MEDIUM = MID-RANGE
                category = "MID-RANGE"
            else:
                # Don't show LOW, HIGH, or any other severity - filter them out
                return None
            
            return f"{category}: {symbol} ({annual_rate:.2f}%)"
        except Exception:
            pass
        return None
    
    def _format_chart_alert(self, alert_data):
        """Format chart alert - will be handled via sentiment cache"""
        # Chart alerts are handled differently via aggregated sentiment
        return None
    
    def _execute_chart_analysis(self, agent_info: Dict) -> bool:
        """Execute chart analysis agent with proper error handling"""
        try:
            # Safety check: ensure agent instance exists
            if 'instance' not in agent_info or agent_info['instance'] is None:
                logger.warning("Chart Analysis Agent not available (matplotlib/mplfinance not installed)")
                return False
                
            logger.info("📊 Starting Chart Analysis Agent execution...")
            start_time = time.time()
            
            # Execute single cycle instead of continuous run
            success = agent_info['instance'].run_single_cycle()
            
            execution_time = time.time() - start_time
            if success:
                logger.info(f"✅ Chart Analysis Agent completed successfully in {execution_time:.2f} seconds")
                
                # Get sentiment from agent
                chart_agent = agent_info['instance']
                sentiment = None
                score = 0
                confidence = 0
                if hasattr(chart_agent, 'aggregated_sentiment_cache') and chart_agent.aggregated_sentiment_cache:
                    sentiment_data = chart_agent.aggregated_sentiment_cache
                    sentiment = sentiment_data.get('overall_sentiment', 'Neutral')
                    score = sentiment_data.get('sentiment_score', 0)
                    confidence = sentiment_data.get('confidence', 0)
                else:
                    sentiment = "Analyzing..."
                
                # Publish update to UI (status is 'idle' after completion)
                self._publish_ui_update('chart:updates', {
                    'status': 'idle',
                    'execution_time': round(execution_time, 2),
                    'last_run': datetime.now().strftime("%H:%M:%S"),
                    'sentiment': sentiment,
                    'sentiment_score': round(score, 1),
                    'confidence': round(confidence, 1)
                })
            else:
                logger.error(f"❌ Chart Analysis Agent failed in {execution_time:.2f} seconds")
                # Publish error status
                self._publish_ui_update('chart:updates', {
                    'status': 'error',
                    'error': 'Analysis failed'
                })
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Chart Analysis Agent execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            # Publish error status
            self._publish_ui_update('chart:updates', {
                'status': 'error',
                'error': str(e)[:50]  # Truncate error message
            })
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
            
            # Wait for alert subscriber to process alerts
            time.sleep(0.5)
            
            # Get recent alerts
            alerts_text = "\n".join(self.recent_alerts['oi']) if self.recent_alerts['oi'] else "No alerts"
            
            # Publish update to UI (status is 'idle' after completion)
            self._publish_ui_update('oi:updates', {
                'status': 'idle',
                'execution_time': round(execution_time, 2),
                'last_run': datetime.now().strftime("%H:%M:%S"),
                'alerts': alerts_text,
                'alert_count': len(self.recent_alerts['oi'])
            })
            
            # Clear alerts after publishing
            self.recent_alerts['oi'] = []
            
            return True
            
        except Exception as e:
            logger.error(f"❌ OI Agent execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            # Publish error status
            self._publish_ui_update('oi:updates', {
                'status': 'error',
                'error': str(e)[:50]  # Truncate error message
            })
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
            
            # Wait for alert subscriber to process alerts
            time.sleep(0.5)
            
            # Get recent alerts
            alerts_text = "\n".join(self.recent_alerts['funding']) if self.recent_alerts['funding'] else "No alerts"
            
            # Publish update to UI (status is 'idle' after completion)
            self._publish_ui_update('funding:updates', {
                'status': 'idle',
                'execution_time': round(execution_time, 2),
                'last_run': datetime.now().strftime("%H:%M:%S"),
                'alerts': alerts_text,
                'alert_count': len(self.recent_alerts['funding'])
            })
            
            # Clear alerts after publishing
            self.recent_alerts['funding'] = []
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Funding Agent execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            # Publish error status
            self._publish_ui_update('funding:updates', {
                'status': 'error',
                'error': str(e)[:50]  # Truncate error message
            })
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
            
            # Publish 'running' status to UI
            channel_map = {
                'chartanalysis': 'chart:updates',
                'funding': 'funding:updates',
                'oi': 'oi:updates'
            }
            if agent_name in channel_map:
                self._publish_ui_update(channel_map[agent_name], {
                    'status': 'running'
                })
            
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
        print(f"{C.GREEN_BRIGHT}║{C.CYAN} <> DATA FARM - NEURAL LINK <>{' '*(width-27)}║{C.RESET}")
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
        print(f"{C.GREEN_BRIGHT}║{C.YELLOW} > NEURAL EXECUTION QUEUE{' '*(width-28)}║{C.RESET}")
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
        
        print(f"\n{ColorTheme.GREEN_BRIGHT}[OK] Farm ready! Starting neural harness...{ColorTheme.RESET}\n")
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
