"""
IUL Appointment Setter System - Main Entry Point

Single launcher that starts all required services:
- Redis check
- Database initialization
- Celery worker (background tasks)
- Celery beat (scheduler)
- FastAPI server (webhooks)
"""
import sys
import time
import subprocess
import signal
import os
from pathlib import Path
from loguru import logger
from typing import List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import app_config, redis_config, db_config
from src.storage.database import engine, Base
from src.storage import models  # Import to register models


class AppointmentSetterSystem:
    """Main system orchestrator"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.running = False
        
        # Configure logging
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level=app_config.log_level
        )
        logger.add(
            "logs/system_{time}.log",
            rotation="1 day",
            retention="7 days",
            level=app_config.log_level
        )
    
    def start_redis(self) -> Optional[subprocess.Popen]:
        """Start Redis server automatically"""
        try:
            # Try common Redis locations
            redis_paths = [
                Path(r"C:\Users\Top Cash Pawn\Okorie-AI\redis\redis-server.exe"),
                Path(r"C:\Program Files\Redis\redis-server.exe"),
                Path(r"redis-server.exe"),  # In PATH
            ]
            
            redis_exe = None
            for path in redis_paths:
                if path.exists():
                    redis_exe = path
                    break
            
            if not redis_exe:
                logger.warning("Redis executable not found. Please start Redis manually or install it.")
                return None
            
            logger.info(f"Starting Redis from: {redis_exe}")
            
            # Start Redis in background
            process = subprocess.Popen(
                [str(redis_exe)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
            
            # Wait for Redis to be ready
            import redis
            for attempt in range(10):
                time.sleep(0.5)
                try:
                    r = redis.from_url(redis_config.url, socket_timeout=1)
                    r.ping()
                    logger.info("[OK] Redis server started successfully")
                    return process
                except:
                    continue
            
            logger.error("[ERROR] Redis started but connection failed")
            process.terminate()
            return None
        
        except Exception as e:
            logger.error(f"[ERROR] Error starting Redis: {e}")
            return None
    
    def check_redis(self) -> bool:
        """Check if Redis is running, and auto-start if not"""
        import redis
        
        try:
            logger.info("Checking Redis connection...")
            r = redis.from_url(redis_config.url, socket_timeout=5)
            r.ping()
            logger.info("[OK] Redis is already running")
            return True
        except Exception as e:
            logger.warning(f"Redis not running: {e}")
            logger.info("Attempting to auto-start Redis...")
            
            # Try to start Redis
            redis_process = self.start_redis()
            if redis_process:
                self.processes.append(redis_process)
                return True
            else:
                logger.error("[ERROR] Could not auto-start Redis")
                logger.info("Please start Redis manually:")
                logger.info("  Windows: cd C:\\Users\\Top Cash Pawn\\Okorie-AI\\redis && .\\redis-server.exe")
                logger.info("  Linux/Mac: redis-server &")
                return False
    
    def init_database(self) -> bool:
        """Initialize database tables"""
        try:
            logger.info("Initializing database...")
            Base.metadata.create_all(bind=engine)
            logger.info("[OK] Database tables created/verified")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Database initialization failed: {e}")
            return False
    
    def check_env_vars(self) -> bool:
        """Check if required environment variables are set"""
        logger.info("Checking environment configuration...")
        
        warnings = []
        
        # Required for Apify
        if not os.getenv("APIFY_API_TOKEN"):
            warnings.append("APIFY_API_TOKEN not set - lead sourcing will fail")
        
        # Required for SendGrid
        if not os.getenv("SENDGRID_API_KEY"):
            warnings.append("SENDGRID_API_KEY not set - email sending will fail")
        
        # Required for Twilio (optional)
        if not os.getenv("TWILIO_ACCOUNT_SID"):
            logger.debug("TWILIO_ACCOUNT_SID not set - SMS features disabled")
        
        # Required for Calendly
        if not os.getenv("CALENDLY_API_KEY"):
            warnings.append("CALENDLY_API_KEY not set - scheduling integration will fail")
        
        if warnings:
            logger.warning("[WARNING] Configuration warnings:")
            for w in warnings:
                logger.warning(f"  - {w}")
            
            response = input("\nContinue anyway? (y/n): ")
            if response.lower() != 'y':
                return False
        
        logger.info("[OK] Environment configuration OK")
        return True
    
    def start_celery_worker(self) -> Optional[subprocess.Popen]:
        """Start Celery worker process"""
        try:
            logger.info("Starting Celery worker...")
            
            cmd = [
                sys.executable, "-m", "celery",
                "-A", "src.workflow.celery_app",
                "worker",
                "--loglevel=info",
                "--pool=solo" if sys.platform == "win32" else "--pool=prefork"
            ]
            
            # Create logs directory if it doesn't exist
            Path("logs").mkdir(exist_ok=True)
            
            # Open log file for worker output
            worker_log = open("logs/celery_worker.log", "a")
            
            process = subprocess.Popen(
                cmd,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            time.sleep(2)  # Give it time to start
            
            if process.poll() is None:
                logger.info("[OK] Celery worker started (logs: logs/celery_worker.log)")
                return process
            else:
                logger.error("[ERROR] Celery worker failed to start")
                worker_log.close()
                return None
        
        except Exception as e:
            logger.error(f"[ERROR] Error starting Celery worker: {e}")
            return None
    
    def start_celery_beat(self) -> Optional[subprocess.Popen]:
        """Start Celery beat scheduler"""
        try:
            logger.info("Starting Celery beat scheduler...")
            
            cmd = [
                sys.executable, "-m", "celery",
                "-A", "src.workflow.celery_app",
                "beat",
                "--loglevel=info"
            ]
            
            # Create logs directory if it doesn't exist
            Path("logs").mkdir(exist_ok=True)
            
            # Open log file for beat output
            beat_log = open("logs/celery_beat.log", "a")
            
            process = subprocess.Popen(
                cmd,
                stdout=beat_log,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            time.sleep(2)
            
            if process.poll() is None:
                logger.info("[OK] Celery beat scheduler started (logs: logs/celery_beat.log)")
                return process
            else:
                logger.error("[ERROR] Celery beat failed to start")
                beat_log.close()
                return None
        
        except Exception as e:
            logger.error(f"[ERROR] Error starting Celery beat: {e}")
            return None
    
    def start_fastapi(self) -> Optional[subprocess.Popen]:
        """Start FastAPI server"""
        try:
            logger.info("Starting FastAPI server...")
            
            cmd = [
                sys.executable, "-m", "uvicorn",
                "src.api.main:app",
                "--host", "0.0.0.0",
                "--port", "8000",
                "--reload" if app_config.debug else "--no-reload"
            ]
            
            # Create logs directory if it doesn't exist
            Path("logs").mkdir(exist_ok=True)
            
            # Open log file for FastAPI output
            api_log = open("logs/fastapi.log", "a")
            
            process = subprocess.Popen(
                cmd,
                stdout=api_log,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            time.sleep(3)
            
            if process.poll() is None:
                logger.info("[OK] FastAPI server started on http://localhost:8000 (logs: logs/fastapi.log)")
                return process
            else:
                logger.error("[ERROR] FastAPI server failed to start")
                api_log.close()
                return None
        
        except Exception as e:
            logger.error(f"[ERROR] Error starting FastAPI: {e}")
            return None
    
    def monitor_processes(self):
        """Monitor running processes and restart if needed"""
        while self.running:
            try:
                for i, process in enumerate(self.processes):
                    if process.poll() is not None:
                        logger.error(f"Process {i} exited unexpectedly with code {process.returncode}")
                        # In production, you might want to restart here
                
                time.sleep(5)
            
            except KeyboardInterrupt:
                break
    
    def stop_all(self):
        """Stop all running processes"""
        logger.info("Shutting down all services...")
        self.running = False
        
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        
        logger.info("[OK] All services stopped")
    
    def run(self):
        """Main entry point - start all services"""
        logger.info("=" * 60)
        logger.info("IUL Appointment Setter System")
        logger.info("=" * 60)
        
        # Pre-flight checks
        if not self.check_redis():
            sys.exit(1)
        
        if not self.init_database():
            sys.exit(1)
        
        if not self.check_env_vars():
            sys.exit(1)
        
        # Start services
        logger.info("\n" + "=" * 60)
        logger.info("Starting Services")
        logger.info("=" * 60)
        
        celery_worker = self.start_celery_worker()
        if not celery_worker:
            logger.error("Failed to start Celery worker. Exiting.")
            sys.exit(1)
        self.processes.append(celery_worker)
        
        celery_beat = self.start_celery_beat()
        if not celery_beat:
            logger.error("Failed to start Celery beat. Exiting.")
            self.stop_all()
            sys.exit(1)
        self.processes.append(celery_beat)
        
        fastapi = self.start_fastapi()
        if not fastapi:
            logger.error("Failed to start FastAPI. Exiting.")
            self.stop_all()
            sys.exit(1)
        self.processes.append(fastapi)
        
        # System is now running
        logger.info("\n" + "=" * 60)
        logger.info("[OK] System is RUNNING")
        logger.info("=" * 60)
        logger.info("API: http://localhost:8000")
        logger.info("Docs: http://localhost:8000/docs")
        logger.info("\nPress Ctrl+C to stop")
        logger.info("=" * 60 + "\n")
        
        self.running = True
        
        # Register signal handlers
        signal.signal(signal.SIGINT, lambda s, f: self.stop_all())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop_all())
        
        # Monitor processes
        try:
            self.monitor_processes()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all()


def main():
    """Entry point"""
    system = AppointmentSetterSystem()
    system.run()


if __name__ == "__main__":
    main()
