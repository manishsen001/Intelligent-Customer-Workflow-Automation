"""Reminder and Calendar Workflow Module."""

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum

from src.config.logging_config import logger
from src.config.settings import settings


class ReminderFrequency(Enum):
    """Reminder frequency options."""

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class Reminder:
    """Represents a reminder."""

    id: str
    title: str
    description: str
    trigger_time: str
    frequency: ReminderFrequency
    enabled: bool = True
    created_at: str | None = None
    last_triggered: str | None = None
    next_trigger: str | None = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.next_trigger is None:
            self.next_trigger = self.trigger_time


@dataclass
class ReminderResult:
    """Result of a reminder operation."""

    success: bool
    message: str
    error: str | None = None
    reminder: Reminder | None = None
    reminders: list[Reminder] | None = None


class ReminderManager:
    """Manages reminders and notifications."""

    def __init__(self):
        self.reminders_file = settings.DATA_DIR / "reminders.json"
        self.reminders: dict[str, Reminder] = {}
        self._running = False
        self._check_thread: threading.Thread | None = None
        self._load_reminders()
        self._start_checker()

    def _load_reminders(self):
        """Load reminders from file."""
        try:
            if self.reminders_file.exists():
                with open(self.reminders_file) as f:
                    data = json.load(f)
                for item in data:
                    item["frequency"] = ReminderFrequency(item["frequency"])
                    reminder = Reminder(**item)
                    self.reminders[reminder.id] = reminder
                logger.info(f"Loaded {len(self.reminders)} reminders")
        except Exception as e:
            logger.error(f"Failed to load reminders: {e}")

    def _save_reminders(self):
        """Save reminders to file."""
        try:
            data = []
            for r in self.reminders.values():
                d = asdict(r)
                d["frequency"] = r.frequency.value
                data.append(d)
            with open(self.reminders_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")

    def _start_checker(self):
        """Start the background reminder checker."""
        if self._running:
            return
        self._running = True
        self._check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self._check_thread.start()
        logger.info("Reminder checker started")

    def _check_loop(self):
        """Background loop to check for due reminders."""
        while self._running:
            try:
                self._check_due_reminders()
            except Exception as e:
                logger.error(f"Reminder check error: {e}")
            time.sleep(30)  # Check every 30 seconds

    def _check_due_reminders(self):
        """Check and trigger due reminders."""
        now = datetime.now()
        for reminder in list(self.reminders.values()):
            if not reminder.enabled:
                continue

            try:
                next_trigger = datetime.fromisoformat(reminder.next_trigger)
                if now >= next_trigger:
                    self._trigger_reminder(reminder)
                    self._update_next_trigger(reminder)
            except ValueError:
                logger.error(f"Invalid trigger time for reminder {reminder.id}")

    def _trigger_reminder(self, reminder: Reminder):
        """Trigger a reminder notification."""
        logger.info(f"REMINDER: {reminder.title} - {reminder.description}")
        reminder.last_triggered = datetime.now().isoformat()

        # Here you could add: desktop notification, email, webhook, etc.
        # For now, just log it
        self._save_reminders()

    def _update_next_trigger(self, reminder: Reminder):
        """Calculate next trigger time based on frequency."""
        if reminder.frequency == ReminderFrequency.ONCE:
            reminder.enabled = False
            reminder.next_trigger = None
        else:
            last_triggered = reminder.last_triggered or datetime.now().isoformat()
            last = datetime.fromisoformat(last_triggered)
            if reminder.frequency == ReminderFrequency.DAILY:
                reminder.next_trigger = (last + timedelta(days=1)).isoformat()
            elif reminder.frequency == ReminderFrequency.WEEKLY:
                reminder.next_trigger = (last + timedelta(weeks=1)).isoformat()
            elif reminder.frequency == ReminderFrequency.MONTHLY:
                # Approximate month addition
                reminder.next_trigger = (last + timedelta(days=30)).isoformat()
            elif reminder.frequency == ReminderFrequency.YEARLY:
                reminder.next_trigger = (last + timedelta(days=365)).isoformat()
        self._save_reminders()

    def set_reminder(
        self, title: str, description: str, trigger_time: str, frequency: str = "once"
    ) -> ReminderResult:
        """Create a new reminder."""
        try:
            # Parse trigger time
            trigger_dt = datetime.fromisoformat(trigger_time)
            if trigger_dt < datetime.now():
                return ReminderResult(
                    success=False,
                    message="",
                    error="Trigger time must be in the future",
                )

            # Validate frequency
            try:
                freq = ReminderFrequency(frequency.lower())
            except ValueError:
                return ReminderResult(
                    success=False,
                    message="",
                    error=f"Invalid frequency. Options: {[f.value for f in ReminderFrequency]}",
                )

            reminder = Reminder(
                id=str(uuid.uuid4())[:8],
                title=title,
                description=description,
                trigger_time=trigger_time,
                frequency=freq,
            )

            self.reminders[reminder.id] = reminder
            self._save_reminders()

            logger.info(f"Reminder created: {reminder.id} - {title}")
            return ReminderResult(
                success=True,
                message=f"Reminder '{title}' set for {trigger_time}",
                reminder=reminder,
            )

        except ValueError as e:
            return ReminderResult(
                success=False, message="", error=f"Invalid time format: {e!s}"
            )
        except Exception as e:
            logger.error(f"Set reminder error: {e}")
            return ReminderResult(success=False, message="", error=str(e))

    def list_reminders(self, include_disabled: bool = False) -> ReminderResult:
        """List all reminders."""
        try:
            reminders = list(self.reminders.values())
            if not include_disabled:
                reminders = [r for r in reminders if r.enabled]

            # Sort by next trigger time
            reminders.sort(key=lambda r: r.next_trigger or "9999-12-31")

            return ReminderResult(
                success=True,
                message=f"Found {len(reminders)} reminders",
                reminders=reminders,
            )
        except Exception as e:
            logger.error(f"List reminders error: {e}")
            return ReminderResult(success=False, message="", error=str(e))

    def cancel_reminder(self, reminder_id: str) -> ReminderResult:
        """Cancel/delete a reminder."""
        try:
            if reminder_id not in self.reminders:
                return ReminderResult(
                    success=False,
                    message="",
                    error=f"Reminder '{reminder_id}' not found",
                )

            reminder = self.reminders.pop(reminder_id)
            self._save_reminders()

            logger.info(f"Reminder cancelled: {reminder_id}")
            return ReminderResult(
                success=True,
                message=f"Reminder '{reminder.title}' cancelled",
                reminder=reminder,
            )
        except Exception as e:
            logger.error(f"Cancel reminder error: {e}")
            return ReminderResult(success=False, message="", error=str(e))

    def enable_reminder(self, reminder_id: str, enabled: bool = True) -> ReminderResult:
        """Enable or disable a reminder."""
        try:
            if reminder_id not in self.reminders:
                return ReminderResult(
                    success=False,
                    message="",
                    error=f"Reminder '{reminder_id}' not found",
                )

            reminder = self.reminders[reminder_id]
            reminder.enabled = enabled
            self._save_reminders()

            status = "enabled" if enabled else "disabled"
            return ReminderResult(
                success=True,
                message=f"Reminder '{reminder.title}' {status}",
                reminder=reminder,
            )
        except Exception as e:
            logger.error(f"Enable reminder error: {e}")
            return ReminderResult(success=False, message="", error=str(e))

    def set_calendar_event(
        self,
        title: str,
        description: str,
        start_time: str,
        end_time: str | None = None,
        location: str | None = None,
    ) -> ReminderResult:
        """Create a calendar event (stored as a special reminder)."""
        try:
            start_dt = datetime.fromisoformat(start_time)
            if start_dt < datetime.now():
                return ReminderResult(
                    success=False, message="", error="Start time must be in the future"
                )

            if end_time:
                end_dt = datetime.fromisoformat(end_time)
                if end_dt <= start_dt:
                    return ReminderResult(
                        success=False,
                        message="",
                        error="End time must be after start time",
                    )

            # Create event as a one-time reminder with extra metadata
            reminder = Reminder(
                id=str(uuid.uuid4())[:8],
                title=f"📅 {title}",
                description=description
                + (f"\nLocation: {location}" if location else ""),
                trigger_time=start_time,
                frequency=ReminderFrequency.ONCE,
            )

            # Store event metadata
            event_data = {
                "type": "calendar_event",
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
            }

            self.reminders[reminder.id] = reminder
            self._save_reminders()

            return ReminderResult(
                success=True,
                message=f"Calendar event '{title}' created for {start_time}",
                reminder=reminder,
            )
        except ValueError as e:
            return ReminderResult(
                success=False, message="", error=f"Invalid time format: {e!s}"
            )
        except Exception as e:
            logger.error(f"Set calendar event error: {e}")
            return ReminderResult(success=False, message="", error=str(e))

    def shutdown(self):
        """Shutdown the reminder manager."""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5)
        logger.info("Reminder manager shutdown")


def create_reminder_manager() -> ReminderManager:
    """Factory function to create reminder manager instance."""
    return ReminderManager()
