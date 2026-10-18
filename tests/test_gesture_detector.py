"""Unit tests for hand gesture detection."""

from dataclasses import dataclass
import pytest

from app.vision.gesture_detector import GestureDetector, GestureType


@dataclass
class Point:
    x: float
    y: float


def _create_mock_hand(open_palm: bool = False, point_up: bool = False, wrist_x: float = 0.5):
    """Creates a synthetic 21-point MediaPipe hand landmark list."""
    pts = [Point(x=wrist_x, y=0.8) for _ in range(21)]

    if open_palm:
        # All 4 fingers extended upward (tip.y < pip.y)
        # Index: tip=8, pip=6
        pts[8].y = 0.2
        pts[6].y = 0.4
        # Middle: tip=12, pip=10
        pts[12].y = 0.18
        pts[10].y = 0.4
        # Ring: tip=16, pip=14
        pts[16].y = 0.22
        pts[14].y = 0.4
        # Pinky: tip=20, pip=18
        pts[20].y = 0.25
        pts[18].y = 0.45
    elif point_up:
        # Only index extended
        pts[8].y = 0.2
        pts[6].y = 0.4
        # Others curled (tip.y > pip.y)
        pts[12].y = 0.55
        pts[10].y = 0.45
        pts[16].y = 0.55
        pts[14].y = 0.45
        pts[20].y = 0.55
        pts[18].y = 0.45
    else:
        # Fist / curled
        pts[8].y = 0.55
        pts[6].y = 0.45
        pts[12].y = 0.55
        pts[10].y = 0.45
        pts[16].y = 0.55
        pts[14].y = 0.45
        pts[20].y = 0.55
        pts[18].y = 0.45

    return pts


def test_open_palm_gesture_detection():
    """Detects open palm pose and emits pause/play gesture event."""
    gd = GestureDetector(debounce_seconds=1.0)
    hand = _create_mock_hand(open_palm=True)

    evt = gd.process_hand_landmarks(hand, current_time=100.0)
    assert evt is not None
    assert evt.gesture == GestureType.OPEN_PALM
    assert "Jeda / Putar" in evt.label


def test_point_up_mute_gesture_detection():
    """Detects pointing / index finger pose and emits mute gesture event."""
    gd = GestureDetector(debounce_seconds=1.0)
    hand = _create_mock_hand(point_up=True)

    evt = gd.process_hand_landmarks(hand, current_time=100.0)
    assert evt is not None
    assert evt.gesture == GestureType.POINT_UP
    assert "Senyapkan" in evt.label


def test_gesture_debounce():
    """Consecutive gestures within debounce window are ignored."""
    gd = GestureDetector(debounce_seconds=1.2)
    hand = _create_mock_hand(open_palm=True)

    e1 = gd.process_hand_landmarks(hand, current_time=100.0)
    assert e1 is not None

    # Within 1.2s: should return None
    e2 = gd.process_hand_landmarks(hand, current_time=100.5)
    assert e2 is None

    # After 1.2s: should trigger again
    e3 = gd.process_hand_landmarks(hand, current_time=101.5)
    assert e3 is not None


def test_swipe_right_detection():
    """Rapid horizontal motion left-to-right triggers SWIPE_RIGHT (Next Track)."""
    gd = GestureDetector(debounce_seconds=1.0)

    # Frame 1: at x=0.2, t=10.0
    gd.process_hand_landmarks(_create_mock_hand(open_palm=False, wrist_x=0.2), current_time=10.0)
    # Frame 2: at x=0.3, t=10.1
    gd.process_hand_landmarks(_create_mock_hand(open_palm=False, wrist_x=0.3), current_time=10.1)
    # Frame 3: at x=0.45, t=10.2
    gd.process_hand_landmarks(_create_mock_hand(open_palm=False, wrist_x=0.45), current_time=10.2)
    # Frame 4: at x=0.6, t=10.3 (delta = 0.4 > 0.25)
    evt = gd.process_hand_landmarks(_create_mock_hand(open_palm=False, wrist_x=0.6), current_time=10.3)

    assert evt is not None
    assert evt.gesture == GestureType.SWIPE_RIGHT
    assert "Berikutnya" in evt.label
