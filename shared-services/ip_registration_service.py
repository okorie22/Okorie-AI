"""
IP Registration Service for Automatic Webhook Forwarding
Detects public IP and registers with Supabase for Render webhook forwarding
"""

import requests
import socket
import logging
import time
import threading
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

# Import logger functions
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    def debug(msg, file_only=False): print(f"DEBUG: {msg}")
    def info(msg): print(f"INFO: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")

logger = logging.getLogger(__name__)

class IPRegistrationService:
    """Service for detecting and registering local machine IP with cloud database"""
    
    def __init__(self):
        self.public_ip = None
        self.local_ip = None
        self.registration_time = None
        self.cache_duration = 300  # 5 minutes cache
        self.registration_interval = 300  # 5 minutes between registrations
        self.background_thread = None
        self.running = False
        
    def get_public_ip(self) -> Optional[str]:
        """Detect public IP using multiple services for reliability"""
        services = [
            "https://api.ipify.org",
            "https://ipv4.icanhazip.com", 
            "https://checkip.amazonaws.com",
            "https://api.ip.sb/ip",
            "https://ifconfig.me/ip"
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    # Validate IP format
                    if self._is_valid_ip(ip):
                        info(f"🌍 Public IP detected: {ip} via {service}", file_only=True)
                        return ip
            except Exception as e:
                debug(f"IP detection failed for {service}: {e}")
                continue
                
        warning("⚠️ Could not detect public IP from any service")
        return None
    
    def get_local_ip(self) -> Optional[str]:
        """Detect local IP address using existing config function"""
        try:
            from src.config import get_local_ip_address
            local_ip = get_local_ip_address()
            info(f"🏠 Local IP detected: {local_ip}", file_only=True)
            return local_ip
        except Exception as e:
            warning(f"⚠️ Could not detect local IP: {e}")
            return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            return all(0 <= int(part) <= 255 for part in parts)
        except:
            return False
    
    def register_local_ip(self, port: int = 8080, hostname: str = None, ngrok_url: str = None) -> bool:
        """Register local IP with cloud database"""
        try:
            # Detect IPs
            public_ip = self.get_public_ip()
            local_ip = self.get_local_ip()
            
            if not public_ip and not local_ip:
                error("❌ No IP addresses detected for registration")
                return False
            
            # Use public IP if available, otherwise local IP
            primary_ip = public_ip or local_ip
            
            # Get hostname if not provided
            if not hostname:
                try:
                    hostname = socket.gethostname()
                except:
                    hostname = "unknown"
            
            # Import cloud database manager
            from src.scripts.database.cloud_database import get_cloud_database_manager
            
            db = get_cloud_database_manager()
            if not db:
                error("❌ Cloud database not available for IP registration")
                return False
            
            # Save registration
            success = db.save_local_ip_registration(
                public_ip=primary_ip,
                local_ip=local_ip,
                port=port,
                hostname=hostname,
                ngrok_url=ngrok_url
            )
            
            if success:
                self.public_ip = public_ip
                self.local_ip = local_ip
                self.registration_time = time.time()
                info(f"✅ IP registration successful: {primary_ip}:{port}" + (f" (ngrok: {ngrok_url})" if ngrok_url else ""), file_only=True)
                return True
            else:
                error("❌ Failed to save IP registration to database")
                return False
                
        except Exception as e:
            error(f"❌ IP registration failed: {e}")
            return False
    
    def get_registered_ip(self) -> Optional[Dict]:
        """Get the latest registered IP from cloud database"""
        try:
            from src.scripts.database.cloud_database import get_cloud_database_manager
            
            db = get_cloud_database_manager()
            if not db:
                warning("⚠️ Cloud database not available for IP retrieval")
                return None
            
            registration = db.get_latest_local_ip_registration()
            if registration:
                debug(f"📡 Retrieved registered IP: {registration.get('public_ip')}:{registration.get('port')}")
            
            return registration
            
        except Exception as e:
            warning(f"⚠️ Failed to get registered IP: {e}")
            return None
    
    def get_webhook_url(self, port: int = 8080) -> Optional[str]:
        """Get the best webhook URL for forwarding"""
        # Check cache first
        if (self.registration_time and 
            (time.time() - self.registration_time) < self.cache_duration and 
            self.public_ip):
            url = f"http://{self.public_ip}:{port}/webhook"
            debug(f"🎯 Using cached webhook URL: {url}")
            return url
        
        # Try to get from database
        registration = self.get_registered_ip()
        if registration:
            ip = registration.get('public_ip') or registration.get('local_ip')
            if ip:
                url = f"http://{ip}:{port}/webhook"
                info(f"🎯 Using registered webhook URL: {url}")
                return url
        
        # Fallback to local detection
        public_ip = self.get_public_ip()
        if public_ip:
            url = f"http://{public_ip}:{port}/webhook"
            warning(f"⚠️ Using detected webhook URL: {url} (not registered)")
            return url
        
        error("❌ Could not determine webhook URL")
        return None
    
    def start_background_registration(self, port: int = 8080, hostname: str = None):
        """Start background thread for periodic IP registration"""
        if self.running:
            warning("⚠️ Background registration already running")
            return
        
        self.running = True
        self.background_thread = threading.Thread(
            target=self._background_registration_loop,
            args=(port, hostname),
            daemon=True
        )
        self.background_thread.start()
        info("🔄 Started background IP registration service", file_only=True)
    
    def stop_background_registration(self):
        """Stop background registration thread"""
        self.running = False
        if self.background_thread:
            self.background_thread.join(timeout=5)
        info("🛑 Stopped background IP registration service", file_only=True)
    
    def _background_registration_loop(self, port: int, hostname: str):
        """Background loop for periodic IP registration"""
        consecutive_failures = 0
        max_failures = 3
        
        while self.running:
            try:
                success = self.register_local_ip(port, hostname)
                if success:
                    consecutive_failures = 0
                    debug("🔄 Background IP registration successful", file_only=True)
                else:
                    consecutive_failures += 1
                    warning(f"⚠️ Background IP registration failed ({consecutive_failures}/{max_failures})", file_only=True)
                
                # If too many consecutive failures, increase delay
                if consecutive_failures >= max_failures:
                    warning(f"⚠️ Too many registration failures, increasing delay to 10 minutes")
                    time.sleep(600)  # 10 minutes
                    consecutive_failures = 0  # Reset counter
                else:
                    time.sleep(self.registration_interval)
                    
            except Exception as e:
                consecutive_failures += 1
                error(f"❌ Background registration error: {e}")
                
                # Exponential backoff for errors
                delay = min(60 * (2 ** consecutive_failures), 600)  # Max 10 minutes
                warning(f"⚠️ Waiting {delay}s before retry (failure #{consecutive_failures})")
                time.sleep(delay)

# Global instance
ip_registration_service = IPRegistrationService()

def get_ip_registration_service() -> IPRegistrationService:
    """Get the global IP registration service instance"""
    return ip_registration_service
