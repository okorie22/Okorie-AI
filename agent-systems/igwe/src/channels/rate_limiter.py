"""
Send rate limiter - enforces daily/hourly caps and send window restrictions.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
import pytz

from ..storage.models import Message, MessageDirection, MessageChannel
from ..config import sendgrid_config


class SendRateLimiter:
    """
    Tracks and enforces daily/hourly send limits.
    Also checks if current time is within allowed send window.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.config = sendgrid_config
        self.est_tz = pytz.timezone('US/Eastern')
    
    def _get_effective_daily_cap(self) -> int:
        """
        Get the effective daily cap, checking warmup manager first.
        
        Returns:
            Daily cap from warmup schedule if warmup is active,
            otherwise returns config value (post-warmup cap).
        """
        from ..workflow.warmup import WarmupManager
        
        warmup_mgr = WarmupManager()
        
        # If warmup mode is active, use warmup schedule
        if warmup_mgr.config.warmup_mode:
            warmup_cap = warmup_mgr.get_daily_cap()
            logger.debug(f"Using warmup daily cap: {warmup_cap}")
            return warmup_cap
        
        # Post-warmup: use config value
        logger.debug(f"Using post-warmup daily cap: {self.config.daily_send_cap}")
        return self.config.daily_send_cap
    
    def can_send_batch(self, batch_size: int) -> bool:
        """
        Check if batch can be sent without exceeding limits.
        
        Args:
            batch_size: Number of emails to send
        
        Returns:
            True if batch can be sent, False otherwise
        """
        # Check daily cap
        sent_today = self._count_sent_today()
        daily_remaining = self.config.daily_send_cap - sent_today
        
        if batch_size > daily_remaining:
            logger.warning(
                f"Daily cap reached: {sent_today}/{self.config.daily_send_cap} "
                f"(need {batch_size}, have {daily_remaining})"
            )
            return False
        
        # Check hourly cap
        sent_this_hour = self._count_sent_this_hour()
        hourly_remaining = self.config.hourly_send_cap - sent_this_hour
        
        if batch_size > hourly_remaining:
            logger.warning(
                f"Hourly cap reached: {sent_this_hour}/{self.config.hourly_send_cap} "
                f"(need {batch_size}, have {hourly_remaining})"
            )
            return False
        
        return True
    
    def is_within_send_window(self) -> bool:
        """
        Check if current time is within send window (8 AM - 5 PM EST, Mon-Fri).
        
        Returns:
            True if within window, False otherwise
        """
        # Get current time in EST
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
        now_est = now_utc.astimezone(self.est_tz)
        
        # Check weekday
        if self.config.send_weekdays_only:
            if now_est.weekday() >= 5:  # Saturday=5, Sunday=6
                logger.debug(f"Outside send window: Weekend (day {now_est.weekday()})")
                return False
        
        # Check hour range
        current_hour = now_est.hour
        if current_hour < self.config.send_start_hour or current_hour >= self.config.send_end_hour:
            logger.debug(
                f"Outside send window: {current_hour}:00 EST "
                f"(window: {self.config.send_start_hour}:00 - {self.config.send_end_hour}:00)"
            )
            return False
        
        return True
    
    def get_send_stats(self) -> dict:
        """
        Get current send statistics.
        
        Returns:
            Dict with send counts and limits (uses warmup schedule if active)
        """
        sent_today = self._count_sent_today()
        sent_this_hour = self._count_sent_this_hour()
        effective_daily_cap = self._get_effective_daily_cap()
        
        return {
            "sent_today": sent_today,
            "daily_cap": effective_daily_cap,
            "daily_remaining": effective_daily_cap - sent_today,
            "sent_this_hour": sent_this_hour,
            "hourly_cap": self.config.hourly_send_cap,
            "hourly_remaining": self.config.hourly_send_cap - sent_this_hour,
            "within_window": self.is_within_send_window()
        }
    
    def _count_sent_today(self) -> int:
        """Count emails sent today (UTC day)"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        count = self.db.query(Message).filter(
            Message.direction == MessageDirection.OUTBOUND,
            Message.channel == MessageChannel.EMAIL,
            Message.created_at >= today_start
        ).count()
        
        return count
    
    def _count_sent_this_hour(self) -> int:
        """Count emails sent in the current hour"""
        hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        count = self.db.query(Message).filter(
            Message.direction == MessageDirection.OUTBOUND,
            Message.channel == MessageChannel.EMAIL,
            Message.created_at >= hour_start
        ).count()
        
        return count
