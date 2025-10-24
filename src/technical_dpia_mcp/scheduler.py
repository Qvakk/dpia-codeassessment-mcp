"""
Scheduler for automated documentation updates.
"""

import asyncio
import logging
import os
from datetime import datetime, time as dt_time
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class DocumentationScheduler:
    """Scheduler for periodic documentation updates."""
    
    def __init__(
        self,
        update_callback: Callable,
        interval_days: Optional[int] = None,
        update_time: Optional[str] = None,
    ):
        """
        Initialize scheduler.
        
        Args:
            update_callback: Async function to call for updates
            interval_days: Update interval in days
            update_time: Time of day to run updates (HH:MM format)
        """
        self.update_callback = update_callback
        self.interval_days = interval_days or int(
            os.getenv("UPDATE_INTERVAL_DAYS", "7")
        )
        self.update_time = update_time or os.getenv("UPDATE_TIME", "02:00")
        
        self.scheduler = AsyncIOScheduler()
        self._setup_triggers()
        
        logger.info(
            f"DocumentationScheduler initialized: "
            f"interval={self.interval_days} days, time={self.update_time}"
        )
    
    def _setup_triggers(self):
        """Setup scheduled triggers."""
        # Parse update time
        try:
            hour, minute = map(int, self.update_time.split(":"))
        except ValueError:
            logger.warning(
                f"Invalid UPDATE_TIME format '{self.update_time}', using 02:00"
            )
            hour, minute = 2, 0
        
        # Create cron trigger for specific time
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
        )
        
        # Add job
        self.scheduler.add_job(
            self._run_update,
            trigger=trigger,
            id="documentation_update",
            name="Documentation Update",
            replace_existing=True,
        )
        
        logger.info(
            f"Scheduled documentation updates at {hour:02d}:{minute:02d} every day"
        )
    
    async def _run_update(self):
        """Run the update callback."""
        logger.info("Starting scheduled documentation update")
        try:
            await self.update_callback()
            logger.info("Scheduled documentation update completed successfully")
        except Exception as e:
            logger.error(f"Error during scheduled update: {e}", exc_info=True)
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    async def trigger_update_now(self):
        """Manually trigger an update immediately."""
        logger.info("Triggering manual documentation update")
        await self._run_update()
