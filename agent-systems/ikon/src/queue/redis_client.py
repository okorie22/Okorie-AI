"""
Redis Queue Client for IKON IUL Pipeline
Handles job queuing, dequeuing, retry logic, and DLQ management
"""

import json
import time
import logging
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import redis
from redis.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger("redis_client")


@dataclass
class JobSchema:
    """Schema for pipeline jobs"""
    job_id: str
    idea_id: str
    dedupe_key: str
    payload: Dict[str, Any]
    attempt: int = 0
    max_attempts: int = 3
    created_at: float = None
    not_before: float = None
    error_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.not_before is None:
            self.not_before = time.time()
        if self.error_history is None:
            self.error_history = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobSchema':
        """Create JobSchema from dictionary"""
        return cls(**data)
    
    def should_process(self) -> bool:
        """Check if job should be processed now"""
        return time.time() >= self.not_before
    
    def increment_attempt(self, error: str = None):
        """Increment attempt counter and add error to history"""
        self.attempt += 1
        if error:
            self.error_history.append({
                "attempt": self.attempt,
                "error": error,
                "timestamp": time.time()
            })
        
        # Exponential backoff: 60s, 300s (5m), 900s (15m)
        backoff_delays = [60, 300, 900]
        if self.attempt < len(backoff_delays):
            self.not_before = time.time() + backoff_delays[self.attempt - 1]
    
    def is_exhausted(self) -> bool:
        """Check if job has exhausted retry attempts"""
        return self.attempt >= self.max_attempts


class RedisQueueClient:
    """Redis-based queue client for IKON pipeline"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", namespace: str = "ikon"):
        """
        Initialize Redis queue client
        
        Args:
            redis_url: Redis connection URL
            namespace: Namespace prefix for all keys
        """
        self.redis_url = redis_url
        self.namespace = namespace
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish Redis connection with retry logic"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                self.client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                self.client.ping()
                logger.info(f"✅ Connected to Redis at {self.redis_url}")
                return
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"❌ Failed to connect to Redis after {max_retries} attempts: {e}")
                    raise
    
    def _key(self, queue_name: str) -> str:
        """Generate namespaced key"""
        return f"{self.namespace}:{queue_name}"
    
    def enqueue(self, queue_name: str, job: JobSchema) -> bool:
        """
        Enqueue a job to the specified queue
        
        Args:
            queue_name: Queue name (e.g., 'ideas:ready')
            job: JobSchema instance
            
        Returns:
            True if successful
        """
        try:
            key = self._key(queue_name)
            job_json = json.dumps(job.to_dict())
            self.client.lpush(key, job_json)
            logger.debug(f"Enqueued job {job.job_id} to {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue job {job.job_id}: {e}")
            return False
    
    def dequeue(self, queue_name: str, timeout: int = 0) -> Optional[JobSchema]:
        """
        Dequeue a job from the specified queue
        
        Args:
            queue_name: Queue name
            timeout: Blocking timeout in seconds (0 = non-blocking)
            
        Returns:
            JobSchema if available, None otherwise
        """
        try:
            key = self._key(queue_name)
            
            if timeout > 0:
                result = self.client.brpop(key, timeout=timeout)
                if result:
                    _, job_json = result
                else:
                    return None
            else:
                job_json = self.client.rpop(key)
                if not job_json:
                    return None
            
            job_dict = json.loads(job_json)
            job = JobSchema.from_dict(job_dict)
            
            # Check if job should be processed now (backoff logic)
            if not job.should_process():
                # Re-enqueue if not ready
                self.enqueue(queue_name, job)
                return None
            
            logger.debug(f"Dequeued job {job.job_id} from {queue_name}")
            return job
            
        except Exception as e:
            logger.error(f"Failed to dequeue from {queue_name}: {e}")
            return None
    
    def peek(self, queue_name: str, count: int = 1) -> List[JobSchema]:
        """
        Peek at jobs in queue without removing them
        
        Args:
            queue_name: Queue name
            count: Number of jobs to peek
            
        Returns:
            List of JobSchema instances
        """
        try:
            key = self._key(queue_name)
            job_jsons = self.client.lrange(key, -count, -1)
            
            jobs = []
            for job_json in job_jsons:
                job_dict = json.loads(job_json)
                jobs.append(JobSchema.from_dict(job_dict))
            
            return jobs
        except Exception as e:
            logger.error(f"Failed to peek {queue_name}: {e}")
            return []
    
    def length(self, queue_name: str) -> int:
        """
        Get queue length
        
        Args:
            queue_name: Queue name
            
        Returns:
            Number of jobs in queue
        """
        try:
            key = self._key(queue_name)
            return self.client.llen(key)
        except Exception as e:
            logger.error(f"Failed to get length of {queue_name}: {e}")
            return 0
    
    def move_to_dlq(self, job: JobSchema, reason: str = None):
        """
        Move job to dead letter queue
        
        Args:
            job: JobSchema instance
            reason: Reason for moving to DLQ
        """
        try:
            if reason:
                job.error_history.append({
                    "final_error": reason,
                    "timestamp": time.time()
                })
            
            dlq_key = self._key("ideas:dead")
            job_json = json.dumps(job.to_dict())
            self.client.lpush(dlq_key, job_json)
            logger.warning(f"Moved job {job.job_id} to DLQ: {reason}")
        except Exception as e:
            logger.error(f"Failed to move job {job.job_id} to DLQ: {e}")
    
    def requeue_with_backoff(self, queue_name: str, job: JobSchema, error: str):
        """
        Requeue job with exponential backoff or move to DLQ if exhausted
        
        Args:
            queue_name: Original queue name
            job: JobSchema instance
            error: Error message
        """
        job.increment_attempt(error)
        
        if job.is_exhausted():
            self.move_to_dlq(job, f"Max attempts ({job.max_attempts}) exceeded")
        else:
            self.enqueue(queue_name, job)
            logger.info(f"Requeued job {job.job_id} with backoff (attempt {job.attempt}/{job.max_attempts})")
    
    def clear_queue(self, queue_name: str) -> int:
        """
        Clear all jobs from queue (use with caution)
        
        Args:
            queue_name: Queue name
            
        Returns:
            Number of jobs removed
        """
        try:
            key = self._key(queue_name)
            count = self.client.llen(key)
            self.client.delete(key)
            logger.warning(f"Cleared {count} jobs from {queue_name}")
            return count
        except Exception as e:
            logger.error(f"Failed to clear {queue_name}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics for all queues
        
        Returns:
            Dictionary of queue names to lengths
        """
        queues = [
            "ideas:ready",
            "ideas:dead",
            "pipeline:tts",
            "pipeline:render",
            "pipeline:publish",
            "engagement:inbox"
        ]
        
        stats = {}
        for queue in queues:
            stats[queue] = self.length(queue)
        
        return stats
    
    def healthcheck(self) -> bool:
        """
        Check if Redis connection is healthy
        
        Returns:
            True if healthy
        """
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis healthcheck failed: {e}")
            return False


def create_job(idea_id: str, payload: Dict[str, Any], dedupe_key: str = None) -> JobSchema:
    """
    Helper function to create a new job
    
    Args:
        idea_id: Unique idea identifier
        payload: Job payload (idea data)
        dedupe_key: Optional deduplication key
        
    Returns:
        JobSchema instance
    """
    if dedupe_key is None:
        # Generate dedupe key from idea_id and timestamp
        dedupe_key = f"{idea_id}_{int(time.time())}"
    
    return JobSchema(
        job_id=str(uuid.uuid4()),
        idea_id=idea_id,
        dedupe_key=dedupe_key,
        payload=payload
    )
