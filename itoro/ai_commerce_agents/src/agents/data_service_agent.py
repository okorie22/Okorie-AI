"""
📊 Data Service Agent
Uploads and sells datasets on platforms like Ocean Protocol, Dune, or custom APIs

This agent packages trading data, strategy metadata, and analytics into monetizable
datasets that can be sold on decentralized marketplaces or accessed via paid APIs.
"""

import os
import json
import time
import asyncio
import threading
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

from ..shared.config import (
    DATA_SERVICE_UPDATE_INTERVAL, OCEAN_MARKET_URL, OCEAN_NETWORK,
    DUNE_API_KEY, DUNE_USERNAME, RAPIDAPI_KEY, DEBUG_MODE
)
from ..shared.database import get_database_manager, TradingSignal, WhaleRanking, StrategyMetadata, ExecutedTrade
from ..shared.utils import (
    export_to_csv, export_to_json, api_key_manager, rate_limiter, require_api_key,
    log_execution, format_currency, generate_unique_id, chunk_list
)
from .pricing import get_pricing_engine

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 📋 DATA MODELS
# =============================================================================

@dataclass
class Dataset:
    """Dataset metadata model"""
    dataset_id: str
    name: str
    description: str
    data_type: str  # 'signals', 'whale_rankings', 'strategy_metadata', 'trades', 'analytics'
    format: str  # 'csv', 'json', 'parquet'
    size_bytes: int
    record_count: int
    price_usd: float
    currency: str
    marketplaces: List[str]  # ['ocean', 'dune', 'rapidapi', 'custom']
    marketplace_ids: Dict[str, str]  # marketplace -> external_id mapping
    tags: List[str]
    created_at: datetime
    updated_at: Optional[datetime] = None
    download_count: int = 0
    revenue_generated: float = 0.0
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dataset':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'updated_at' in data_copy and data_copy['updated_at']:
            data_copy['updated_at'] = datetime.fromisoformat(data_copy['updated_at'])
        return cls(**data_copy)

@dataclass
class DatasetSale:
    """Dataset sale tracking model"""
    sale_id: str
    dataset_id: str
    buyer_id: str
    marketplace: str
    price_paid: float
    currency: str
    transaction_hash: Optional[str] = None
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatasetSale':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'expires_at' in data_copy and data_copy['expires_at']:
            data_copy['expires_at'] = datetime.fromisoformat(data_copy['expires_at'])
        return cls(**data_copy)

# =============================================================================
# 📊 DATA SERVICE AGENT
# =============================================================================

class DataServiceAgent:
    """Agent for packaging and selling trading datasets"""

    def __init__(self):
        self.db = get_database_manager()
        self.pricing = get_pricing_engine()

        # Initialize marketplace clients
        self._init_ocean_protocol()
        self._init_dune_analytics()
        self._init_rapidapi()

        # Data storage
        self.datasets: Dict[str, Dataset] = {}
        self.dataset_sales: List[DatasetSale] = []

        # Control flags
        self.running = False
        self.update_thread = None
        self.upload_executor = ThreadPoolExecutor(max_workers=5)

        # Local storage paths
        self.datasets_dir = os.path.join('data', 'datasets')
        self.exports_dir = os.path.join('data', 'exports')
        os.makedirs(self.datasets_dir, exist_ok=True)
        os.makedirs(self.exports_dir, exist_ok=True)

        # Load existing data
        self._load_datasets()
        self._load_sales()

        logger.info("✅ Data Service Agent initialized")

    def _init_ocean_protocol(self):
        """Initialize Ocean Protocol client"""
        self.ocean_session = requests.Session()
        # Ocean Protocol integration would require their SDK
        # For now, we'll prepare the structure
        logger.info("✅ Ocean Protocol integration ready")

    def _init_dune_analytics(self):
        """Initialize Dune Analytics client"""
        self.dune_session = requests.Session()
        if DUNE_API_KEY:
            self.dune_session.headers.update({
                'Authorization': f'Bearer {DUNE_API_KEY}',
                'Content-Type': 'application/json'
            })
            logger.info("✅ Dune Analytics integration initialized")
        else:
            logger.warning("⚠️  Dune API key not configured")

    def _init_rapidapi(self):
        """Initialize RapidAPI client"""
        self.rapidapi_session = requests.Session()
        if RAPIDAPI_KEY:
            self.rapidapi_session.headers.update({
                'X-RapidAPI-Key': RAPIDAPI_KEY,
                'X-RapidAPI-Host': 'your-api-host'  # Would be configured per API
            })
            logger.info("✅ RapidAPI integration initialized")
        else:
            logger.warning("⚠️  RapidAPI key not configured")

    def _load_datasets(self):
        """Load datasets from storage"""
        # In a real implementation, this would load from cloud storage
        self.datasets = {}

    def _load_sales(self):
        """Load sales data from storage"""
        # In a real implementation, this would load from cloud storage
        self.dataset_sales = []

    # =========================================================================
    # 🚀 CORE FUNCTIONALITY
    # =========================================================================

    def start(self):
        """Start the data service agent"""
        if self.running:
            logger.warning("Data Service Agent is already running")
            return

        self.running = True
        self.update_thread = threading.Thread(target=self._dataset_update_loop, daemon=True)
        self.update_thread.start()

        logger.info("🚀 Data Service Agent started")

    def stop(self):
        """Stop the data service agent"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)

        self.upload_executor.shutdown(wait=True)
        logger.info("🛑 Data Service Agent stopped")

    def _dataset_update_loop(self):
        """Main dataset creation and marketplace sync loop"""
        logger.info("📊 Starting dataset update loop")

        while self.running:
            try:
                # Create new datasets from fresh data
                self._create_datasets_from_new_data()

                # Sync existing datasets with marketplaces
                self._sync_marketplaces()

                # Clean up old temporary files
                self._cleanup_temp_files()

                # Sleep until next update
                time.sleep(DATA_SERVICE_UPDATE_INTERVAL)

            except Exception as e:
                logger.error(f"❌ Error in dataset update loop: {e}")
                time.sleep(60)  # Wait before retrying

    def _create_datasets_from_new_data(self):
        """Create new datasets from recent trading data"""
        try:
            # Create signal datasets
            self._create_signal_dataset()

            # Create whale ranking datasets
            self._create_whale_ranking_dataset()

            # Create strategy metadata datasets
            self._create_strategy_metadata_dataset()

            # Create trade history datasets
            self._create_trade_history_dataset()

            # Create analytics datasets
            self._create_analytics_dataset()

            logger.info("✅ Created datasets from new trading data")

        except Exception as e:
            logger.error(f"❌ Failed to create datasets: {e}")

    def _create_signal_dataset(self):
        """Create trading signals dataset"""
        try:
            # Get recent signals (last 30 days)
            signals = self.db.get_trading_signals(days_back=30, limit=10000)

            if len(signals) < 100:  # Minimum threshold
                return

            # Convert to DataFrame
            signal_data = []
            for signal in signals:
                signal_data.append({
                    'timestamp': signal.timestamp,
                    'symbol': signal.symbol,
                    'action': signal.action,
                    'confidence': signal.confidence,
                    'price': signal.price,
                    'volume': signal.volume,
                    'source_agent': signal.source_agent,
                    'signal_id': signal.signal_id
                })

            df = pd.DataFrame(signal_data)

            # Create dataset metadata
            dataset_id = f"signals_{int(time.time())}"
            dataset = Dataset(
                dataset_id=dataset_id,
                name=f"Trading Signals Dataset - {datetime.now().strftime('%Y-%m-%d')}",
                description="Real-time trading signals generated by AI agents across multiple strategies and timeframes",
                data_type="signals",
                format="csv",
                size_bytes=0,  # Will be calculated after export
                record_count=len(signals),
                price_usd=49.99,
                currency="USD",
                marketplaces=["ocean", "rapidapi"],
                marketplace_ids={},
                tags=["trading", "signals", "ai", "crypto", "forex", "stocks"],
                created_at=datetime.now()
            )

            # Export dataset
            filename = f"{dataset_id}.csv"
            filepath = export_to_csv(signal_data, filename, self.datasets_dir)

            if filepath:
                # Update size
                dataset.size_bytes = os.path.getsize(filepath)

                # Upload to marketplaces
                self._upload_dataset_to_marketplaces(dataset, filepath)

                # Store dataset metadata
                self.datasets[dataset_id] = dataset

                logger.info(f"✅ Created signal dataset: {dataset_id} ({len(signals)} signals)")

        except Exception as e:
            logger.error(f"❌ Failed to create signal dataset: {e}")

    def _create_whale_ranking_dataset(self):
        """Create whale wallet rankings dataset"""
        try:
            # Get whale rankings
            rankings = self.db.get_whale_rankings(limit=1000)

            if len(rankings) < 50:  # Minimum threshold
                return

            # Convert to DataFrame
            ranking_data = []
            for ranking in rankings:
                ranking_data.append({
                    'address': ranking.address,
                    'twitter_handle': ranking.twitter_handle,
                    'pnl_30d': ranking.pnl_30d,
                    'pnl_7d': ranking.pnl_7d,
                    'pnl_1d': ranking.pnl_1d,
                    'winrate_7d': ranking.winrate_7d,
                    'txs_30d': ranking.txs_30d,
                    'token_active': ranking.token_active,
                    'last_active': ranking.last_active,
                    'is_blue_verified': ranking.is_blue_verified,
                    'avg_holding_period_7d': ranking.avg_holding_period_7d,
                    'score': ranking.score,
                    'rank': ranking.rank,
                    'last_updated': ranking.last_updated
                })

            # Create dataset metadata
            dataset_id = f"whale_rankings_{int(time.time())}"
            dataset = Dataset(
                dataset_id=dataset_id,
                name=f"Whale Wallet Rankings - {datetime.now().strftime('%Y-%m-%d')}",
                description="Comprehensive ranking of top-performing cryptocurrency whale wallets with performance metrics",
                data_type="whale_rankings",
                format="csv",
                size_bytes=0,
                record_count=len(rankings),
                price_usd=29.99,
                currency="USD",
                marketplaces=["ocean", "dune"],
                marketplace_ids={},
                tags=["whales", "wallets", "crypto", "rankings", "performance"],
                created_at=datetime.now()
            )

            # Export dataset
            filename = f"{dataset_id}.csv"
            filepath = export_to_csv(ranking_data, filename, self.datasets_dir)

            if filepath:
                dataset.size_bytes = os.path.getsize(filepath)
                self._upload_dataset_to_marketplaces(dataset, filepath)
                self.datasets[dataset_id] = dataset

                logger.info(f"✅ Created whale ranking dataset: {dataset_id} ({len(rankings)} wallets)")

        except Exception as e:
            logger.error(f"❌ Failed to create whale ranking dataset: {e}")

    def _create_strategy_metadata_dataset(self):
        """Create strategy performance metadata dataset"""
        try:
            # Get strategy metadata
            strategies = self.db.get_strategy_metadata()

            if len(strategies) < 5:  # Minimum threshold
                return

            # Convert to DataFrame
            strategy_data = []
            for strategy in strategies:
                strategy_data.append({
                    'strategy_id': strategy.strategy_id,
                    'strategy_name': strategy.strategy_name,
                    'agent_type': strategy.agent_type,
                    'performance_metrics': json.dumps(strategy.performance_metrics),
                    'risk_metrics': json.dumps(strategy.risk_metrics),
                    'last_updated': strategy.last_updated,
                    'is_active': strategy.is_active
                })

            # Create dataset metadata
            dataset_id = f"strategy_metadata_{int(time.time())}"
            dataset = Dataset(
                dataset_id=dataset_id,
                name=f"Strategy Performance Metadata - {datetime.now().strftime('%Y-%m-%d')}",
                description="Detailed performance and risk metrics for AI trading strategies",
                data_type="strategy_metadata",
                format="json",
                size_bytes=0,
                record_count=len(strategies),
                price_usd=39.99,
                currency="USD",
                marketplaces=["ocean", "rapidapi"],
                marketplace_ids={},
                tags=["strategies", "performance", "risk", "ai", "trading"],
                created_at=datetime.now()
            )

            # Export dataset
            filename = f"{dataset_id}.json"
            filepath = export_to_json(strategy_data, filename, self.datasets_dir)

            if filepath:
                dataset.size_bytes = os.path.getsize(filepath)
                self._upload_dataset_to_marketplaces(dataset, filepath)
                self.datasets[dataset_id] = dataset

                logger.info(f"✅ Created strategy metadata dataset: {dataset_id} ({len(strategies)} strategies)")

        except Exception as e:
            logger.error(f"❌ Failed to create strategy metadata dataset: {e}")

    def _create_trade_history_dataset(self):
        """Create executed trades dataset"""
        try:
            # Get recent trades (last 90 days)
            trades = self.db.get_executed_trades(days_back=90, limit=50000)

            if len(trades) < 1000:  # Minimum threshold
                return

            # Convert to DataFrame
            trade_data = []
            for trade in trades:
                trade_data.append({
                    'timestamp': trade.timestamp,
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'quantity': trade.quantity,
                    'price': trade.price,
                    'value_usd': trade.value_usd,
                    'pnl_realized': trade.pnl_realized,
                    'source_agent': trade.source_agent,
                    'trade_id': trade.trade_id
                })

            # Create dataset metadata
            dataset_id = f"trade_history_{int(time.time())}"
            dataset = Dataset(
                dataset_id=dataset_id,
                name=f"Trade Execution History - {datetime.now().strftime('%Y-%m-%d')}",
                description="Complete history of executed trades across all AI agents and strategies",
                data_type="trades",
                format="csv",
                size_bytes=0,
                record_count=len(trades),
                price_usd=79.99,
                currency="USD",
                marketplaces=["ocean", "dune"],
                marketplace_ids={},
                tags=["trades", "execution", "history", "ai", "performance"],
                created_at=datetime.now()
            )

            # Export dataset
            filename = f"{dataset_id}.csv"
            filepath = export_to_csv(trade_data, filename, self.datasets_dir)

            if filepath:
                dataset.size_bytes = os.path.getsize(filepath)
                self._upload_dataset_to_marketplaces(dataset, filepath)
                self.datasets[dataset_id] = dataset

                logger.info(f"✅ Created trade history dataset: {dataset_id} ({len(trades)} trades)")

        except Exception as e:
            logger.error(f"❌ Failed to create trade history dataset: {e}")

    def _create_analytics_dataset(self):
        """Create comprehensive analytics dataset"""
        try:
            # Gather various analytics
            signal_stats = self.db.get_signal_stats(days_back=30)
            whale_stats = self.db.get_whale_stats()
            strategy_stats = self.db.get_strategy_stats()

            analytics_data = {
                'generated_at': datetime.now().isoformat(),
                'period_days': 30,
                'signal_analytics': signal_stats,
                'whale_analytics': whale_stats,
                'strategy_analytics': strategy_stats,
                'market_summary': {
                    'total_signals': signal_stats.get('total_signals', 0),
                    'total_whales_tracked': whale_stats.get('total_whales', 0),
                    'active_strategies': strategy_stats.get('total_strategies', 0)
                }
            }

            # Create dataset metadata
            dataset_id = f"analytics_{int(time.time())}"
            dataset = Dataset(
                dataset_id=dataset_id,
                name=f"Trading Analytics Report - {datetime.now().strftime('%Y-%m-%d')}",
                description="Comprehensive analytics report combining signal performance, whale tracking, and strategy metrics",
                data_type="analytics",
                format="json",
                size_bytes=0,
                record_count=1,  # Single analytics document
                price_usd=19.99,
                currency="USD",
                marketplaces=["rapidapi"],
                marketplace_ids={},
                tags=["analytics", "performance", "metrics", "reports"],
                created_at=datetime.now()
            )

            # Export dataset
            filename = f"{dataset_id}.json"
            filepath = export_to_json([analytics_data], filename, self.datasets_dir)

            if filepath:
                dataset.size_bytes = os.path.getsize(filepath)
                self._upload_dataset_to_marketplaces(dataset, filepath)
                self.datasets[dataset_id] = dataset

                logger.info(f"✅ Created analytics dataset: {dataset_id}")

        except Exception as e:
            logger.error(f"❌ Failed to create analytics dataset: {e}")

    def _upload_dataset_to_marketplaces(self, dataset: Dataset, filepath: str):
        """Upload dataset to configured marketplaces"""
        for marketplace in dataset.marketplaces:
            try:
                if marketplace == 'ocean':
                    self.upload_executor.submit(self._upload_to_ocean_protocol, dataset, filepath)
                elif marketplace == 'dune':
                    self.upload_executor.submit(self._upload_to_dune_analytics, dataset, filepath)
                elif marketplace == 'rapidapi':
                    self.upload_executor.submit(self._upload_to_rapidapi, dataset, filepath)
            except Exception as e:
                logger.error(f"❌ Failed to queue upload to {marketplace}: {e}")

    def _upload_to_ocean_protocol(self, dataset: Dataset, filepath: str):
        """Upload dataset to Ocean Protocol"""
        try:
            # This would integrate with Ocean Protocol SDK
            # For now, simulate the upload process
            logger.info(f"📤 Uploading {dataset.dataset_id} to Ocean Protocol...")

            # Simulate API call
            time.sleep(2)  # Simulate network delay

            # Store marketplace ID
            marketplace_id = f"ocean_{dataset.dataset_id}_{int(time.time())}"
            dataset.marketplace_ids['ocean'] = marketplace_id

            logger.info(f"✅ Uploaded {dataset.dataset_id} to Ocean Protocol: {marketplace_id}")

        except Exception as e:
            logger.error(f"❌ Failed to upload to Ocean Protocol: {e}")

    def _upload_to_dune_analytics(self, dataset: Dataset, filepath: str):
        """Upload dataset to Dune Analytics"""
        try:
            logger.info(f"📤 Uploading {dataset.dataset_id} to Dune Analytics...")

            # Read file content
            with open(filepath, 'rb') as f:
                file_content = f.read()

            # Prepare upload payload (Dune API structure)
            payload = {
                'query_name': dataset.name,
                'description': dataset.description,
                'tags': dataset.tags,
                'is_private': False
            }

            # This would make actual API call to Dune
            # response = self.dune_session.post('https://api.dune.com/api/v1/query/upload', json=payload)

            # Simulate successful upload
            time.sleep(1)
            marketplace_id = f"dune_{dataset.dataset_id}_{int(time.time())}"
            dataset.marketplace_ids['dune'] = marketplace_id

            logger.info(f"✅ Uploaded {dataset.dataset_id} to Dune Analytics: {marketplace_id}")

        except Exception as e:
            logger.error(f"❌ Failed to upload to Dune Analytics: {e}")

    def _upload_to_rapidapi(self, dataset: Dataset, filepath: str):
        """Upload dataset to RapidAPI"""
        try:
            logger.info(f"📤 Uploading {dataset.dataset_id} to RapidAPI...")

            # Simulate API deployment
            time.sleep(1)
            marketplace_id = f"rapidapi_{dataset.dataset_id}_{int(time.time())}"
            dataset.marketplace_ids['rapidapi'] = marketplace_id

            logger.info(f"✅ Uploaded {dataset.dataset_id} to RapidAPI: {marketplace_id}")

        except Exception as e:
            logger.error(f"❌ Failed to upload to RapidAPI: {e}")

    def _sync_marketplaces(self):
        """Sync dataset metadata with marketplaces"""
        # This would update pricing, availability, etc. on marketplaces
        logger.debug("🔄 Syncing datasets with marketplaces...")

    def _cleanup_temp_files(self):
        """Clean up old temporary dataset files"""
        try:
            # Keep only last 10 datasets per type
            dataset_types = {}
            for dataset in self.datasets.values():
                if dataset.data_type not in dataset_types:
                    dataset_types[dataset.data_type] = []
                dataset_types[dataset.data_type].append((dataset.created_at, dataset.dataset_id))

            for data_type, datasets in dataset_types.items():
                if len(datasets) > 10:
                    # Sort by creation date (oldest first)
                    datasets.sort()
                    to_remove = datasets[:-10]  # Keep newest 10

                    for _, dataset_id in to_remove:
                        # Remove from storage
                        self.datasets.pop(dataset_id, None)

                        # Remove files
                        for ext in ['.csv', '.json', '.zip']:
                            filepath = os.path.join(self.datasets_dir, f"{dataset_id}{ext}")
                            if os.path.exists(filepath):
                                os.remove(filepath)

            logger.debug("🧹 Cleaned up old dataset files")

        except Exception as e:
            logger.error(f"❌ Failed to cleanup temp files: {e}")

    # =========================================================================
    # 📊 API ENDPOINTS
    # =========================================================================

    @require_api_key
    def get_available_datasets(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """API endpoint to get available datasets"""
        try:
            # Record API usage
            self.pricing.record_api_usage(
                user_id=user_info['user_id'],
                endpoint='dataset_listing'
            )

            # Get active datasets
            active_datasets = [
                dataset for dataset in self.datasets.values()
                if dataset.is_active
            ]

            # Format for API response
            dataset_list = []
            for dataset in active_datasets:
                dataset_list.append({
                    'dataset_id': dataset.dataset_id,
                    'name': dataset.name,
                    'description': dataset.description,
                    'data_type': dataset.data_type,
                    'format': dataset.format,
                    'record_count': dataset.record_count,
                    'size_mb': round(dataset.size_bytes / (1024 * 1024), 2),
                    'price_usd': dataset.price_usd,
                    'tags': dataset.tags,
                    'marketplaces': dataset.marketplaces,
                    'created_at': dataset.created_at.isoformat(),
                    'download_count': dataset.download_count
                })

            return {
                'status': 'success',
                'datasets': dataset_list,
                'count': len(dataset_list),
                'user_tier': user_info.get('tier', 'free')
            }

        except Exception as e:
            logger.error(f"❌ Error getting available datasets: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def purchase_dataset(self, user_info: Dict[str, Any], dataset_id: str,
                        payment_method: str = 'stripe') -> Dict[str, Any]:
        """API endpoint to purchase a dataset"""
        try:
            # Check if dataset exists
            dataset = self.datasets.get(dataset_id)
            if not dataset or not dataset.is_active:
                return {'error': 'Dataset not found or unavailable', 'status': 'error'}

            # Check user tier limits
            allowed, message = self.pricing.check_tier_limits(
                user_info['user_id'], 'data_access'
            )
            if not allowed:
                return {'error': message, 'status': 'error'}

            # Process payment (would integrate with payment processor)
            # For now, simulate successful payment
            transaction_id = self.pricing.record_data_sale(
                user_id=user_info['user_id'],
                dataset_type=dataset.data_type,
                amount=dataset.price_usd,
                payment_method=payment_method
            )

            # Create sale record
            sale = DatasetSale(
                sale_id=generate_unique_id('sale'),
                dataset_id=dataset_id,
                buyer_id=user_info['user_id'],
                marketplace='api',
                price_paid=dataset.price_usd,
                currency='USD',
                transaction_hash=transaction_id,
                download_url=self._generate_download_url(dataset),
                expires_at=datetime.now() + timedelta(days=30),  # 30-day access
                created_at=datetime.now()
            )

            self.dataset_sales.append(sale)
            dataset.download_count += 1
            dataset.revenue_generated += dataset.price_usd

            return {
                'status': 'success',
                'sale_id': sale.sale_id,
                'dataset_id': dataset_id,
                'download_url': sale.download_url,
                'expires_at': sale.expires_at.isoformat(),
                'transaction_id': transaction_id
            }

        except Exception as e:
            logger.error(f"❌ Error purchasing dataset: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def download_dataset(self, user_info: Dict[str, Any], sale_id: str) -> Dict[str, Any]:
        """API endpoint to download a purchased dataset"""
        try:
            # Find sale record
            sale = None
            for s in self.dataset_sales:
                if s.sale_id == sale_id and s.buyer_id == user_info['user_id']:
                    sale = s
                    break

            if not sale:
                return {'error': 'Sale not found or access denied', 'status': 'error'}

            # Check if access hasn't expired
            if sale.expires_at and datetime.now() > sale.expires_at:
                return {'error': 'Access expired', 'status': 'error'}

            # Get dataset
            dataset = self.datasets.get(sale.dataset_id)
            if not dataset:
                return {'error': 'Dataset not found', 'status': 'error'}

            # Generate download link (would be pre-signed URL in production)
            filepath = os.path.join(self.datasets_dir, f"{dataset.dataset_id}.{dataset.format}")

            if not os.path.exists(filepath):
                return {'error': 'Dataset file not available', 'status': 'error'}

            # Read file content (in production, this would be a download URL)
            with open(filepath, 'rb') as f:
                file_content = f.read()

            return {
                'status': 'success',
                'dataset_id': dataset.dataset_id,
                'filename': f"{dataset.dataset_id}.{dataset.format}",
                'content_type': 'application/octet-stream',
                'file_size': len(file_content),
                'expires_at': sale.expires_at.isoformat() if sale.expires_at else None
            }

        except Exception as e:
            logger.error(f"❌ Error downloading dataset: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    def _generate_download_url(self, dataset: Dataset) -> str:
        """Generate download URL for dataset"""
        # In production, this would be a secure, time-limited URL
        return f"/api/datasets/download/{dataset.dataset_id}"

    @require_api_key
    def get_dataset_stats(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """API endpoint to get dataset statistics"""
        try:
            # Get user's purchase history
            user_sales = [
                sale for sale in self.dataset_sales
                if sale.buyer_id == user_info['user_id']
            ]

            total_spent = sum(sale.price_paid for sale in user_sales)
            total_downloads = len(user_sales)

            # Get available datasets by type
            dataset_types = {}
            for dataset in self.datasets.values():
                if dataset.is_active:
                    dataset_types[dataset.data_type] = dataset_types.get(dataset.data_type, 0) + 1

            return {
                'status': 'success',
                'user_stats': {
                    'total_purchases': total_downloads,
                    'total_spent_usd': total_spent,
                    'active_downloads': len([s for s in user_sales if not s.expires_at or s.expires_at > datetime.now()])
                },
                'available_datasets': {
                    'total': len([d for d in self.datasets.values() if d.is_active]),
                    'by_type': dataset_types
                },
                'marketplace_distribution': self._get_marketplace_distribution()
            }

        except Exception as e:
            logger.error(f"❌ Error getting dataset stats: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    def _get_marketplace_distribution(self) -> Dict[str, int]:
        """Get distribution of datasets across marketplaces"""
        distribution = {}
        for dataset in self.datasets.values():
            if dataset.is_active:
                for marketplace in dataset.marketplaces:
                    distribution[marketplace] = distribution.get(marketplace, 0) + 1
        return distribution

    # =========================================================================
    # 📈 ANALYTICS & MONITORING
    # =========================================================================

    def get_revenue_stats(self) -> Dict[str, Any]:
        """Get dataset revenue statistics"""
        total_revenue = sum(dataset.revenue_generated for dataset in self.datasets.values())
        total_downloads = sum(dataset.download_count for dataset in self.datasets.values())

        # Revenue by data type
        revenue_by_type = {}
        downloads_by_type = {}

        for dataset in self.datasets.values():
            revenue_by_type[dataset.data_type] = revenue_by_type.get(dataset.data_type, 0) + dataset.revenue_generated
            downloads_by_type[dataset.data_type] = downloads_by_type.get(dataset.data_type, 0) + dataset.download_count

        # Recent sales (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_sales = [
            sale for sale in self.dataset_sales
            if sale.created_at >= thirty_days_ago
        ]

        return {
            'total_revenue_usd': total_revenue,
            'total_downloads': total_downloads,
            'average_price_per_dataset': total_revenue / max(total_downloads, 1),
            'revenue_by_type': revenue_by_type,
            'downloads_by_type': downloads_by_type,
            'recent_sales_count': len(recent_sales),
            'recent_sales_revenue': sum(sale.price_paid for sale in recent_sales)
        }

    def get_marketplace_performance(self) -> Dict[str, Any]:
        """Get performance metrics by marketplace"""
        marketplace_stats = {}

        for dataset in self.datasets.values():
            for marketplace in dataset.marketplaces:
                if marketplace not in marketplace_stats:
                    marketplace_stats[marketplace] = {
                        'datasets': 0,
                        'downloads': 0,
                        'revenue': 0.0
                    }

                marketplace_stats[marketplace]['datasets'] += 1
                marketplace_stats[marketplace]['downloads'] += dataset.download_count
                marketplace_stats[marketplace]['revenue'] += dataset.revenue_generated

        return marketplace_stats

    # =========================================================================
    # 🔧 UTILITY METHODS
    # =========================================================================

    def create_custom_dataset(self, name: str, description: str, data: List[Dict[str, Any]],
                            price_usd: float, tags: List[str] = None) -> Optional[str]:
        """Create a custom dataset from provided data"""
        try:
            dataset_id = generate_unique_id('custom_dataset')

            # Export data
            filename = f"{dataset_id}.json"
            filepath = export_to_json(data, filename, self.datasets_dir)

            if not filepath:
                return None

            # Create dataset metadata
            dataset = Dataset(
                dataset_id=dataset_id,
                name=name,
                description=description,
                data_type="custom",
                format="json",
                size_bytes=os.path.getsize(filepath),
                record_count=len(data),
                price_usd=price_usd,
                currency="USD",
                marketplaces=["rapidapi"],  # Custom datasets go to API marketplace
                marketplace_ids={},
                tags=tags or ["custom", "dataset"],
                created_at=datetime.now()
            )

            # Upload to marketplace
            self._upload_dataset_to_marketplaces(dataset, filepath)

            # Store dataset
            self.datasets[dataset_id] = dataset

            logger.info(f"✅ Created custom dataset: {dataset_id}")
            return dataset_id

        except Exception as e:
            logger.error(f"❌ Failed to create custom dataset: {e}")
            return None

    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return {
            'agent': 'DataServiceAgent',
            'running': self.running,
            'active_datasets': len([d for d in self.datasets.values() if d.is_active]),
            'total_datasets': len(self.datasets),
            'total_sales': len(self.dataset_sales),
            'ocean_enabled': True,  # Ocean Protocol integration ready
            'dune_enabled': DUNE_API_KEY is not None,
            'rapidapi_enabled': RAPIDAPI_KEY is not None,
            'datasets_dir_size_mb': self._get_datasets_dir_size() / (1024 * 1024),
            'last_update': datetime.now().isoformat()
        }

    def _get_datasets_dir_size(self) -> int:
        """Get total size of datasets directory"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.datasets_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            return total_size
        except:
            return 0

# =============================================================================
# 🏭 FACTORY FUNCTION
# =============================================================================

_data_service_agent = None

def get_data_service_agent() -> DataServiceAgent:
    """
    Factory function to get data service agent (singleton)

    Returns:
        DataServiceAgent instance
    """
    global _data_service_agent
    if _data_service_agent is None:
        _data_service_agent = get_data_service_agent()
    return _data_service_agent

# =============================================================================
# 🧪 TEST FUNCTIONS
# =============================================================================

def test_data_service_agent():
    """Test data service agent functionality"""
    print("🧪 Testing Data Service Agent...")

    try:
        agent = DataServiceAgent()

        # Test health check
        health = agent.health_check()
        print(f"✅ Agent health: {health}")

        # Test dataset creation (would create actual datasets)
        # dataset_id = agent.create_custom_dataset(
        #     name="Test Dataset",
        #     description="A test dataset",
        #     data=[{"test": "data"}],
        #     price_usd=9.99
        # )
        # print(f"✅ Created custom dataset: {dataset_id}")

        # Test revenue stats
        revenue_stats = agent.get_revenue_stats()
        print(f"✅ Revenue stats: {revenue_stats}")

        print("🎉 Data Service Agent tests completed!")

    except Exception as e:
        print(f"❌ Data Service Agent test failed: {e}")

if __name__ == "__main__":
    test_data_service_agent()
