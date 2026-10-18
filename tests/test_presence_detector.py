"""Unit tests for JARVIS Smart Presence state machine and auto-lock."""

import pytest
from app.vision.presence_detector import PresenceDetector, PresenceEventType, PresenceState


def test_presence_initial_state():
    """Initial presence state must be PRESENT."""
    pd = PresenceDetector(autolock_seconds=90, return_greeting_threshold=60.0)
    assert pd.state == PresenceState.PRESENT


def test_presence_remains_active_when_face_detected():
    """Consecutive face observations maintain PRESENT state without events."""
    pd = PresenceDetector(autolock_seconds=90, return_greeting_threshold=60.0)
    evt = pd.update(face_detected=True, current_time=100.0)
    assert evt is None
    assert pd.state == PresenceState.PRESENT

    evt2 = pd.update(face_detected=True, current_time=105.0)
    assert evt2 is None
    assert pd.state == PresenceState.PRESENT


def test_presence_brief_absence_no_greeting():
    """Brief face disappearance (e.g. 5s looking away) does NOT trigger return greeting."""
    pd = PresenceDetector(autolock_seconds=90, return_greeting_threshold=60.0)
    pd.update(face_detected=True, current_time=100.0)

    # Face disappears for 5 seconds
    evt_away = pd.update(face_detected=False, current_time=105.0)
    assert evt_away is None

    # Face returns at 106s (away only 6s < 60s threshold)
    evt_return = pd.update(face_detected=True, current_time=106.0)
    assert evt_return is None
    assert pd.state == PresenceState.PRESENT


def test_presence_return_greeting_after_long_absence():
    """Face returning after >60s emits USER_RETURNED greeting event."""
    pd = PresenceDetector(autolock_seconds=90, return_greeting_threshold=60.0)
    pd.update(face_detected=True, current_time=100.0)

    # Disappears at 100s, checked at 130s
    pd.update(face_detected=False, current_time=130.0)
    assert pd.state == PresenceState.AWAY

    # Returns at 175s (away 75s > 60s)
    evt = pd.update(face_detected=True, current_time=175.0)
    assert evt is not None
    assert evt.event_type == PresenceEventType.USER_RETURNED
    assert evt.duration_away >= 60.0
    assert pd.state == PresenceState.PRESENT


def test_presence_warning_and_autolock_flow():
    """State machine emits 10s pre-warning, then 90s timeout auto-lock event."""
    pd = PresenceDetector(autolock_seconds=90, return_greeting_threshold=60.0, warning_lead_seconds=10.0)
    pd.update(face_detected=True, current_time=100.0)

    # At 170s (away 70s): no warning yet
    e1 = pd.update(face_detected=False, current_time=170.0)
    assert e1 is None

    # At 181s (away 81s >= 80s): pre-lock warning emitted!
    e2 = pd.update(face_detected=False, current_time=181.0)
    assert e2 is not None
    assert e2.event_type == PresenceEventType.USER_ABSENT_WARNING

    # Subsequent check before 90s should not duplicate warning
    e2_dup = pd.update(face_detected=False, current_time=185.0)
    assert e2_dup is None

    # At 191s (away 91s >= 90s): auto-lock timeout event emitted!
    e3 = pd.update(face_detected=False, current_time=191.0)
    assert e3 is not None
    assert e3.event_type == PresenceEventType.USER_ABSENT_TIMEOUT
    assert pd.state == PresenceState.LOCKED
