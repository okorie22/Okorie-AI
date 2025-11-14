import os
import json
import time
from datetime import datetime
from typing import Optional, List

import requests
from src.scripts.shared_services.logger import info


class RestDatabaseManager:
    """
    Minimal Supabase REST manager used when direct Postgres connectivity is
    unavailable. Implements only the methods used by the app and tests.
    """

    def __init__(self) -> None:
        supabase_url = os.getenv('SUPABASE_URL', '').rstrip('/')
        service_role = os.getenv('SUPABASE_SERVICE_ROLE', '')
        if not supabase_url or not service_role:
            raise ValueError('SUPABASE_URL or SUPABASE_SERVICE_ROLE not set')

        self.base_url = f"{supabase_url}/rest/v1"
        self.headers = {
            'Authorization': f"Bearer {service_role}",
            'apikey': service_role,
            'Content-Type': 'application/json',
        }
    
    def _test_connection(self) -> bool:
        """Test if the REST API connection is working"""
        try:
            # Test with a simple query
            test_url = f"{self.base_url}/paper_trading_portfolio"
            params = {'select': 'id', 'limit': 1}
            response = requests.get(test_url, headers=self.headers, params=params, timeout=10)
            return response.ok
        except Exception:
            return False

    # --------------- helpers ---------------
    def _post(self, path: str, payload: dict, upsert: Optional[str] = None) -> bool:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = dict(self.headers)
        # Ask Supabase to return representation to detect success
        headers['Prefer'] = 'return=representation'
        if upsert:
            headers['Prefer'] = headers['Prefer'] + f",resolution={upsert}"
        rsp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        return rsp.ok

    def _get(self, path: str, params: dict) -> Optional[List[dict]]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        rsp = requests.get(url, headers=self.headers, params=params, timeout=15)
        if not rsp.ok:
            return None
        try:
            return rsp.json()
        except Exception:
            return None

    # --------------- portfolio API ---------------
    def save_paper_trading_portfolio(self, portfolio_data: dict) -> bool:
        payload = {
            'total_value_usd': portfolio_data.get('total_value', 0.0),
            'usdc_balance': portfolio_data.get('usdc_balance', 0.0),
            'sol_balance': portfolio_data.get('sol_balance', 0.0),
            'sol_value_usd': portfolio_data.get('sol_value_usd', 0.0),
            'positions_value_usd': portfolio_data.get('positions_value_usd', 0.0),
            'change_detected': portfolio_data.get('change_detected', False),
            'change_type': portfolio_data.get('change_type', 'unknown'),
            'metadata': portfolio_data.get('metadata', {}),
        }
        return self._post('paper_trading_portfolio', payload)

    def get_latest_paper_trading_portfolio(self):
        rows = self._get('paper_trading_portfolio', {
            'select': '*',
            'order': 'timestamp.desc',
            'limit': 1,
        })
        return rows[0] if rows else None

    def save_paper_trading_transaction(self, tx: dict) -> bool:
        payload = {
            'transaction_id': tx.get('transaction_id', ''),
            'transaction_type': tx.get('transaction_type', ''),
            'token_mint': tx.get('token_mint', ''),
            'token_symbol': tx.get('token_symbol', ''),
            'amount': tx.get('amount', 0.0),
            'price_usd': tx.get('price_usd', 0.0),
            'value_usd': tx.get('value_usd', 0.0),
            'usdc_amount': tx.get('usdc_amount', 0.0),
            'sol_amount': tx.get('sol_amount', 0.0),
            'agent_name': tx.get('agent_name', ''),
            'metadata': tx.get('metadata', {}),
        }
        return self._post('paper_trading_transactions', payload)

    def get_paper_trading_transactions(self, limit: int = 100):
        rows = self._get('paper_trading_transactions', {
            'select': '*',
            'order': 'timestamp.desc',
            'limit': limit,
        })
        return rows or []

    # --------------- live portfolio/trades (minimal) ---------------
    def upsert_live_portfolio_snapshot(self, total_value_usd: float, usdc_balance: float,
                                       sol_balance: float, sol_value_usd: float,
                                       positions_value_usd: float,
                                       metadata: Optional[dict] = None) -> bool:
        payload = {
            'total_value_usd': total_value_usd,
            'usdc_balance': usdc_balance,
            'sol_balance': sol_balance,
            'sol_value_usd': sol_value_usd,
            'positions_value_usd': positions_value_usd,
            'change_detected': True,
            'change_type': 'status_update',
            'metadata': metadata or {},
        }
        return self._post('portfolio_history', payload)

    def add_live_trade(self, signature: str, side: str, size: float, price_usd: float,
                       usd_value: float, agent: str, token_mint: str,
                       metadata: Optional[dict] = None, token_symbol: str = None, token_name: str = None) -> bool:
        # Fetch metadata if not provided
        if not token_symbol or not token_name:
            try:
                from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                metadata_service = get_token_metadata_service()
                token_metadata = metadata_service.get_metadata(token_mint)
                if token_metadata:
                    token_symbol = token_metadata.get('symbol', 'UNK')
                    token_name = token_metadata.get('name', 'Unknown Token')
            except:
                pass
        
        token_symbol = token_symbol or 'UNK'
        token_name = token_name or 'Unknown Token'
        
        payload = {
            'signature': signature,
            'side': side,
            'size': size,
            'price_usd': price_usd,
            'usd_value': usd_value,
            'agent': agent,
            'token_mint': token_mint,
            'metadata': metadata or {},
            'token_symbol': token_symbol,
            'token_name': token_name,
        }
        return self._post('live_trades', payload)

    def get_recent_live_trades(self, limit: int = 5) -> List[dict]:
        rows = self._get('live_trades', {
            'select': '*',
            'order': 'timestamp.desc',
            'limit': limit,
        })
        return rows or []

    # --------------- agent shared data ---------------
    def save_agent_data(self, agent_name: str, data_type: str, data: dict) -> bool:
        payload = {
            'agent_name': agent_name,
            'data_type': data_type,
            'data': data,
        }
        # Upsert on the unique (agent_name, data_type)
        return self._post('agent_shared_data', payload, upsert='merge-duplicates')

    def get_agent_data(self, agent_name: str = None, data_type: str = None):
        params = {'select': '*', 'order': 'timestamp.desc'}
        if agent_name:
            params['agent_name'] = f"eq.{agent_name}"
        if data_type:
            params['data_type'] = f"eq.{data_type}"
        rows = self._get('agent_shared_data', params)
        return rows or []

    def execute_query(self, query: str, params: tuple = None, fetch: str = "all") -> List[dict]:
        """Execute a SQL query via REST API (limited functionality)."""
        # For REST, we can only do simple table operations
        # This is a stub to prevent attribute errors
        # Suppress REST query logging to avoid display overlap
        # print(f"REST execute_query called with: {query[:100]}... (fetch={fetch})")
        return []
    
    def clear_paper_trading_data(self) -> bool:
        """Clear all paper trading data from cloud database via REST API"""
        try:
            # Clear portfolio data - add query parameter to make DELETE work
            portfolio_url = f"{self.base_url}/paper_trading_portfolio?id=gt.0"
            portfolio_rsp = requests.delete(portfolio_url, headers=self.headers, timeout=15)
            
            # Clear transaction data - add query parameter to make DELETE work
            transaction_url = f"{self.base_url}/paper_trading_transactions?id=gt.0"
            transaction_rsp = requests.delete(transaction_url, headers=self.headers, timeout=15)
            
            if portfolio_rsp.ok and transaction_rsp.ok:
                info("✅ Cleared all paper trading data from cloud database via REST API", file_only=True)
                return True
            else:
                print(f"⚠️ Cloud database clearing had issues - portfolio: {portfolio_rsp.status_code}, transactions: {transaction_rsp.status_code}")
                return False
        except Exception as e:
            print(f"Failed to clear paper trading data from cloud via REST: {e}")
            return False

    # --------------- staking API ---------------
    def save_staking_transaction(self, transaction_data: dict) -> bool:
        """Save staking transaction to cloud database via REST"""
        try:
            return self._post('staking_transactions', transaction_data)
        except Exception as e:
            print(f"Failed to save staking transaction via REST: {e}")
            return False

    def save_staking_position(self, position_data: dict) -> bool:
        """Save staking position to cloud database via REST"""
        try:
            return self._post('staking_positions', position_data)
        except Exception as e:
            print(f"Failed to save staking position via REST: {e}")
            return False

    def get_staking_positions(self, wallet_address: str = None) -> Optional[List[dict]]:
        """Get staking positions from cloud database via REST"""
        try:
            params = {}
            if wallet_address:
                params['wallet_address'] = f"eq.{wallet_address}"
            return self._get('staking_positions', params)
        except Exception as e:
            print(f"Failed to get staking positions via REST: {e}")
            return None

    def get_staking_transactions(self, wallet_address: str = None, limit: int = 10) -> Optional[List[dict]]:
        """Get staking transactions from cloud database via REST"""
        try:
            params = {'limit': limit, 'order': 'timestamp.desc'}
            if wallet_address:
                params['wallet_address'] = f"eq.{wallet_address}"
            return self._get('staking_transactions', params)
        except Exception as e:
            print(f"Failed to get staking transactions via REST: {e}")
            return None

    # --------------- entry prices API ---------------
    def save_entry_price(self, mint: str, entry_price_usd: float, entry_amount: float, 
                        source: str = "manual", notes: str = "") -> bool:
        """Save entry price to cloud database via REST"""
        try:
            payload = {
                'token_mint': mint,
                'wallet_address': 'default',
                'entry_price_usd': entry_price_usd,
                'amount': entry_amount,
                'value_usd': entry_price_usd * entry_amount,
                'metadata': {
                    'source': source,
                    'notes': notes,
                    'entry_timestamp': time.time(),
                    'last_updated': time.time()
                }
            }
            return self._post('entry_prices', payload, upsert='merge-duplicates')
        except Exception as e:
            print(f"Failed to save entry price via REST: {e}")
            return False

    def get_entry_price(self, mint: str) -> Optional[dict]:
        """Get entry price from cloud database via REST"""
        try:
            rows = self._get('entry_prices', {
                'select': '*',
                'token_mint': f"eq.{mint}",
                'wallet_address': f"eq.default",
                'order': 'timestamp.desc',
                'limit': 1
            })
            return rows[0] if rows else None
        except Exception as e:
            print(f"Failed to get entry price via REST: {e}")
            return None

    def update_entry_price(self, mint: str, entry_price_usd: float, entry_amount: float,
                          source: str = "manual", notes: str = "") -> bool:
        """Update entry price in cloud database via REST"""
        try:
            payload = {
                'entry_price_usd': entry_price_usd,
                'amount': entry_amount,
                'value_usd': entry_price_usd * entry_amount,
                'metadata': {
                    'source': source,
                    'notes': notes,
                    'last_updated': time.time()
                }
            }
            # Use PATCH to update existing record
            url = f"{self.base_url}/entry_prices"
            params = {
                'token_mint': f"eq.{mint}",
                'wallet_address': f"eq.default"
            }
            headers = dict(self.headers)
            headers['Prefer'] = 'return=representation'

            response = requests.patch(url, headers=headers, params=params,
                                    data=json.dumps(payload), timeout=15)
            return response.ok
        except Exception as e:
            print(f"Failed to update entry price via REST: {e}")
            return False

    # --------------- chart analysis API ---------------
    def save_chart_analysis(self, analysis_data: dict) -> bool:
        """Save chart analysis to cloud database via REST"""
        try:
            payload = {
                'token_symbol': analysis_data.get('token_symbol', ''),
                'token_mint': analysis_data.get('token_mint', ''),
                'timeframe': analysis_data.get('timeframe', ''),
                'overall_sentiment': analysis_data.get('overall_sentiment', ''),
                'sentiment_score': analysis_data.get('sentiment_score', 0.0),
                'confidence': analysis_data.get('confidence', 0.0),
                'technical_indicators': analysis_data.get('technical_indicators', {}),
                'support_levels': analysis_data.get('support_levels', []),
                'resistance_levels': analysis_data.get('resistance_levels', []),
                'metadata': analysis_data.get('metadata', {})
            }
            return self._post('chart_analysis', payload)
        except Exception as e:
            print(f"Failed to save chart analysis via REST: {e}")
            return False

    def get_chart_analysis(self, token_symbol: str = None, limit: int = 10) -> Optional[List[dict]]:
        """Get chart analysis from cloud database via REST"""
        try:
            params = {'order': 'timestamp.desc', 'limit': limit}
            if token_symbol:
                params['token_symbol'] = f"eq.{token_symbol}"
            return self._get('chart_analysis', params)
        except Exception as e:
            print(f"Failed to get chart analysis via REST: {e}")
            return None

    # --------------- sentiment data API ---------------
    def save_sentiment_data(self, sentiment_data: dict) -> bool:
        """Save sentiment data to cloud database via REST"""
        try:
            payload = {
                'sentiment_type': sentiment_data.get('sentiment_type', 'twitter'),
                'overall_sentiment': sentiment_data.get('overall_sentiment', ''),
                'sentiment_score': sentiment_data.get('sentiment_score', 0.0),
                'confidence': sentiment_data.get('confidence', 50.0),
                'num_tokens_analyzed': sentiment_data.get('num_tokens_analyzed', 0),
                'num_tweets': sentiment_data.get('num_tweets', 0),
                'engagement_avg': sentiment_data.get('engagement_avg', 0.0),
                'ai_enhanced_score': sentiment_data.get('ai_enhanced_score'),
                'ai_model_used': sentiment_data.get('ai_model_used'),
                'tokens_analyzed': sentiment_data.get('tokens_analyzed', ''),
                'metadata': sentiment_data.get('metadata', {})
            }
            return self._post('sentiment_data', payload)
        except Exception as e:
            print(f"Failed to save sentiment data via REST: {e}")
            return False

    def get_sentiment_data(self, sentiment_type: str = None, limit: int = 10) -> Optional[List[dict]]:
        """Get sentiment data from cloud database via REST"""
        try:
            params = {'order': 'timestamp.desc', 'limit': limit}
            if sentiment_type:
                params['sentiment_type'] = f"eq.{sentiment_type}"
            return self._get('sentiment_data', params)
        except Exception as e:
            print(f"Failed to get sentiment data via REST: {e}")
            return None

    # --------------- whale data API ---------------
    def save_whale_data(self, whale_data_list: List[dict]) -> bool:
        """Save whale data to cloud database via REST"""
        try:
            success_count = 0
            for whale_data in whale_data_list:
                payload = {
                    'wallet_address': whale_data.get('wallet_address', ''),
                    'wallet_name': whale_data.get('wallet_name', ''),
                    'total_value_usd': whale_data.get('total_value_usd'),
                    'pnl_1d': whale_data.get('pnl_1d'),
                    'pnl_7d': whale_data.get('pnl_7d'),
                    'pnl_30d': whale_data.get('pnl_30d'),
                    'top_tokens': whale_data.get('top_tokens', []),
                    'trading_volume_24h': whale_data.get('trading_volume_24h'),
                    'risk_score': whale_data.get('risk_score'),
                    'is_active': whale_data.get('is_active', True),
                    'metadata': whale_data.get('metadata', {})
                }
                if self._post('whale_data', payload, upsert='merge-duplicates'):
                    success_count += 1
            return success_count > 0
        except Exception as e:
            print(f"Failed to save whale data via REST: {e}")
            return False

    def save_whale_history(self, history_data_list: List[dict]) -> bool:
        """Save whale history to cloud database via REST"""
        try:
            success_count = 0
            for history_data in history_data_list:
                payload = {
                    'wallet_address': history_data.get('wallet_address', ''),
                    'action_type': history_data.get('action_type', 'update'),
                    'token_mint': history_data.get('token_mint'),
                    'amount': history_data.get('amount'),
                    'value_usd': history_data.get('value_usd'),
                    'metadata': history_data.get('metadata', {})
                }
                if self._post('whale_history', payload):
                    success_count += 1
            return success_count > 0
        except Exception as e:
            print(f"Failed to save whale history via REST: {e}")
            return False

    def save_whale_schedules(self, schedule_data_list: List[dict]) -> bool:
        """Save whale schedules to cloud database via REST"""
        try:
            success_count = 0
            for schedule_data in schedule_data_list:
                payload = {
                    'wallet_address': schedule_data.get('wallet_address', ''),
                    'next_execution_time': schedule_data.get('next_execution_time'),
                    'last_update': schedule_data.get('last_update'),
                    'update_interval_hours': schedule_data.get('update_interval_hours', 24),
                    'is_active': schedule_data.get('is_active', True),
                    'metadata': schedule_data.get('metadata', {})
                }
                if self._post('whale_schedules', payload, upsert='merge-duplicates'):
                    success_count += 1
            return success_count > 0
        except Exception as e:
            print(f"Failed to save whale schedules via REST: {e}")
            return False

    def get_whale_data(self, wallet_address: str = None, limit: int = 10) -> Optional[List[dict]]:
        """Get whale data from cloud database via REST"""
        try:
            params = {'order': 'timestamp.desc', 'limit': limit}
            if wallet_address:
                params['wallet_address'] = f"eq.{wallet_address}"
            return self._get('whale_data', params)
        except Exception as e:
            print(f"Failed to get whale data via REST: {e}")
            return None

    def get_whale_history(self, wallet_address: str = None, limit: int = 10) -> Optional[List[dict]]:
        """Get whale history from cloud database via REST"""
        try:
            params = {'order': 'timestamp.desc', 'limit': limit}
            if wallet_address:
                params['wallet_address'] = f"eq.{wallet_address}"
            return self._get('whale_history', params)
        except Exception as e:
            print(f"Failed to get whale history via REST: {e}")
            return None

    def get_whale_schedules(self, wallet_address: str = None) -> Optional[List[dict]]:
        """Get whale schedules from cloud database via REST"""
        try:
            params = {}
            if wallet_address:
                params['wallet_address'] = f"eq.{wallet_address}"
            return self._get('whale_schedules', params)
        except Exception as e:
            print(f"Failed to get whale schedules via REST: {e}")
            return None

    # --------------- webhook events API ---------------
    def save_webhook_event(self, event: dict) -> bool:
        """Save webhook event to cloud database via REST API"""
        try:
            payload = {
                'signature': event.get('signature', ''),
                'timestamp': event.get('timestamp', int(time.time())),
                'type': event.get('type', 'unknown'),
                'accounts': event.get('accounts', []),
                'parsed_at': event.get('parsed_at', ''),
                'metadata': event.get('metadata', {})
            }
            return self._post('webhook_events', payload)
        except Exception as e:
            print(f"Failed to save webhook event via REST: {e}")
            return False

    def get_webhook_events(self, limit: int = 100) -> Optional[List[dict]]:
        """Get webhook events from cloud database via REST"""
        try:
            params = {
                'select': '*',
                'order': 'timestamp.desc',
                'limit': limit
            }
            return self._get('webhook_events', params)
        except Exception as e:
            print(f"Failed to get webhook events via REST: {e}")
            return None

    def save_local_ip_registration(self, public_ip: str, local_ip: str = None, 
                                 port: int = 8080, hostname: str = None, ngrok_url: str = None) -> bool:
        """Save local IP registration to cloud database via REST API"""
        try:
            # Start with basic payload (without ngrok_url)
            payload = {
                'public_ip': public_ip,
                'local_ip': local_ip,
                'port': port,
                'hostname': hostname
            }
            
            # Only add ngrok_url if it's provided and not None
            if ngrok_url:
                payload['ngrok_url'] = ngrok_url
            
            # First try to update existing record
            update_url = f"{self.base_url}/local_ip_registrations"
            update_params = {
                'public_ip': f"eq.{public_ip}",
                'port': f"eq.{port}"
            }
            
            # Try to update first
            update_headers = dict(self.headers)
            update_headers['Prefer'] = 'return=representation'
            
            update_response = requests.patch(
                update_url, 
                headers=update_headers, 
                params=update_params,
                data=json.dumps(payload), 
                timeout=15
            )
            
            if update_response.ok and len(update_response.json()) > 0:
                info(f"✅ Local IP registration updated via REST: {public_ip}:{port}" + (f" (ngrok: {ngrok_url})" if ngrok_url else ""), file_only=True)
                return True
            
            # If no existing record, insert new one
            insert_response = requests.post(
                update_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=15
            )
            
            if insert_response.ok:
                info(f"✅ Local IP registration created via REST: {public_ip}:{port}" + (f" (ngrok: {ngrok_url})" if ngrok_url else ""), file_only=True)
                return True
            else:
                # Check if the error is due to missing ngrok_url column
                error_text = insert_response.text
                if "ngrok_url" in error_text and "PGRST204" in error_text:
                    print(f"⚠️ ngrok_url column not found, retrying without ngrok_url...")
                    # Retry without ngrok_url
                    basic_payload = {
                        'public_ip': public_ip,
                        'local_ip': local_ip,
                        'port': port,
                        'hostname': hostname
                    }
                    
                    retry_response = requests.post(
                        update_url,
                        headers=self.headers,
                        data=json.dumps(basic_payload),
                        timeout=15
                    )
                    
                    if retry_response.ok:
                        info(f"✅ Local IP registration created via REST (without ngrok_url): {public_ip}:{port}", file_only=True)
                        return True
                    else:
                        print(f"❌ Failed to save IP registration (retry): {retry_response.status_code} - {retry_response.text}")
                        return False
                else:
                    print(f"❌ Failed to save IP registration: {insert_response.status_code} - {insert_response.text}")
                    return False
            
        except Exception as e:
            print(f"Failed to save local IP registration via REST: {e}")
            return False
    
    def get_latest_local_ip_registration(self) -> Optional[dict]:
        """Get the latest local IP registration from cloud database via REST API"""
        try:
            params = {
                'select': 'public_ip,local_ip,port,hostname,registered_at,last_seen',
                'order': 'registered_at.desc',
                'limit': '1'
            }
            
            result = self._get('local_ip_registrations', params)
            if result and len(result) > 0:
                return result[0]
            return None
            
        except Exception as e:
            print(f"Failed to get latest local IP registration via REST: {e}")
            return None
    
    def save_onchain_metrics(self, metrics: dict) -> bool:
        """Save on-chain network metrics to cloud database via REST"""
        try:
            return self._post('onchain_network_metrics', metrics)
        except Exception as e:
            print(f"Failed to save on-chain metrics via REST: {e}")
            return False
    
    def save_onchain_analysis(self, analysis: dict) -> bool:
        """Save on-chain health analysis to cloud database via REST"""
        try:
            return self._post('onchain_health_scores', analysis)
        except Exception as e:
            print(f"Failed to save on-chain analysis via REST: {e}")
            return False
    
    def save_oi_data(self, oi_records: List[dict]) -> bool:
        """Save OI data to cloud database via REST"""
        try:
            if not oi_records:
                return False

            success_count = 0
            for record in oi_records:
                # Convert datetime objects to strings for JSON serialization
                serializable_record = {}
                for key, value in record.items():
                    if isinstance(value, datetime):
                        serializable_record[key] = value.isoformat()
                    else:
                        serializable_record[key] = value

                if self._post('oi_data', serializable_record):
                    success_count += 1

            return success_count > 0
        except Exception as e:
            print(f"Failed to save OI data via REST: {e}")
            return False
    
    def save_oi_analytics(self, analytics_records: List[dict]) -> bool:
        """Save OI analytics to cloud database via REST"""
        try:
            if not analytics_records:
                return False

            success_count = 0
            for record in analytics_records:
                if self._post('oi_analytics', record):
                    success_count += 1

            return success_count > 0
        except Exception as e:
            print(f"Failed to save OI analytics via REST: {e}")
            return False

    def save_funding_data(self, funding_records: List[dict]) -> bool:
        """Save funding rate data to cloud database via REST"""
        try:
            if not funding_records:
                return False

            success_count = 0
            for record in funding_records:
                # Convert datetime objects to ISO strings for JSON serialization
                event_time = record.get('event_time')
                if hasattr(event_time, 'isoformat'):
                    event_time_str = event_time.isoformat()
                else:
                    event_time_str = str(event_time)

                payload = {
                    'timestamp': event_time_str,  # Use event_time as timestamp
                    'symbol': record.get('symbol'),
                    'funding_rate': record.get('funding_rate'),
                    'annual_rate': record.get('annual_rate'),
                    'mark_price': record.get('mark_price'),
                    'open_interest': record.get('open_interest'),
                    'event_time': event_time_str
                }
                if self._post('funding_rates', payload):
                    success_count += 1

            return success_count > 0
        except Exception as e:
            print(f"Failed to save funding data via REST: {e}")
            return False

    def save_funding_analytics(self, analytics_records: List[dict]) -> bool:
        """Save funding analytics to cloud database via REST"""
        try:
            if not analytics_records:
                return False

            success_count = 0
            for record in analytics_records:
                # Convert datetime objects to ISO strings for JSON serialization
                timestamp = record.get('timestamp')
                if hasattr(timestamp, 'isoformat'):
                    timestamp_str = timestamp.isoformat()
                else:
                    timestamp_str = str(timestamp)

                payload = {
                    'timestamp': timestamp_str,
                    'symbol': record.get('symbol'),
                    'rate_change_pct': record.get('rate_change_pct'),
                    'trend': record.get('trend'),
                    'alert_level': record.get('alert_level'),
                    'timeframe': record.get('timeframe'),
                    'metadata': record.get('metadata', {})
                }
                if self._post('funding_analytics', payload):
                    success_count += 1

            return success_count > 0
        except Exception as e:
            print(f"Failed to save funding analytics via REST: {e}")
            return False


