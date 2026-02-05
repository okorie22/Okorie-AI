"""
IUL Appointment Setter System - Main Entry Point

Single launcher that starts all required services:
- Redis check
- Database initialization
- Celery worker (background tasks)
- Celery beat (scheduler)
- FastAPI server (webhooks)
- Optional: ngrok tunnel (ENABLE_NGROK=1) for HTTPS webhook URL (e.g. SendGrid)
"""
import sys
import time
import subprocess
import signal
import os
import json
import urllib.request
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
            level=app_config.log_level.upper()
        )
        logger.add(
            "logs/system_{time}.log",
            rotation="1 day",
            retention="7 days",
            level=app_config.log_level.upper()
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
    
    def _is_external_redis(self) -> bool:
        """True if REDIS_URL points to an external service (Render Redis, Upstash, etc.)."""
        url = (redis_config.url or "").strip().lower()
        if not url:
            return False
        return "localhost" not in url and "127.0.0.1" not in url

    def check_redis(self) -> bool:
        """Check if Redis is running. On Render/external Redis, only check connection; locally, auto-start if needed."""
        import redis

        try:
            logger.info("Checking Redis connection...")
            r = redis.from_url(redis_config.url, socket_timeout=5)
            r.ping()
            logger.info("[OK] Redis is reachable")
            return True
        except Exception as e:
            if self._is_external_redis():
                logger.error(f"[ERROR] Cannot connect to external Redis: {e}")
                logger.info("Check REDIS_URL (e.g. Render Redis add-on or Upstash) and network.")
                return False
            logger.warning(f"Redis not running: {e}")
            logger.info("Attempting to auto-start Redis...")
            redis_process = self.start_redis()
            if redis_process:
                self.processes.append(redis_process)
                return True
            logger.error("[ERROR] Could not auto-start Redis")
            logger.info("Please start Redis manually or set REDIS_URL to an external Redis.")
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
            # On Render (RUN_MODE set) or non-interactive, do not block on input
            if os.getenv("RUN_MODE"):
                logger.warning("RUN_MODE is set; continuing despite warnings.")
            else:
                try:
                    response = input("\nContinue anyway? (y/n): ")
                    if response.lower() != 'y':
                        return False
                except EOFError:
                    logger.warning("Non-interactive; continuing despite warnings.")
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
            Path("logs").mkdir(exist_ok=True)
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
            logger.error("[ERROR] Celery beat failed to start")
            beat_log.close()
            return None
        except Exception as e:
            logger.error(f"[ERROR] Error starting Celery beat: {e}")
            return None

    def start_celery_worker_with_beat(self) -> Optional[subprocess.Popen]:
        """Start Celery worker and beat in one process (for Render background worker)."""
        try:
            logger.info("Starting Celery worker + beat (single process)...")
            cmd = [
                sys.executable, "-m", "celery",
                "-A", "src.workflow.celery_app",
                "worker",
                "--beat",
                "--loglevel=info",
                "--pool=solo" if sys.platform == "win32" else "--pool=prefork"
            ]
            Path("logs").mkdir(exist_ok=True)
            worker_log = open("logs/celery_worker.log", "a")
            process = subprocess.Popen(
                cmd,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
                text=True
            )
            time.sleep(3)
            if process.poll() is None:
                logger.info("[OK] Celery worker+beat started (logs: logs/celery_worker.log)")
                return process
            logger.error("[ERROR] Celery worker+beat failed to start")
            worker_log.close()
            return None
        except Exception as e:
            logger.error(f"[ERROR] Error starting Celery worker+beat: {e}")
            return None
    
    def start_fastapi(self) -> Optional[subprocess.Popen]:
        """Start FastAPI server"""
        try:
            port = os.getenv("PORT", "8000")
            logger.info("Starting FastAPI server...")
            
            cmd = [
                sys.executable, "-m", "uvicorn",
                "src.api.main:app",
                "--host", "0.0.0.0",
                "--port", port,
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
                logger.info(f"[OK] FastAPI server started on port {port} (logs: logs/fastapi.log)")
                return process
            else:
                logger.error("[ERROR] FastAPI server failed to start")
                api_log.close()
                return None
        
        except Exception as e:
            logger.error(f"[ERROR] Error starting FastAPI: {e}")
            return None

    def _should_run_ngrok(self) -> bool:
        """True if ENABLE_NGROK is set (1, true, yes)."""
        v = (os.getenv("ENABLE_NGROK") or "").strip().lower()
        return v in ("1", "true", "yes")

    def _get_ngrok_public_url(self, port: str = "8000", max_attempts: int = 15) -> Optional[str]:
        """Poll ngrok local API for the HTTPS public URL. Returns None if not found."""
        for _ in range(max_attempts):
            try:
                req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode())
                tunnels = data.get("tunnels") or []
                for t in tunnels:
                    addr = (t.get("config", {}).get("addr") or "")
                    if f":{port}" in addr or addr.endswith(port):
                        url = (t.get("public_url") or "").strip()
                        if url.startswith("https://"):
                            return url
                return (tunnels[0].get("public_url") or "").strip() or None
            except Exception:
                time.sleep(0.8)
        return None

    def start_ngrok(self) -> Optional[subprocess.Popen]:
        """Start ngrok tunnel to port (for HTTPS webhook URL). Requires ngrok installed and authtoken set."""
        port = os.getenv("PORT", "8000")
        try:
            if not self._should_run_ngrok():
                return None
            # ngrok must be in PATH (install via scripts/install_ngrok_vm.sh on VM)
            process = subprocess.Popen(
                ["ngrok", "http", port],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            time.sleep(2)
            if process.poll() is not None:
                logger.warning("[WARN] ngrok exited; is it installed and authtoken set? Run: ngrok config add-authtoken <token>")
                return None
            self.processes.append(process)
            public_url = self._get_ngrok_public_url(port)
            if public_url:
                logger.info(f"[OK] ngrok tunnel: {public_url}")
                logger.info(f"     SendGrid Event Webhook URL: {public_url.rstrip('/')}/webhooks/sendgrid")
            else:
                logger.info("[OK] ngrok started; get URL at http://127.0.0.1:4040")
            return process
        except FileNotFoundError:
            logger.warning("[WARN] ngrok not found in PATH. Install: bash scripts/install_ngrok_vm.sh")
            return None
        except Exception as e:
            logger.warning(f"[WARN] ngrok start failed: {e}")
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
        """Main entry point. Use RUN_MODE=web|worker|all to run only part of the stack (e.g. on Render)."""
        run_mode = (os.getenv("RUN_MODE") or "all").strip().lower()
        logger.info("=" * 60)
        logger.info("IUL Appointment Setter System")
        logger.info(f"RUN_MODE={run_mode}")
        logger.info("=" * 60)

        if not self.check_redis():
            sys.exit(1)
        if not self.init_database():
            sys.exit(1)
        if not self.check_env_vars():
            sys.exit(1)

        logger.info("\n" + "=" * 60)
        logger.info("Starting Services")
        logger.info("=" * 60)

        if run_mode == "web":
            # Render Web Service: FastAPI only (Redis/DB/Celery run elsewhere)
            fastapi = self.start_fastapi()
            if not fastapi:
                logger.error("Failed to start FastAPI. Exiting.")
                sys.exit(1)
            self.processes.append(fastapi)
            logger.info("[OK] Web service running (FastAPI only)")
            self.start_ngrok()  # optional: ENABLE_NGROK=1
        elif run_mode == "worker":
            # Render Background Worker: Celery worker + beat in one process
            worker = self.start_celery_worker_with_beat()
            if not worker:
                logger.error("Failed to start Celery worker+beat. Exiting.")
                sys.exit(1)
            self.processes.append(worker)
            logger.info("[OK] Worker running (Celery worker + beat)")
        else:
            # Local / all: Redis (if local), Celery worker, Celery beat, FastAPI
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
            logger.info("[OK] Full stack running (worker + beat + API)")
            self.start_ngrok()  # optional: ENABLE_NGROK=1

        port = os.getenv("PORT", "8000")
        logger.info("\n" + "=" * 60)
        logger.info("[OK] System is RUNNING")
        logger.info("=" * 60)
        if run_mode != "worker":
            logger.info(f"API: http://0.0.0.0:{port}")
            logger.info(f"Docs: http://0.0.0.0:{port}/docs")
        if run_mode == "all":
            logger.info("\nPress Ctrl+C to stop")
        logger.info("=" * 60 + "\n")

        self.running = True
        signal.signal(signal.SIGINT, lambda s, f: self.stop_all())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop_all())
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
