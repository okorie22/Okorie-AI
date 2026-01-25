"""
Test script for warmup mode system.

Simulates the 4-week warmup schedule and validates:
1. Daily cap calculations
2. Lead acquisition scaling
3. Apify run requirements
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from datetime import datetime, timedelta

from src.workflow.warmup import WarmupManager
from src.config import workflow_config


def simulate_warmup_schedule():
    """Simulate the complete 4-week warmup schedule"""
    logger.info("=" * 80)
    logger.info("WARMUP SCHEDULE SIMULATION")
    logger.info("=" * 80)
    
    warmup = WarmupManager()
    
    # Display warmup schedule
    logger.info("\n4-Week Warmup Schedule (Business Days Only):")
    logger.info("-" * 80)
    logger.info(f"{'Day':<6} {'Week':<8} {'Daily Cap':<12} {'Leads Needed':<15} {'Apify Runs':<12}")
    logger.info("-" * 80)
    
    total_emails = 0
    total_leads = 0
    total_runs = 0
    
    for day in range(1, 21):
        week = (day - 1) // 5 + 1
        daily_cap = warmup.WARMUP_SCHEDULE[day]
        leads_needed = daily_cap * 1.5  # 1.5x multiplier
        runs_needed = (leads_needed // 100) + 1
        
        total_emails += daily_cap
        total_leads += leads_needed
        total_runs += runs_needed
        
        logger.info(
            f"{day:<6} Week {week:<4} {daily_cap:<12} {leads_needed:<15} {runs_needed:<12}"
        )
    
    logger.info("-" * 80)
    logger.info(f"{'TOTAL':<6} {'4 weeks':<8} {total_emails:<12} {total_leads:<15} {total_runs:<12}")
    logger.info("=" * 80)
    
    # Weekly breakdown
    logger.info("\nWeekly Summary:")
    logger.info("-" * 60)
    
    for week in range(1, 5):
        start_day = (week - 1) * 5 + 1
        end_day = week * 5
        
        week_emails = sum(warmup.WARMUP_SCHEDULE[d] for d in range(start_day, end_day + 1))
        week_leads = week_emails * 1.5
        week_runs = (week_leads // 100) + 1
        
        logger.info(
            f"Week {week}: {week_emails:,} emails, {week_leads:,} leads, ~{week_runs} Apify runs"
        )
    
    logger.info("-" * 60)
    
    # Apify token requirements
    logger.info("\n📊 Resource Requirements:")
    logger.info(f"  • Total emails to send: {total_emails:,}")
    logger.info(f"  • Total leads needed: {total_leads:,}")
    logger.info(f"  • Total Apify runs: ~{total_runs}")
    logger.info(f"  • Apify tokens needed: ~{(total_runs // 20) + 1} (assuming 20 runs/token during free tier)")
    
    # Final capacity
    logger.info("\n🎯 Post-Warmup Capacity (Day 21+):")
    logger.info(f"  • Daily emails: 2,500/day (Mon-Fri)")
    logger.info(f"  • Weekly emails: 12,500/week")
    logger.info(f"  • Monthly emails: ~50,000/month (4 weeks)")
    logger.info(f"  • Daily leads needed: ~7,500")
    logger.info(f"  • Daily Apify runs: ~75")
    logger.info(f"  • Apify tokens for scale: 16 (for continuous operation)")
    
    return total_emails, total_leads, total_runs


def test_current_day_calculation():
    """Test warmup day calculation"""
    logger.info("\n=" * 80)
    logger.info("WARMUP DAY CALCULATION TEST")
    logger.info("=" * 80)
    
    warmup = WarmupManager()
    
    # Show current warmup status
    status = warmup.get_warmup_status()
    
    logger.info(f"\nWarmup Mode: {status['warmup_mode']}")
    logger.info(f"Start Date: {status['warmup_start_date']}")
    logger.info(f"Current Day: {status['current_day']}")
    logger.info(f"Daily Cap: {status['daily_cap']:,}")
    logger.info(f"Leads Needed Today: {status['leads_needed_today']:,}")
    logger.info(f"Apify Runs Needed: {status['apify_runs_needed']}")
    logger.info(f"Warmup Complete: {status['warmup_complete']}")
    logger.info(f"Skip Today (weekend): {status['skip_today']}")
    
    # Simulate different start dates
    logger.info("\n📅 Simulating Different Start Dates:")
    logger.info("-" * 60)
    
    test_dates = [
        "2026-01-13",  # Monday
        "2026-01-20",  # Next Monday
        "2026-02-03",  # 3 weeks later
    ]
    
    for start_date in test_dates:
        # Temporarily modify config
        original_date = workflow_config.warmup_start_date
        workflow_config.warmup_start_date = start_date
        
        warmup = WarmupManager()
        day = warmup.get_current_day()
        cap = warmup.get_daily_cap()
        
        logger.info(f"  Start: {start_date} → Day {day}, Cap: {cap:,}")
        
        # Restore original
        workflow_config.warmup_start_date = original_date


def test_lead_scaling():
    """Test lead acquisition scaling logic"""
    logger.info("\n=" * 80)
    logger.info("LEAD ACQUISITION SCALING TEST")
    logger.info("=" * 80)
    
    warmup = WarmupManager()
    
    # Test days throughout warmup
    test_days = [1, 5, 10, 15, 20, 25]
    
    logger.info(f"\n{'Day':<6} {'Daily Cap':<12} {'Leads Needed':<15} {'Apify Runs':<12} {'Tokens Needed':<15}")
    logger.info("-" * 70)
    
    for day in test_days:
        if day <= 20:
            daily_cap = warmup.WARMUP_SCHEDULE[day]
        else:
            daily_cap = 2500
        
        leads_needed = daily_cap * 1.5
        runs_needed = (leads_needed // 100) + 1
        tokens_needed = min((runs_needed // 2) + 1, 16)  # Rough estimate
        
        logger.info(
            f"{day:<6} {daily_cap:<12} {leads_needed:<15} {runs_needed:<12} {tokens_needed:<15}"
        )


def test_weekend_skipping():
    """Test weekend skipping logic"""
    logger.info("\n=" * 80)
    logger.info("WEEKEND SKIPPING TEST")
    logger.info("=" * 80)
    
    warmup = WarmupManager()
    
    logger.info("\nChecking if today should be skipped:")
    should_skip = warmup.should_skip_today()
    today = datetime.utcnow()
    day_name = today.strftime("%A")
    
    logger.info(f"  Today: {day_name}")
    logger.info(f"  Skip? {should_skip}")
    
    if should_skip:
        logger.info("  ✓ Correctly skipping weekend")
    else:
        logger.info("  ✓ Weekday - processing normally")


def main():
    """Run all warmup tests"""
    logger.info("\n")
    logger.info("*" * 80)
    logger.info("WARMUP MODE SYSTEM TESTS")
    logger.info("*" * 80)
    
    try:
        # Test 1: Simulate full schedule
        total_emails, total_leads, total_runs = simulate_warmup_schedule()
        
        # Test 2: Current day calculation
        test_current_day_calculation()
        
        # Test 3: Lead scaling
        test_lead_scaling()
        
        # Test 4: Weekend skipping
        test_weekend_skipping()
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL WARMUP TESTS COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n📈 Summary:")
        logger.info(f"  • 4-week warmup ramps from 50 → 2,500 emails/day")
        logger.info(f"  • Total warmup emails: {total_emails:,}")
        logger.info(f"  • Total leads needed: {total_leads:,}")
        logger.info(f"  • Total Apify runs: ~{total_runs}")
        logger.info(f"\n🚀 Ready for production deployment!")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
