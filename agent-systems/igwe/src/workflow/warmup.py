"""
Warmup manager - coordinates email warmup ramp and lead acquisition scaling.
"""
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

from ..config import workflow_config, sendgrid_config


class WarmupManager:
    """
    Manage warmup ramp and coordinate lead acquisition.
    
    4-week warmup schedule to reach 2,500 emails/day (Mon-Fri only).
    """
    
    # Warmup schedule (business day: daily_cap)
    # Only counting weekdays (Mon-Fri)
    WARMUP_SCHEDULE = {
        # Week 1 (days 1-5)
        1: 50,    # Monday
        2: 70,    # Tuesday
        3: 90,    # Wednesday
        4: 120,   # Thursday
        5: 150,   # Friday
        
        # Week 2 (days 6-10)
        6: 250,   # Monday
        7: 350,   # Tuesday
        8: 450,   # Wednesday
        9: 550,   # Thursday
        10: 600,  # Friday
        
        # Week 3 (days 11-15)
        11: 700,  # Monday
        12: 850,  # Tuesday
        13: 1000, # Wednesday
        14: 1150, # Thursday
        15: 1200, # Friday
        
        # Week 4 (days 16-20)
        16: 1500, # Monday
        17: 1800, # Tuesday
        18: 2100, # Wednesday
        19: 2400, # Thursday
        20: 2500, # Friday (target reached!)
    }
    
    def __init__(self):
        self.config = workflow_config
        self.sendgrid_config = sendgrid_config
    
    def get_current_day(self) -> int:
        """
        Calculate current warmup day since start_date (business days only).
        
        Returns:
            Business day number (1-20 for warmup, 21+ for post-warmup)
        """
        if not self.config.warmup_mode:
            return 99  # Post-warmup (return high number)
        
        try:
            # Parse start date
            start_date = datetime.strptime(self.config.warmup_start_date, "%Y-%m-%d").date()
            today = datetime.utcnow().date()
            
            if today < start_date:
                logger.warning(f"Current date {today} is before warmup start {start_date}")
                return 0
            
            # Count business days between start_date and today
            current = start_date
            business_days = 0
            
            while current <= today:
                # Only count weekdays (Mon-Fri)
                if current.weekday() < 5:
                    business_days += 1
                current += timedelta(days=1)
            
            return business_days
        
        except Exception as e:
            logger.error(f"Error calculating warmup day: {e}")
            return 1  # Default to day 1
    
    def get_daily_cap(self) -> int:
        """
        Get today's send cap based on warmup schedule.
        
        Returns:
            Daily send cap for today
        """
        if not self.config.warmup_mode:
            return 2500  # Post-warmup target
        
        day = self.get_current_day()
        
        # If beyond schedule, use target
        if day > 20:
            logger.info("Warmup complete! Using target cap of 2,500/day")
            return 2500
        
        # Get cap from schedule
        cap = self.WARMUP_SCHEDULE.get(day, 50)
        
        logger.info(f"Warmup day {day}: daily cap = {cap}")
        return cap
    
    def get_leads_needed(self) -> int:
        """
        Calculate how many leads to import today.
        
        We need roughly 1.5x the daily email cap in raw leads due to:
        - Scoring filters (only tier 1-2 get auto-contacted)
        - Already contacted leads
        - Duplicates
        
        Returns:
            Number of leads needed today
        """
        daily_cap = self.get_daily_cap()
        
        # Multiplier: need 1.5x raw leads per email sent
        # This accounts for scoring filters and already-contacted leads
        multiplier = 1.5
        
        leads_needed = daily_cap * multiplier
        
        logger.info(f"Leads needed today: {leads_needed} (cap: {daily_cap} × {multiplier})")
        return leads_needed
    
    def get_apify_runs_needed(self) -> int:
        """
        Calculate Apify runs needed today.
        
        Each free Apify token gives ~100 leads per run.
        
        Returns:
            Number of Apify runs needed
        """
        leads_needed = self.get_leads_needed()
        
        # Each run imports ~100 leads
        leads_per_run = 100
        
        runs_needed = (leads_needed // leads_per_run) + 1
        
        logger.info(f"Apify runs needed: {runs_needed} (for {leads_needed} leads)")
        return runs_needed
    
    def should_skip_today(self) -> bool:
        """
        Check if we should skip today (e.g., weekend during warmup).
        
        Returns:
            True if we should skip today, False otherwise
        """
        if not self.sendgrid_config.send_weekdays_only:
            return False
        
        today = datetime.utcnow()
        is_weekend = today.weekday() >= 5  # Saturday=5, Sunday=6
        
        if is_weekend:
            logger.info("Skipping today: Weekend")
            return True
        
        return False
    
    def update_daily_cap_in_config(self):
        """
        Update SendGrid daily cap based on warmup schedule.
        
        This is called at the start of each day to adjust the cap.
        Note: In production, you'd want to persist this or use a dynamic config.
        """
        new_cap = self.get_daily_cap()
        
        # Update in-memory config (Note: this doesn't persist across restarts)
        self.sendgrid_config.daily_send_cap = new_cap
        
        logger.info(f"Updated daily send cap to {new_cap}")
    
    def get_warmup_status(self) -> dict:
        """
        Get current warmup status for monitoring.
        
        Returns:
            Dict with warmup stats
        """
        day = self.get_current_day()
        daily_cap = self.get_daily_cap()
        leads_needed = self.get_leads_needed()
        runs_needed = self.get_apify_runs_needed()
        
        return {
            "warmup_mode": self.config.warmup_mode,
            "warmup_start_date": self.config.warmup_start_date,
            "current_day": day,
            "daily_cap": daily_cap,
            "leads_needed_today": leads_needed,
            "apify_runs_needed": runs_needed,
            "warmup_complete": day > 20,
            "skip_today": self.should_skip_today()
        }
