"""Presence detector and state machine for JARVIS Smart Presence.

Tracks face detection signals, manages absence timeouts for Windows auto-lock,
and emits return greeting events when the user sits back down.
"""

from dataclasses import dataclass
from enum import Enum
import time
from typing import Optional

from app.core.logger import setup_logger

logger = setup_logger("jarvis.vision.presence")


class PresenceState(str, Enum):
    """Current presence state of the user in front of the PC."""
    PRESENT = "present"
    AWAY = "away"
    LOCKED = "locked"


class PresenceEventType(str, Enum):
    """Presence events triggered by state transitions."""
    USER_RETURNED = "user_returned"
    USER_ABSENT_WARNING = "user_absent_warning"
    USER_ABSENT_TIMEOUT = "user_absent_timeout"


@dataclass
class PresenceEvent:
    """Event emitted when presence state changes."""
    event_type: PresenceEventType
    duration_away: float
    message: str = ""


class PresenceDetector:
    """Monitors face presence, handles return greetings, and triggers 90s auto-lock."""

    def __init__(
        self,
        autolock_seconds: int = 90,
        return_greeting_threshold: float = 60.0,
        warning_lead_seconds: float = 10.0,
    ):
        self.autolock_seconds = max(15, autolock_seconds)
        self.return_greeting_threshold = max(10.0, return_greeting_threshold)
        self.warning_lead_seconds = max(3.0, warning_lead_seconds)

        self.state = PresenceState.PRESENT
        self.last_seen_time = time.time()
        self.departure_time: Optional[float] = None
        self._warning_emitted = False
        self._lock_emitted = False

    def update(self, face_detected: bool, current_time: Optional[float] = None) -> Optional[PresenceEvent]:
        """Updates presence state machine with new camera frame observation."""
        now = time.time() if current_time is None else current_time

        if face_detected:
            # Face is detected in current frame
            event: Optional[PresenceEvent] = None

            if self.state in (PresenceState.AWAY, PresenceState.LOCKED) and self.departure_time is not None:
                duration_away = now - self.departure_time
                if duration_away >= self.return_greeting_threshold:
                    event = PresenceEvent(
                        event_type=PresenceEventType.USER_RETURNED,
                        duration_away=duration_away,
                        message=f"User returned after {duration_away:.1f}s away.",
                    )
                    logger.info("Presence event: USER_RETURNED (away %.1fs)", duration_away)

            # Reset tracking
            self.state = PresenceState.PRESENT
            self.last_seen_time = now
            self.departure_time = None
            self._warning_emitted = False
            self._lock_emitted = False
            return event

        # Face is NOT detected
        if self.departure_time is None:
            self.departure_time = self.last_seen_time

        away_duration = now - self.last_seen_time

        # Check for 90s timeout (Auto-Lock)
        if away_duration >= self.autolock_seconds:
            if not self._lock_emitted:
                self.state = PresenceState.LOCKED
                self._lock_emitted = True
                logger.info("Presence event: USER_ABSENT_TIMEOUT (away %.1fs >= %ds)", away_duration, self.autolock_seconds)
                return PresenceEvent(
                    event_type=PresenceEventType.USER_ABSENT_TIMEOUT,
                    duration_away=away_duration,
                    message=f"Auto-lock triggered after {away_duration:.1f}s absence.",
                )
            return None

        # Check for 10s pre-lock warning
        warning_time = self.autolock_seconds - self.warning_lead_seconds
        if away_duration >= warning_time and not self._warning_emitted:
            self.state = PresenceState.AWAY
            self._warning_emitted = True
            logger.info("Presence event: USER_ABSENT_WARNING (away %.1fs, lock in %.1fs)", away_duration, self.autolock_seconds - away_duration)
            return PresenceEvent(
                event_type=PresenceEventType.USER_ABSENT_WARNING,
                duration_away=away_duration,
                message="Layar akan dikunci otomatis sebentar lagi karena Anda tidak di depan laptop.",
            )

        if away_duration > 5.0 and self.state == PresenceState.PRESENT:
            self.state = PresenceState.AWAY

        return None

    def reset(self) -> None:
        """Resets presence state to active PRESENT."""
        self.state = PresenceState.PRESENT
        self.last_seen_time = time.time()
        self.departure_time = None
        self._warning_emitted = False
        self._lock_emitted = False
