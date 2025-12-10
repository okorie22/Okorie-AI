"""
🔄 Wallet Manager Module
Handles automated wallet updates for the trading system
Built with love by Anarcho Capital 🚀
"""

import os
import json
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Local imports
from src.scripts.shared_services.logger import info, warning, error, critical

logger = logging.getLogger(__name__)

class WalletManager:
    """
    Manages automated wallet updates for the trading system
    """
    
    def __init__(self):
        """Initialize the wallet manager"""
        # Handle different execution contexts
        if Path("src/config.py").exists():
            self.config_file_path = Path("src/config.py")
            self.backup_dir = Path("src/data/backups")
        elif Path("../config.py").exists():
            self.config_file_path = Path("../config.py")
            self.backup_dir = Path("../data/backups")
        else:
            # Fallback to absolute path
            self.config_file_path = Path(__file__).parent.parent / "config.py"
            self.backup_dir = Path(__file__).parent.parent / "data" / "backups"
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def update_wallets_after_emergency_stop(self, num_wallets: int = 3) -> bool:
        """
        Update WALLETS_TO_TRACK in config.py with best performing wallets after emergency stop
        
        Args:
            num_wallets: Number of wallets to select (default: 3)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            info("🔄 Starting automated wallet update after emergency stop...")
            
            # Get best performing wallets from whale data
            best_wallets = self._get_best_performing_wallets(num_wallets)
            
            if not best_wallets:
                error("❌ No suitable wallets found for update")
                return False
            
            # Create backup of current config
            backup_created = self._create_config_backup()
            if not backup_created:
                warning("⚠️ Failed to create config backup, proceeding anyway...")
            
            # Update the config file
            success = self._update_config_file(best_wallets)
            
            if success:
                info(f"✅ Successfully updated WALLETS_TO_TRACK with {len(best_wallets)} new wallets")
                self._log_wallet_update(best_wallets)
                return True
            else:
                error("❌ Failed to update config file")
                return False
                
        except Exception as e:
            error(f"❌ Error in wallet update: {str(e)}")
            return False
    
    def _get_best_performing_wallets(self, num_wallets: int) -> List[Dict[str, str]]:
        """
        Get the best performing wallets from whale data
        
        Args:
            num_wallets: Number of wallets to select
            
        Returns:
            List of wallet dictionaries with address and metadata
        """
        try:
            # Read whale data directly from JSON file (more reliable than async calls)
            whale_data = self._read_whale_data_from_file()
            
            if not whale_data:
                warning("⚠️ No whale data available, using fallback wallets")
                return self._get_fallback_wallets(num_wallets)
            
            # Filter and rank wallets based on performance criteria
            filtered_wallets = self._filter_wallets_by_criteria(whale_data)
            
            # Select the best wallets
            selected_wallets = filtered_wallets[:num_wallets]
            
            # Convert to simple format for config
            wallet_list = []
            for wallet in selected_wallets:
                wallet_info = {
                    'address': wallet['address'],
                    'twitter_handle': wallet.get('twitter_handle', 'Unknown'),
                    'score': wallet.get('score', 0),
                    'pnl_30d': wallet.get('pnl_30d', 0),
                    'winrate_7d': wallet.get('winrate_7d', 0)
                }
                wallet_list.append(wallet_info)
            
            info(f"📊 Selected {len(wallet_list)} best performing wallets")
            for wallet in wallet_list:
                info(f"  • {wallet['address'][:8]}... ({wallet['twitter_handle']}) - Score: {wallet['score']:.3f}")
            
            return wallet_list
            
        except Exception as e:
            error(f"❌ Error getting best performing wallets: {str(e)}")
            return self._get_fallback_wallets(num_wallets)
    
    def _filter_wallets_by_criteria(self, wallets: List[Dict]) -> List[Dict]:
        """
        Filter wallets based on performance criteria
        
        Args:
            wallets: List of wallet dictionaries
            
        Returns:
            Filtered and sorted list of wallets
        """
        try:
            filtered = []
            
            for wallet in wallets:
                # Basic validation
                if not wallet.get('address') or len(wallet['address']) != 44:
                    continue
                
                # Skip inactive wallets
                if not wallet.get('is_active', True):
                    continue
                
                # Performance criteria
                score = wallet.get('score', 0)
                pnl_30d = wallet.get('pnl_30d', 0)
                winrate_7d = wallet.get('winrate_7d', 0)
                txs_30d = wallet.get('txs_30d', 0)
                rank = wallet.get('rank', 999)
                
                # Filter criteria (more lenient for emergency situations)
                if (score >= 0.25 and      # Minimum score (lowered for emergency)
                    pnl_30d > -0.1 and     # Not too much loss (allow small losses)
                    winrate_7d >= 0.3 and  # At least 30% win rate (lowered)
                    txs_30d >= 50 and      # Minimum transaction activity (lowered)
                    rank <= 50):           # Top 50 ranked wallets
                    
                    filtered.append(wallet)
            
            # Sort by score (highest first)
            filtered.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            info(f"📊 Filtered {len(filtered)} wallets from {len(wallets)} total")
            return filtered
            
        except Exception as e:
            error(f"❌ Error filtering wallets: {str(e)}")
            return wallets[:3]  # Return first 3 if filtering fails
    
    def _get_fallback_wallets(self, num_wallets: int) -> List[Dict[str, str]]:
        """
        Get fallback wallets if whale data is unavailable
        
        Args:
            num_wallets: Number of wallets to return
            
        Returns:
            List of fallback wallet dictionaries
        """
        # These are some known high-performing wallets as fallbacks
        fallback_wallets = [
            {
                'address': 'DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt',
                'twitter_handle': 'KayTheDoc',
                'score': 0.36,
                'pnl_30d': 0.33,
                'winrate_7d': 0.67
            },
            {
                'address': '86AEJExyjeNNgcp7GrAvCXTDicf5aGWgoERbXFiG1EdD',
                'twitter_handle': 'publixplays',
                'score': 0.35,
                'pnl_30d': 0.06,
                'winrate_7d': 0.44
            },
            {
                'address': '4DdrfiDHpmx55i4SPssxVzS9ZaKLb8qr45NKY9Er9nNh',
                'twitter_handle': 'TheMisterFrog',
                'score': 0.35,
                'pnl_30d': 0.07,
                'winrate_7d': 0.81
            }
        ]
        
        warning("⚠️ Using fallback wallets due to unavailable whale data")
        return fallback_wallets[:num_wallets]
    
    def _create_config_backup(self) -> bool:
        """
        Create a backup of the current config file
        
        Returns:
            bool: True if backup created successfully
        """
        try:
            if not self.config_file_path.exists():
                error("❌ Config file not found")
                return False
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_backup_{timestamp}.py"
            backup_path = self.backup_dir / backup_filename
            
            # Copy config file
            with open(self.config_file_path, 'r', encoding='utf-8') as src:
                content = src.read()
            
            with open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(content)
            
            info(f"✅ Config backup created: {backup_filename}")
            return True
            
        except Exception as e:
            error(f"❌ Error creating config backup: {str(e)}")
            return False
    
    def _update_config_file(self, wallets: List[Dict[str, str]]) -> bool:
        """
        Update the WALLETS_TO_TRACK list in config.py
        
        Args:
            wallets: List of wallet dictionaries to add
            
        Returns:
            bool: True if update successful
        """
        try:
            if not self.config_file_path.exists():
                error("❌ Config file not found")
                return False
            
            # Read current config
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract wallet addresses
            wallet_addresses = [wallet['address'] for wallet in wallets]
            
            # Create new WALLETS_TO_TRACK list
            new_wallet_list = '[\n'
            for i, address in enumerate(wallet_addresses):
                wallet_info = wallets[i]
                comment = f"  # {wallet_info['twitter_handle']} (Score: {wallet_info['score']:.3f})"
                new_wallet_list += f'    "{address}",{comment}\n'
            new_wallet_list += ']'
            
            # Replace the WALLETS_TO_TRACK section
            pattern = r'WALLETS_TO_TRACK\s*=\s*\[[^\]]*\]'
            replacement = f'WALLETS_TO_TRACK = {new_wallet_list}'
            
            # Check if pattern exists
            if not re.search(pattern, content, re.MULTILINE | re.DOTALL):
                error("❌ WALLETS_TO_TRACK section not found in config")
                return False
            
            # Replace the section
            updated_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
            
            # Write updated config
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            info("✅ Config file updated successfully")
            return True
            
        except Exception as e:
            error(f"❌ Error updating config file: {str(e)}")
            return False
    
    def _log_wallet_update(self, wallets: List[Dict[str, str]]):
        """
        Log the wallet update for audit purposes
        
        Args:
            wallets: List of updated wallets
        """
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'event': 'emergency_stop_wallet_update',
                'wallets_updated': len(wallets),
                'wallets': wallets,
                'reason': 'Emergency stop triggered - updating to best performing wallets'
            }
            
            # Save to log file
            log_file = self.backup_dir / "wallet_updates.json"
            
            # Load existing logs or create new
            if log_file.exists():
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            logs.append(log_entry)
            
            # Keep only last 50 entries
            if len(logs) > 50:
                logs = logs[-50:]
            
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
            
            info("📝 Wallet update logged for audit")
            
        except Exception as e:
            warning(f"⚠️ Error logging wallet update: {str(e)}")
    
    def get_current_wallets(self) -> List[str]:
        """
        Get current wallets from config file
        
        Returns:
            List of wallet addresses
        """
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract wallet addresses using regex
            pattern = r'WALLETS_TO_TRACK\s*=\s*\[([^\]]*)\]'
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            
            if not match:
                return []
            
            wallet_section = match.group(1)
            # Extract addresses from the section
            address_pattern = r'"([A-Za-z0-9]{44})"'
            addresses = re.findall(address_pattern, wallet_section)
            
            return addresses
            
        except Exception as e:
            error(f"❌ Error reading current wallets: {str(e)}")
            return []
    
    def _read_whale_data_from_file(self) -> List[Dict]:
        """
        Read whale data directly from the ranked_whales.json file
        
        Returns:
            List of wallet dictionaries
        """
        try:
            # Handle different execution contexts
            whale_file = None
            possible_paths = [
                Path("src/data/whale_dump/ranked_whales.json"),
                Path("../data/whale_dump/ranked_whales.json"),
                Path(__file__).parent.parent / "data" / "whale_dump" / "ranked_whales.json"
            ]
            
            for path in possible_paths:
                if path.exists():
                    whale_file = path
                    break
            
            if not whale_file:
                warning("⚠️ Whale data file not found")
                return []
            
            # Check if file is recent (within last 24 hours)
            file_age = datetime.now() - datetime.fromtimestamp(whale_file.stat().st_mtime)
            if file_age > timedelta(hours=24):
                warning("⚠️ Whale data file is older than 24 hours")
            
            with open(whale_file, 'r') as f:
                whale_data = json.load(f)
            
            # Convert to list format
            wallets = []
            for address, data in whale_data.items():
                wallet_info = {
                    'address': address,
                    'twitter_handle': data.get('twitter_handle', 'Unknown'),
                    'score': data.get('score', 0),
                    'pnl_30d': data.get('pnl_30d', 0),
                    'pnl_7d': data.get('pnl_7d', 0),
                    'winrate_7d': data.get('winrate_7d', 0),
                    'txs_30d': data.get('txs_30d', 0),
                    'token_active': data.get('token_active', 0),
                    'is_blue_verified': data.get('is_blue_verified', False),
                    'is_active': data.get('is_active', True),
                    'rank': data.get('rank', 999)
                }
                wallets.append(wallet_info)
            
            info(f"📊 Loaded {len(wallets)} wallets from whale data file")
            return wallets
            
        except Exception as e:
            error(f"❌ Error reading whale data file: {str(e)}")
            return []
    
    def validate_wallet_address(self, address: str) -> bool:
        """
        Validate a Solana wallet address
        
        Args:
            address: Wallet address to validate
            
        Returns:
            bool: True if valid
        """
        # Basic Solana address validation
        if not isinstance(address, str):
            return False
        
        if len(address) != 44:
            return False
        
        # Check if it's alphanumeric
        if not address.isalnum():
            return False
        
        return True

# Global instance
wallet_manager = WalletManager()

def update_wallets_after_emergency_stop(num_wallets: int = 3) -> bool:
    """
    Convenience function to update wallets after emergency stop
    
    Args:
        num_wallets: Number of wallets to select
        
    Returns:
        bool: True if successful
    """
    return wallet_manager.update_wallets_after_emergency_stop(num_wallets) 
