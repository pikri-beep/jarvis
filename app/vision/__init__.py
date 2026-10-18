"""Vision & Webcam Smart Presence / Gesture Control package for JARVIS."""

from typing import Optional
from app.vision.gesture_detector import GestureDetector, GestureEvent, GestureType
from app.vision.presence_detector import PresenceDetector, PresenceEvent, PresenceEventType
from app.vision.vision_manager import VisionManager

__all__ = [
    "GestureDetector",
    "GestureEvent",
    "GestureType",
    "PresenceDetector",
    "PresenceEvent",
    "PresenceEventType",
    "VisionManager",
    "get_vision_manager",
]

_vision_manager_instance: Optional[VisionManager] = None


def get_vision_manager() -> VisionManager:
    """Returns or creates the singleton VisionManager instance."""
    global _vision_manager_instance
    if _vision_manager_instance is None:
        _vision_manager_instance = VisionManager()
    return _vision_manager_instance
