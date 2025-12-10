"""
🐋 Whale Agent Module
Tracks and ranks top-performing cryptocurrency wallets from gmgn.ai
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import json
import csv
import time
import logging
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import backoff
import threading
import schedule

# Third-party imports
from apify_client import ApifyClient
from apify_client.clients.base.actor_job_base_client import ActorJobStatus
try:
    import schedule
except ImportError:
    print("schedule library not found. Installing...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'schedule'])
    import schedule

# Local imports
try:
    from .base_agent import BaseAgent
    from ..config import (
        APIFY_API_TOKEN, APIFY_ACTOR_ID, APIFY_DEFAULT_INPUT,
        WHALE_SCORING_WEIGHTS, WHALE_THRESHOLDS,
        WHALE_DATA_DIR, WHALE_RANKED_FILE, WHALE_HISTORY_FILE,
        WHALE_UPDATE_INTERVAL_HOURS, WHALE_MAX_STORED_WALLETS,
        WHALE_HISTORY_MAX_RECORDS, WHALE_HISTORY_RETENTION_DAYS,
        LOG_LEVEL, LOG_TO_FILE, LOG_DIRECTORY
    )
    from ..integration.core_bridge import publish_whale_rankings
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.agents.base_agent import BaseAgent
    from src.config import (
        APIFY_API_TOKEN, APIFY_ACTOR_ID, APIFY_DEFAULT_INPUT,
        WHALE_SCORING_WEIGHTS, WHALE_THRESHOLDS,
        WHALE_DATA_DIR, WHALE_RANKED_FILE, WHALE_HISTORY_FILE,
        WHALE_UPDATE_INTERVAL_HOURS, WHALE_MAX_STORED_WALLETS,
        WHALE_HISTORY_MAX_RECORDS, WHALE_HISTORY_RETENTION_DAYS,
        LOG_LEVEL, LOG_TO_FILE, LOG_DIRECTORY
    )
    from src.integration.core_bridge import publish_whale_rankings

# Cloud database import
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False

# Configure logging
# logging.basicConfig(
#     level=getattr(logging, LOG_LEVEL),
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )  # Removed - main logger configured in src/scripts/shared_services/logger.py
logger = logging.getLogger(__name__)

@dataclass
class WhaleWallet:
    """Data class for whale wallet information"""
    address: str
    twitter_handle: str
    pnl_30d: float
    pnl_7d: float
    pnl_1d: float
    winrate_7d: float
    txs_30d: int
    token_active: int
    last_active: str
    is_blue_verified: bool
    avg_holding_period_7d: float
    score: float
    rank: int
    last_updated: str
    is_active: bool = True

class WhaleAgent(BaseAgent):
    """
    Whale Agent for tracking and ranking top-performing cryptocurrency wallets
    """
    
    def __init__(self):
        """Initialize the Whale Agent"""
        super().__init__("whale_agent")

        # Load all available API tokens
        self.apify_tokens = []
        for i in range(1, 4):  # Support up to 3 tokens
            token_key = f'APIFY_API_TOKEN_{i}' if i > 1 else 'APIFY_API_TOKEN'
            token = os.getenv(token_key)
            if token:
                self.apify_tokens.append(token)
                logger.info(f"🐋 Loaded {token_key}")

        # Validate we have at least one API token
        if not self.apify_tokens:
            raise ValueError("At least one APIFY_API_TOKEN environment variable is required")

        # Initialize Apify client with first token
        self.current_token_index = 0
        self.apify_client = ApifyClient(self.apify_tokens[self.current_token_index])
        
        # Data storage paths
        self.data_dir = Path(WHALE_DATA_DIR)
        self.ranked_file = self.data_dir / WHALE_RANKED_FILE
        self.history_file = self.data_dir / WHALE_HISTORY_FILE
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize data structures
        self.ranked_wallets: Dict[str, WhaleWallet] = {}
        self.wallet_history: List[Dict] = []
        
        # Load existing data
        self._load_existing_data()
        
        # Update tracking
        self.last_update = None
        self.update_interval = timedelta(hours=WHALE_UPDATE_INTERVAL_HOURS)
        
        # Scheduling state management
        self.schedule_state_file = self.data_dir / "whale_schedule_state.json"
        self.scheduler_thread = None
        self.scheduler_stop_event = threading.Event()
        
        # Load scheduling state
        self._load_schedule_state()
        
        # Always run immediately on startup, then schedule for 48 hours later
        current_time = datetime.now()
        self.initial_delay_completed = True  # Always run immediately on startup
        self.initialization_time = current_time
        
        # If we have existing state but it's in the future, override it to run now
        if hasattr(self, 'next_execution_time') and self.next_execution_time and self.next_execution_time > current_time:
            logger.info("🔄 Overriding scheduled time to run immediately on startup")
            self.next_execution_time = current_time  # Run now
        elif not hasattr(self, 'next_execution_time') or self.next_execution_time is None:
            self.next_execution_time = current_time  # Run now
        
        self._save_schedule_state()
        
        # Initialize scheduler
        self._setup_scheduler()
        
        logger.info(f"🐋 Whale Agent initialized successfully with {len(self.apify_tokens)} API token(s)")
        if hasattr(self, 'next_execution_time'):
            logger.info(f"📅 Next scheduled execution: {self.next_execution_time.strftime('%Y-%m-%d %H:%M:%S')}")
            if not self.initial_delay_completed:
                remaining_time = self.next_execution_time - datetime.now()
                if remaining_time.total_seconds() > 0:
                    logger.info(f"⏰ Initial delay: {remaining_time.total_seconds() / 3600:.1f} hours remaining")

    def _switch_to_next_token(self) -> bool:
        """Switch to the next available API token"""
        if self.current_token_index < len(self.apify_tokens) - 1:
            self.current_token_index += 1
            self.apify_client = ApifyClient(self.apify_tokens[self.current_token_index])
            logger.warning(f"🔄 Switched to APIFY_API_TOKEN_{self.current_token_index + 1}")
            return True
        else:
            logger.error("❌ All APIFY API tokens have been exhausted")
            return False

    def _load_existing_data(self):
        """Load existing ranked wallets and history data"""
        try:
            # Load ranked wallets
            if self.ranked_file.exists():
                with open(self.ranked_file, 'r') as f:
                    data = json.load(f)
                    self.ranked_wallets = {
                        addr: WhaleWallet(**wallet_data)
                        for addr, wallet_data in data.items()
                    }
                logger.info(f"Loaded {len(self.ranked_wallets)} existing ranked wallets")
            
            # Load history
            if self.history_file.exists():
                self.wallet_history = pd.read_csv(self.history_file).to_dict('records')
                logger.info(f"Loaded {len(self.wallet_history)} history records")
                
        except Exception as e:
            logger.warning(f"Error loading existing data: {e}")
            self.ranked_wallets = {}
            self.wallet_history = []
    
    def _save_data(self):
        """Save ranked wallets and history data to local files first, then sync to cloud database"""
        try:
            # Clean up history before saving
            self._cleanup_history()
            
            # PRIMARY: Save to local files first
            self._save_whale_data_to_local_files()
            
            # SECONDARY: Try to sync to cloud database
            if CLOUD_DB_AVAILABLE:
                try:
                    db_manager = get_cloud_database_manager()
                    if db_manager is not None:
                        # Save whale data to cloud database
                        for addr, wallet in self.ranked_wallets.items():
                            wallet_dict = asdict(wallet)
                            
                            # Fix NaN values in pnl_1d
                            if wallet_dict.get('pnl_1d') is None or str(wallet_dict.get('pnl_1d')).lower() == 'nan':
                                wallet_dict['pnl_1d'] = None
                            
                            # Save to whale_data table
                            query = '''
                                INSERT INTO whale_data (
                                    wallet_address, wallet_name, total_value_usd, pnl_1d, pnl_7d, pnl_30d,
                                    top_tokens, trading_volume_24h, risk_score, is_active, metadata
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (wallet_address) DO UPDATE SET
                                    total_value_usd = EXCLUDED.total_value_usd,
                                    pnl_1d = EXCLUDED.pnl_1d,
                                    pnl_7d = EXCLUDED.pnl_7d,
                                    pnl_30d = EXCLUDED.pnl_30d,
                                    top_tokens = EXCLUDED.top_tokens,
                                    trading_volume_24h = EXCLUDED.trading_volume_24h,
                                    risk_score = EXCLUDED.risk_score,
                                    is_active = EXCLUDED.is_active,
                                    metadata = EXCLUDED.metadata,
                                    timestamp = NOW()
                            '''
                            
                            params = (
                                addr,  # wallet_address
                                wallet_dict.get('twitter_handle', ''),  # wallet_name
                                None,  # total_value_usd (not available in current data)
                                wallet_dict.get('pnl_1d'),  # pnl_1d
                                wallet_dict.get('pnl_7d'),  # pnl_7d
                                wallet_dict.get('pnl_30d'),  # pnl_30d
                                json.dumps([]),  # top_tokens (not available in current data)
                                None,  # trading_volume_24h (not available in current data)
                                wallet_dict.get('score'),  # risk_score
                                wallet_dict.get('is_active', True),  # is_active
                                json.dumps(wallet_dict)  # metadata (full wallet data)
                            )
                            
                            db_manager.execute_query(query, params, fetch=False)
                        
                        # Save whale history to cloud database
                        if self.wallet_history:
                            for record in self.wallet_history:
                                query = '''
                                    INSERT INTO whale_history (
                                        wallet_address, action_type, token_mint, amount, value_usd, metadata
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                '''
                                
                                params = (
                                    record.get('wallet_address', ''),  # wallet_address
                                    'update',  # action_type (default)
                                    None,  # token_mint (not available in current data)
                                    None,  # amount (not available in current data)
                                    None,  # value_usd (not available in current data)
                                    json.dumps(record)  # metadata (full record data)
                                )
                                
                                db_manager.execute_query(query, params, fetch=False)
                        
                        logger.info("✅ Whale data synced to cloud database successfully")
                        
                except Exception as cloud_error:
                    logger.warning(f"⚠️ Cloud database sync failed (local data saved): {cloud_error}")
            
            # TERTIARY: Sync to commerce agents' Supabase collection (whale_rankings)
            try:
                import sys
                import os
                commerce_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ai_commerce_agents', 'src')
                if commerce_path not in sys.path:
                    sys.path.insert(0, commerce_path)
                
                from shared.cloud_storage import get_cloud_storage_manager
                
                commerce_storage = get_cloud_storage_manager()
                if commerce_storage and commerce_storage.connect():
                    rankings_for_commerce = []
                    for addr, wallet in self.ranked_wallets.items():
                        # Convert WhaleWallet to commerce-compatible format
                        metadata_payload = {
                            'address': wallet.address,
                            'twitter_handle': wallet.twitter_handle if wallet.twitter_handle else None,
                            'pnl_30d': float(wallet.pnl_30d),
                            'pnl_7d': float(wallet.pnl_7d),
                            'pnl_1d': float(wallet.pnl_1d) if wallet.pnl_1d and str(wallet.pnl_1d).lower() != 'nan' else 0.0,
                            'winrate_7d': float(wallet.winrate_7d),
                            'txs_30d': int(wallet.txs_30d),
                            'token_active': int(wallet.token_active),
                            'last_active': wallet.last_active,
                            'is_blue_verified': bool(wallet.is_blue_verified),
                            'avg_holding_period_7d': float(wallet.avg_holding_period_7d),
                            'score': float(wallet.score),
                            'rank': int(wallet.rank),
                            'last_updated': wallet.last_updated,
                            'ranking_id': f"whale_{wallet.address}"
                        }

                        supabase_record = {
                            'wallet_address': wallet.address,
                            'wallet_name': wallet.twitter_handle or wallet.address[:12],
                            'pnl_1d': metadata_payload['pnl_1d'],
                            'pnl_7d': metadata_payload['pnl_7d'],
                            'pnl_30d': metadata_payload['pnl_30d'],
                            'risk_score': metadata_payload['score'],
                            'is_active': wallet.is_active,
                            'metadata': metadata_payload
                        }
                        rankings_for_commerce.append(supabase_record)
                    
                    # Store to commerce cloud storage (Supabase whale_rankings collection)
                    if rankings_for_commerce:
                        success = commerce_storage.store_whale_rankings(rankings_for_commerce)
                        if success:
                            logger.info(f"✅ Synced {len(rankings_for_commerce)} rankings to Supabase whale_data table")
                        else:
                            logger.warning("⚠️ Failed to sync rankings to Supabase whale_data table")
                else:
                    logger.debug("Commerce cloud storage not available or not connected")
                    
            except ImportError as import_error:
                logger.debug(f"Commerce cloud storage not available: {import_error}")
            except Exception as commerce_error:
                logger.warning(f"⚠️ Failed to sync to commerce cloud storage: {commerce_error}")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def _save_whale_data_to_local_files(self):
        """Fallback method to save whale data to local files"""
        try:
            # Save ranked wallets (fix NaN values)
            with open(self.ranked_file, 'w') as f:
                cleaned_wallets = {}
                for addr, wallet in self.ranked_wallets.items():
                    wallet_dict = asdict(wallet)
                    # Fix NaN values in pnl_1d
                    if wallet_dict.get('pnl_1d') is None or str(wallet_dict.get('pnl_1d')).lower() == 'nan':
                        wallet_dict['pnl_1d'] = None
                    cleaned_wallets[addr] = wallet_dict
                json.dump(cleaned_wallets, f, indent=2)
            
            # Save history
            if self.wallet_history:
                df = pd.DataFrame(self.wallet_history)
                df.to_csv(self.history_file, index=False)
                
            logger.info("📁 Whale data saved to local files successfully")
            
        except Exception as e:
            logger.error(f"Error saving whale data to local files: {e}")
    
    def _cleanup_history(self):
        """Clean up whale history data based on retention policies"""
        try:
            if not self.wallet_history:
                return
            
            original_count = len(self.wallet_history)
            cutoff_date = datetime.now() - timedelta(days=WHALE_HISTORY_RETENTION_DAYS)
            
            # Filter by date and record count
            cleaned_history = []
            for record in self.wallet_history:
                try:
                    # Parse timestamp
                    record_date = datetime.fromisoformat(record.get('timestamp', ''))
                    if record_date >= cutoff_date:
                        cleaned_history.append(record)
                except (ValueError, TypeError):
                    # Keep records with invalid timestamps for safety
                    cleaned_history.append(record)
            
            # Limit by maximum records (keep most recent)
            if len(cleaned_history) > WHALE_HISTORY_MAX_RECORDS:
                # Sort by timestamp descending and keep the most recent
                cleaned_history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                cleaned_history = cleaned_history[:WHALE_HISTORY_MAX_RECORDS]
            
            self.wallet_history = cleaned_history
            removed_count = original_count - len(cleaned_history)
            
            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} old history records (kept {len(cleaned_history)} records)")
                
        except Exception as e:
            logger.error(f"Error cleaning up history: {e}")
    
    def _load_schedule_state(self):
        """Load scheduling state from persistent storage"""
        try:
            if self.schedule_state_file.exists():
                with open(self.schedule_state_file, 'r') as f:
                    state = json.load(f)
                    
                # Parse stored timestamps
                if 'next_execution_time' in state and state['next_execution_time']:
                    self.next_execution_time = datetime.fromisoformat(state['next_execution_time'])
                else:
                    self.next_execution_time = None
                    
                if 'last_update' in state and state['last_update']:
                    self.last_update = datetime.fromisoformat(state['last_update'])
                    
                self.initial_delay_completed = state.get('initial_delay_completed', False)
                
                logger.info(f"📋 Loaded scheduling state from {self.schedule_state_file}")
                if self.next_execution_time:
                    logger.info(f"📅 Next execution scheduled for: {self.next_execution_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
        except Exception as e:
            logger.warning(f"Could not load scheduling state: {e}. Starting fresh.")
            self.next_execution_time = None
            self.initial_delay_completed = False
    
    def _save_schedule_state(self):
        """Save scheduling state to persistent storage"""
        try:
            state = {
                'next_execution_time': self.next_execution_time.isoformat() if self.next_execution_time else None,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'initial_delay_completed': self.initial_delay_completed,
                'update_interval_hours': WHALE_UPDATE_INTERVAL_HOURS,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(self.schedule_state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
            logger.debug(f"💾 Saved scheduling state to {self.schedule_state_file}")
            
        except Exception as e:
            logger.error(f"Error saving scheduling state: {e}")
    
    def _setup_scheduler(self):
        """Setup the scheduling system using the schedule library"""
        try:
            # Clear any existing schedules
            schedule.clear()
            
            # Calculate when to run the job
            if self.next_execution_time and datetime.now() < self.next_execution_time:
                # Schedule for the specific time
                schedule_time = self.next_execution_time.strftime('%H:%M')
                schedule.every().day.at(schedule_time).do(self._scheduled_update_wrapper)
                logger.info(f"📅 Scheduled whale data update for {schedule_time} daily")
            else:
                # Schedule to run now and then every 48 hours
                schedule.every(WHALE_UPDATE_INTERVAL_HOURS).hours.do(self._scheduled_update_wrapper)
                logger.info(f"📅 Scheduled whale data update every {WHALE_UPDATE_INTERVAL_HOURS} hours")
                
        except Exception as e:
            logger.error(f"Error setting up scheduler: {e}")
    
    def _scheduled_update_wrapper(self):
        """Wrapper for scheduled updates that handles async execution"""
        try:
            logger.info("🔔 Scheduled whale data update triggered")
            
            # Run the async update in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                success = loop.run_until_complete(self.update_whale_data())
                if success:
                    logger.info("✅ Scheduled whale data update completed successfully")
                    # Update next execution time
                    self.next_execution_time = datetime.now() + timedelta(hours=WHALE_UPDATE_INTERVAL_HOURS)
                    self._save_schedule_state()
                    logger.info(f"📅 Next execution scheduled for: {self.next_execution_time.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logger.warning("⚠️ Scheduled whale data update failed")
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error in scheduled update: {e}")
    
    def start_scheduler(self):
        """Start the background scheduler thread"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Scheduler thread is already running")
            return
            
        def run_scheduler():
            logger.info("🚀 Starting whale agent scheduler thread")
            while not self.scheduler_stop_event.is_set():
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Error in scheduler thread: {e}")
                    time.sleep(60)
                    
            logger.info("🛑 Scheduler thread stopped")
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("📅 Whale agent scheduler started")
    
    def stop_scheduler(self):
        """Stop the background scheduler thread"""
        if self.scheduler_thread:
            logger.info("🛑 Stopping whale agent scheduler")
            self.scheduler_stop_event.set()
            self.scheduler_thread.join(timeout=5)
            if self.scheduler_thread.is_alive():
                logger.warning("Scheduler thread did not stop gracefully")
            else:
                logger.info("✅ Scheduler thread stopped successfully")
    
    async def execute_now(self) -> bool:
        """Execute whale data update immediately, bypassing schedule"""
        logger.info("🚀 Manual whale data update triggered")
        success = await self.update_whale_data()
        
        if success:
            # Update scheduling state
            self.next_execution_time = datetime.now() + timedelta(hours=WHALE_UPDATE_INTERVAL_HOURS)
            self.initial_delay_completed = True
            self._save_schedule_state()
            logger.info(f"📅 Next execution rescheduled for: {self.next_execution_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return success
    
    async def _fetch_apify_data(self) -> Optional[pd.DataFrame]:
        """
        Fetch data from Apify GMGN CopyTrade Wallet Scraper with token fallback
        """
        max_token_attempts = len(self.apify_tokens)
        token_attempt = 0

        while token_attempt < max_token_attempts:
            try:
                logger.info(f"🔄 Fetching data from Apify (Token {self.current_token_index + 1}/{len(self.apify_tokens)})...")

                # Run the actor
                run = self.apify_client.actor(APIFY_ACTOR_ID).call(
                    run_input=APIFY_DEFAULT_INPUT
                )

                # Wait for completion
                while run['status'] not in [ActorJobStatus.SUCCEEDED, ActorJobStatus.FAILED]:
                    await asyncio.sleep(10)
                    run = self.apify_client.actor(APIFY_ACTOR_ID).last_run()

                if run['status'] == ActorJobStatus.FAILED:
                    error_msg = run.get('meta', {}).get('error', 'Unknown error')
                    raise Exception(f"Actor run failed: {error_msg}")

                # Get dataset items
                dataset_id = run['defaultDatasetId']
                dataset_items = self.apify_client.dataset(dataset_id).list_items().items

                if not dataset_items:
                    logger.warning("No data returned from Apify")
                    return None

                # Convert to DataFrame
                df = pd.DataFrame(dataset_items)
                logger.info(f"✅ Fetched {len(df)} wallet records from Apify")

                # Log sample data for debugging
                if len(df) > 0:
                    logger.info(f"Sample data columns: {list(df.columns)}")
                    logger.info(f"Sample row: {df.iloc[0].to_dict()}")

                return df

            except Exception as e:
                error_str = str(e).lower()

                # Check if this is a rate limit error
                if ("exceed your remaining usage" in error_str or
                    "rate limit" in error_str or
                    "billing" in error_str or
                    "subscription" in error_str):

                    logger.warning(f"🚫 Rate limit detected on APIFY_API_TOKEN_{self.current_token_index + 1}: {e}")

                    # Try switching to next token
                    if self._switch_to_next_token():
                        token_attempt += 1
                        logger.info(f"🔄 Retrying with backup token (attempt {token_attempt}/{max_token_attempts})")
                        continue
                    else:
                        # No more tokens available
                        break
                else:
                    # Not a rate limit error, re-raise
                    logger.error(f"Error fetching Apify data: {e}")
                    break

        logger.error("❌ Failed to fetch data from Apify with all available tokens")
        return None
    
    def _normalize_metric(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a metric to 0-1 range"""
        if max_val == min_val:
            return 0.5
        return max(0, min(1, (value - min_val) / (max_val - min_val)))
    
    def _calculate_wallet_score(self, wallet_data: Dict[str, Any]) -> float:
        """
        Calculate comprehensive score for a wallet based on multiple metrics
        """
        try:
            # Extract metrics with safe defaults - handle different field names
            # Note: pnl_30d and pnl_7d are percentages, not absolute amounts
            pnl_30d_pct = float(wallet_data.get('pnl_30d', 0))  # This is percentage
            pnl_7d_pct = float(wallet_data.get('pnl_7d', 0))    # This is percentage
            realized_profit_30d = float(wallet_data.get('realized_profit_30d', 0))  # This is absolute amount
            realized_profit_7d = float(wallet_data.get('realized_profit_7d', 0))    # This is absolute amount
            winrate_7d = float(wallet_data.get('winrate_7d', 0))
            txs_30d = int(wallet_data.get('txs_30d', 0))
            
            # Handle token_active from risk object
            risk_data = wallet_data.get('risk', {})
            if isinstance(risk_data, dict):
                token_active = int(risk_data.get('token_active', 0))
            else:
                token_active = int(wallet_data.get('token_active', 0))
            
            is_blue_verified = bool(wallet_data.get('is_blue_verified', False))
            avg_holding_period_7d = float(wallet_data.get('avg_holding_period_7d', 1))
            
            # Apply thresholds based on ideal wallet characteristics
            # Use realized_profit for absolute amounts, pnl percentages for relative performance
            if (realized_profit_30d < WHALE_THRESHOLDS['min_pnl_30d'] or
                winrate_7d < WHALE_THRESHOLDS['min_winrate_7d'] or
                txs_30d > WHALE_THRESHOLDS['max_txs_30d'] or
                token_active < WHALE_THRESHOLDS['min_token_active'] or
                token_active > WHALE_THRESHOLDS['max_token_active'] or
                avg_holding_period_7d < WHALE_THRESHOLDS['min_avg_holding_period'] or
                avg_holding_period_7d > WHALE_THRESHOLDS['max_avg_holding_period']):
                return 0.0
            
            # Get 1-day PNL data (handle NaN/None values)
            pnl_1d_pct = float(wallet_data.get('pnl_1d', 0)) if wallet_data.get('pnl_1d') not in [None, 'NaN', float('nan')] else 0
            realized_profit_1d = float(wallet_data.get('realized_profit_1d', 0)) if wallet_data.get('realized_profit_1d') not in [None, 'NaN', float('nan')] else 0
            
            # Normalize PNL metrics based on ideal wallet characteristics
            # Use percentage-based PNL for better comparison across different wallet sizes
            pnl_30d_norm = self._normalize_metric(pnl_30d_pct, 0, 5.0)  # Cap at 500% (5.0 as decimal)
            pnl_7d_norm = self._normalize_metric(pnl_7d_pct, 0, 3.0)    # Cap at 300% (3.0 as decimal)
            pnl_1d_norm = self._normalize_metric(pnl_1d_pct, 0, 1.0)    # Cap at 100% (1.0 as decimal)
            
            # Other normalized metrics
            winrate_norm = winrate_7d  # Already 0-1
            txs_norm = 1 - self._normalize_metric(txs_30d, 0, WHALE_THRESHOLDS['max_txs_30d'])  # Inverse
            token_norm = self._normalize_metric(
                token_active, 
                WHALE_THRESHOLDS['min_token_active'], 
                WHALE_THRESHOLDS['max_token_active']
            )
            
            # Improved holding period normalization
            # Optimal holding period is between 1 hour and 7 days for most profitable traders
            optimal_holding_min = 1.0 / 24.0  # 1 hour in days
            optimal_holding_max = 7.0  # 7 days
            holding_period_days = avg_holding_period_7d / 86400.0  # Convert seconds to days
            
            if optimal_holding_min <= holding_period_days <= optimal_holding_max:
                # Peak score for optimal range
                holding_norm = 1.0 - abs(holding_period_days - 1.0) / 6.0  # Peak at 1 day
            elif holding_period_days < optimal_holding_min:
                # Penalize very short holding periods (likely MEV bots)
                holding_norm = 0.2
            else:
                # Gradually decrease for longer holding periods
                holding_norm = max(0.1, 1.0 / (1.0 + (holding_period_days - optimal_holding_max) / 30.0))
            
            # Calculate weighted score with new priority order
            score = (
                WHALE_SCORING_WEIGHTS['pnl_30d'] * pnl_30d_norm +
                WHALE_SCORING_WEIGHTS['pnl_7d'] * pnl_7d_norm +
                WHALE_SCORING_WEIGHTS['pnl_1d'] * pnl_1d_norm +
                WHALE_SCORING_WEIGHTS['winrate_7d'] * winrate_norm +
                WHALE_SCORING_WEIGHTS['avg_holding_period_7d'] * holding_norm +
                WHALE_SCORING_WEIGHTS['token_active'] * token_norm +
                WHALE_SCORING_WEIGHTS['is_blue_verified'] * (1.0 if is_blue_verified else 0.0) +
                WHALE_SCORING_WEIGHTS['txs_30d'] * txs_norm
            )
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating score for wallet: {e}")
            return 0.0
    
    def _process_wallet_data(self, df: pd.DataFrame) -> List[WhaleWallet]:
        """
        Process raw wallet data and create WhaleWallet objects
        """
        wallets = []
        
        for _, row in df.iterrows():
            try:
                # Calculate score
                score = self._calculate_wallet_score(row.to_dict())
                
                if score > 0:  # Only include wallets that meet minimum criteria
                    # Handle different field names
                    address = str(row.get('address', row.get('wallet_address', '')))
                    twitter_handle = str(row.get('twitter_username', row.get('twitter_handle', '')))
                    pnl_30d = float(row.get('pnl_30d', row.get('realized_profit_30d', 0)))
                    pnl_7d = float(row.get('pnl_7d', row.get('realized_profit_7d', 0)))
                    # Handle NaN values in pnl_1d
                    pnl_1d_raw = row.get('pnl_1d', row.get('realized_profit_1d', 0))
                    if pnl_1d_raw is None or str(pnl_1d_raw).lower() in ['nan', 'null']:
                        pnl_1d = 0.0
                    else:
                        try:
                            pnl_1d = float(pnl_1d_raw)
                        except (ValueError, TypeError):
                            pnl_1d = 0.0
                    winrate_7d = float(row.get('winrate_7d', 0))
                    txs_30d = int(row.get('txs_30d', 0))
                    
                    # Handle token_active from risk object
                    risk_data = row.get('risk', {})
                    if isinstance(risk_data, dict):
                        token_active = int(risk_data.get('token_active', 0))
                    else:
                        token_active = int(row.get('token_active', 0))
                    
                    last_active = str(row.get('last_active', ''))
                    is_blue_verified = bool(row.get('is_blue_verified', False))
                    avg_holding_period_7d = float(row.get('avg_holding_period_7d', 1))
                    
                    wallet = WhaleWallet(
                        address=address,
                        twitter_handle=twitter_handle,
                        pnl_30d=pnl_30d,
                        pnl_7d=pnl_7d,
                        pnl_1d=pnl_1d,
                        winrate_7d=winrate_7d,
                        txs_30d=txs_30d,
                        token_active=token_active,
                        last_active=last_active,
                        is_blue_verified=is_blue_verified,
                        avg_holding_period_7d=avg_holding_period_7d,
                        score=score,
                        rank=0,  # Will be set after sorting
                        last_updated=datetime.now().isoformat(),
                        is_active=True
                    )
                    wallets.append(wallet)
                    
            except Exception as e:
                logger.error(f"Error processing wallet data: {e}")
                continue
        
        # Sort by score and assign ranks
        wallets.sort(key=lambda x: x.score, reverse=True)
        for i, wallet in enumerate(wallets):
            wallet.rank = i + 1
        
        return wallets
    
    def _update_ranked_wallets(self, new_wallets: List[WhaleWallet]):
        """
        Update the ranked wallets list with new data
        """
        # Create new ranked dictionary
        new_ranked = {}
        timestamp = datetime.now().isoformat()
        
        for wallet in new_wallets:
            new_ranked[wallet.address] = wallet
            
            # Update or add to history (prevent duplicates)
            self._update_wallet_history(wallet, timestamp)
        
        # Merge with existing wallets (keep inactive ones for a while)
        for addr, wallet in self.ranked_wallets.items():
            if addr not in new_ranked:
                # Mark as inactive if not in new data
                wallet.is_active = False
                wallet.last_updated = datetime.now().isoformat()
                new_ranked[addr] = wallet
        
        # Limit total stored wallets
        if len(new_ranked) > WHALE_MAX_STORED_WALLETS:
            # Keep only top wallets and most recent inactive ones
            active_wallets = {addr: w for addr, w in new_ranked.items() if w.is_active}
            inactive_wallets = {addr: w for addr, w in new_ranked.items() if not w.is_active}
            
            # Sort inactive by last updated
            inactive_sorted = sorted(
                inactive_wallets.items(),
                key=lambda x: x[1].last_updated,
                reverse=True
            )
            
            # Keep top active + recent inactive
            keep_count = WHALE_MAX_STORED_WALLETS - len(active_wallets)
            recent_inactive = dict(inactive_sorted[:keep_count])
            
            new_ranked = {**active_wallets, **recent_inactive}
        
        self.ranked_wallets = new_ranked
        logger.info(f"Updated ranked wallets: {len([w for w in new_ranked.values() if w.is_active])} active, {len([w for w in new_ranked.values() if not w.is_active])} inactive")
        try:
            publish_whale_rankings(new_ranked.values())
        except Exception:
            logger.exception("Failed to publish whale rankings to core bridge")
    
    def _update_wallet_history(self, wallet: WhaleWallet, timestamp: str):
        """
        Update or add wallet to history, preventing duplicates by address
        """
        try:
            # Find existing history record for this address
            existing_index = None
            for i, record in enumerate(self.wallet_history):
                if record.get('address') == wallet.address:
                    existing_index = i
                    break
            
            # Create new history record
            history_record = asdict(wallet)
            history_record['timestamp'] = timestamp
            
            if existing_index is not None:
                # Update existing record
                self.wallet_history[existing_index] = history_record
                logger.debug(f"Updated history for wallet {wallet.address[:8]}...")
            else:
                # Add new record
                self.wallet_history.append(history_record)
                logger.debug(f"Added new history for wallet {wallet.address[:8]}...")
                
        except Exception as e:
            logger.error(f"Error updating wallet history for {wallet.address}: {e}")
    
    def _cleanup_stale_wallets(self):
        """
        Remove wallets that have been inactive for too long
        """
        cutoff_date = datetime.now() - timedelta(days=WHALE_THRESHOLDS['max_inactive_days'])
        
        stale_addresses = []
        for addr, wallet in self.ranked_wallets.items():
            try:
                last_updated = datetime.fromisoformat(wallet.last_updated)
                if last_updated < cutoff_date and not wallet.is_active:
                    stale_addresses.append(addr)
            except (ValueError, TypeError):
                stale_addresses.append(addr)
        
        for addr in stale_addresses:
            del self.ranked_wallets[addr]
        
        if stale_addresses:
            logger.info(f"Removed {len(stale_addresses)} stale wallets")
    
    async def update_whale_data(self) -> bool:
        """
        Main method to update whale data from Apify
        """
        try:
            logger.info("🔄 Starting whale data update...")
            
            # Fetch new data
            df = await self._fetch_apify_data()
            if df is None:
                logger.error("Failed to fetch data from Apify")
                return False
            
            # Process wallet data
            new_wallets = self._process_wallet_data(df)
            logger.info(f"Processed {len(new_wallets)} qualifying wallets")
            
            # Update ranked wallets
            self._update_ranked_wallets(new_wallets)
            
            # Cleanup stale wallets
            self._cleanup_stale_wallets()
            
            # Save data
            self._save_data()
            
            # Update timestamp and scheduling state
            self.last_update = datetime.now()
            self.initial_delay_completed = True
            self._save_schedule_state()
            
            logger.info("✅ Whale data update completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating whale data: {e}")
            return False
    
    def get_top_wallets(self, limit: int = 10, active_only: bool = True) -> List[WhaleWallet]:
        """
        Get top-ranked wallets
        """
        wallets = [
            wallet for wallet in self.ranked_wallets.values()
            if not active_only or wallet.is_active
        ]
        
        wallets.sort(key=lambda x: x.score, reverse=True)
        return wallets[:limit]
    
    def get_wallet_by_address(self, address: str) -> Optional[WhaleWallet]:
        """
        Get wallet information by address
        """
        return self.ranked_wallets.get(address)
    
    def get_wallet_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the whale data
        """
        active_wallets = [w for w in self.ranked_wallets.values() if w.is_active]
        inactive_wallets = [w for w in self.ranked_wallets.values() if not w.is_active]
        
        if not active_wallets:
            return {
                'total_wallets': len(self.ranked_wallets),
                'active_wallets': 0,
                'inactive_wallets': len(inactive_wallets),
                'avg_score': 0,
                'last_update': self.last_update.isoformat() if self.last_update else None
            }
        
        return {
            'total_wallets': len(self.ranked_wallets),
            'active_wallets': len(active_wallets),
            'inactive_wallets': len(inactive_wallets),
            'avg_score': sum(w.score for w in active_wallets) / len(active_wallets),
            'top_score': max(w.score for w in active_wallets),
            'avg_pnl_30d': sum(w.pnl_30d for w in active_wallets) / len(active_wallets),
            'avg_winrate': sum(w.winrate_7d for w in active_wallets) / len(active_wallets),
            'verified_count': sum(1 for w in active_wallets if w.is_blue_verified),
            'last_update': self.last_update.isoformat() if self.last_update else None
        }
    
    def should_update(self) -> bool:
        """
        Check if it's time to update the data based on persistent scheduling
        """
        current_time = datetime.now()
        
        # Check if we have a scheduled execution time
        if hasattr(self, 'next_execution_time') and self.next_execution_time:
            should_run = current_time >= self.next_execution_time
            if should_run:
                logger.info(f"⏰ Scheduled execution time reached: {self.next_execution_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return should_run
        
        # Fallback to legacy logic if no scheduled time
        # Check if initial 48-hour delay has passed
        if not self.initial_delay_completed:
            time_since_init = current_time - self.initialization_time
            if time_since_init >= timedelta(hours=48):
                self.initial_delay_completed = True
                logger.info("⏰ Initial 48-hour delay completed. Whale Agent will now start fetching data.")
                return True
            else:
                remaining_hours = 48 - (time_since_init.total_seconds() / 3600)
                logger.info(f"⏰ Waiting for initial delay: {remaining_hours:.1f} hours remaining")
                return False
        
        # Normal update interval check
        if self.last_update is None:
            return True
        
        return current_time - self.last_update >= self.update_interval
    
    def get_next_execution_info(self) -> Dict[str, Any]:
        """
        Get information about the next scheduled execution
        """
        current_time = datetime.now()
        info = {
            'current_time': current_time.isoformat(),
            'next_execution_time': None,
            'time_until_next': None,
            'hours_until_next': None,
            'initial_delay_completed': self.initial_delay_completed,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'update_interval_hours': WHALE_UPDATE_INTERVAL_HOURS
        }
        
        if hasattr(self, 'next_execution_time') and self.next_execution_time:
            info['next_execution_time'] = self.next_execution_time.isoformat()
            time_diff = self.next_execution_time - current_time
            info['time_until_next'] = str(time_diff)
            info['hours_until_next'] = time_diff.total_seconds() / 3600
        
        return info
    
    async def run(self, use_scheduler: bool = True):
        """
        Main run loop for the Whale Agent
        
        Args:
            use_scheduler: If True, use the background scheduler. If False, use polling mode.
        """
        logger.info("🚀 Starting Whale Agent...")
        
        if use_scheduler:
            # Start the background scheduler
            self.start_scheduler()
            
            # Keep the main thread alive and handle immediate execution if needed
            while self.running:
                try:
                    # Check if we should run immediately (for initial execution or manual triggers)
                    if self.should_update():
                        success = await self.update_whale_data()
                        if success:
                            logger.info("✅ Whale data updated successfully")
                            # Update next execution time
                            self.next_execution_time = datetime.now() + timedelta(hours=WHALE_UPDATE_INTERVAL_HOURS)
                            self._save_schedule_state()
                        else:
                            logger.warning("⚠️ Whale data update failed")
                    
                    # Wait before next check (longer interval since scheduler handles regular execution)
                    await asyncio.sleep(1800)  # Check every 30 minutes
                    
                except Exception as e:
                    logger.error(f"Error in Whale Agent run loop: {e}")
                    await asyncio.sleep(300)  # Wait 5 minutes on error
        else:
            # Legacy polling mode
            while self.running:
                try:
                    if self.should_update():
                        success = await self.update_whale_data()
                        if success:
                            logger.info("✅ Whale data updated successfully")
                        else:
                            logger.warning("⚠️ Whale data update failed")
                    else:
                        # Log waiting status
                        if hasattr(self, 'next_execution_time') and self.next_execution_time:
                            time_diff = self.next_execution_time - datetime.now()
                            if time_diff.total_seconds() > 0:
                                hours_remaining = time_diff.total_seconds() / 3600
                                logger.info(f"⏰ Whale Agent waiting: {hours_remaining:.1f} hours until next execution")
                    
                    # Wait before next check
                    await asyncio.sleep(3600)  # Check every hour
                    
                except Exception as e:
                    logger.error(f"Error in Whale Agent run loop: {e}")
                    await asyncio.sleep(300)  # Wait 5 minutes on error
    
    def stop(self):
        """
        Stop the Whale Agent gracefully
        """
        logger.info("🛑 Stopping Whale Agent...")
        
        # Stop the scheduler first
        self.stop_scheduler()
        
        # Stop the base agent
        super().stop()
        
        # Save all data and state
        self._save_data()
        self._save_schedule_state()
        
        logger.info("✅ Whale Agent stopped")

# Utility functions for external use
async def create_whale_agent() -> WhaleAgent:
    """Create and return a Whale Agent instance"""
    return WhaleAgent()

def get_whale_agent_singleton() -> WhaleAgent:
    """Get or create a singleton Whale Agent instance"""
    if not hasattr(get_whale_agent_singleton, '_instance'):
        get_whale_agent_singleton._instance = WhaleAgent()
    return get_whale_agent_singleton._instance

if __name__ == "__main__":
    import argparse
    
    # Command line argument parsing
    parser = argparse.ArgumentParser(description='Whale Agent - Track and rank cryptocurrency wallets')
    parser.add_argument('--mode', choices=['test', 'run', 'execute-now', 'status'], default='run',
                       help='Execution mode: test, run, execute-now, or status')
    parser.add_argument('--scheduler', action='store_true', default=True,
                       help='Use background scheduler (default: True)')
    parser.add_argument('--no-scheduler', dest='scheduler', action='store_false',
                       help='Disable background scheduler, use polling mode')
    args = parser.parse_args()
    
    async def test_whale_agent():
        """Test mode - run one update and show statistics"""
        agent = WhaleAgent()
        success = await agent.update_whale_data()
        if success:
            stats = agent.get_wallet_statistics()
            print(f"Whale Agent Statistics: {stats}")
            
            top_wallets = agent.get_top_wallets(5)
            print(f"\nTop 5 Wallets:")
            for wallet in top_wallets:
                print(f"Rank {wallet.rank}: {wallet.twitter_handle} (@{wallet.address[:8]}...) - Score: {wallet.score:.3f}")
        
        agent.stop()
        return success
    
    async def run_whale_agent():
        """Run mode - continuous operation with scheduling"""
        agent = WhaleAgent()
        try:
            await agent.run(use_scheduler=args.scheduler)
        except KeyboardInterrupt:
            logger.info("\n🛑 Received interrupt signal")
        finally:
            agent.stop()
    
    async def execute_now():
        """Execute now mode - immediate execution bypassing schedule"""
        agent = WhaleAgent()
        success = await agent.execute_now()
        if success:
            stats = agent.get_wallet_statistics()
            print(f"Execution completed successfully. Statistics: {stats}")
        else:
            print("Execution failed")
        
        agent.stop()
        return success
    
    def show_status():
        """Status mode - show current scheduling information"""
        agent = WhaleAgent()
        info = agent.get_next_execution_info()
        
        print("\n🐋 Whale Agent Status:")
        print(f"Current Time: {datetime.fromisoformat(info['current_time']).strftime('%Y-%m-%d %H:%M:%S')}")
        
        if info['next_execution_time']:
            next_time = datetime.fromisoformat(info['next_execution_time'])
            print(f"Next Execution: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            if info['hours_until_next'] is not None:
                if info['hours_until_next'] > 0:
                    print(f"Time Remaining: {info['hours_until_next']:.1f} hours")
                else:
                    print("⚠️ Execution is overdue!")
        else:
            print("Next Execution: Not scheduled")
        
        print(f"Initial Delay Completed: {'✅' if info['initial_delay_completed'] else '❌'}")
        print(f"Last Update: {datetime.fromisoformat(info['last_update']).strftime('%Y-%m-%d %H:%M:%S') if info['last_update'] else 'Never'}")
        print(f"Update Interval: {info['update_interval_hours']} hours")
        
        # Show wallet statistics if data exists
        try:
            stats = agent.get_wallet_statistics()
            print(f"\n📊 Current Data:")
            print(f"Total Wallets: {stats['total_wallets']}")
            print(f"Active Wallets: {stats['active_wallets']}")
            print(f"Inactive Wallets: {stats['inactive_wallets']}")
            if stats['active_wallets'] > 0:
                print(f"Average Score: {stats['avg_score']:.3f}")
                print(f"Top Score: {stats['top_score']:.3f}")
        except Exception as e:
            print(f"Could not load wallet statistics: {e}")
        
        agent.stop()
    
    # Execute based on mode
    if args.mode == 'test':
        print("🧪 Running in test mode...")
        asyncio.run(test_whale_agent())
    elif args.mode == 'run':
        scheduler_mode = "with scheduler" if args.scheduler else "polling mode"
        print(f"🚀 Running in continuous mode {scheduler_mode}...")
        asyncio.run(run_whale_agent())
    elif args.mode == 'execute-now':
        print("⚡ Executing immediately...")
        asyncio.run(execute_now())
    elif args.mode == 'status':
        print("📋 Showing status...")
        show_status() 
