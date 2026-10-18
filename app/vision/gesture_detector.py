"""Hand gesture recognition engine for JARVIS Media Control.

Uses MediaPipe Hands landmarks to recognize:
- Open Palm (🖐️): Toggle Pause / Play
- Swipe Right (➡️): Next Track
- Swipe Left (⬅️): Previous Track
- Pointing / Finger to Lips (☝️): Toggle Mute / Unmute
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
import math
import time
from typing import Any, List, Optional, Tuple

from app.core.logger import setup_logger

logger = setup_logger("jarvis.vision.gesture")


class GestureType(str, Enum):
    """Recognized hand gesture categories."""
    NONE = "none"
    OPEN_PALM = "open_palm"       # 🖐️ Pause / Resume
    SWIPE_RIGHT = "swipe_right"   # ➡️ Next track
    SWIPE_LEFT = "swipe_left"     # ⬅️ Previous track
    POINT_UP = "point_up"         # ☝️ Mute / Unmute


@dataclass
class GestureEvent:
    """Event emitted when a recognized hand gesture occurs."""
    gesture: GestureType
    label: str
    confidence: float = 1.0


class GestureDetector:
    """Classifies hand landmark coordinates into actionable media gestures."""

    def __init__(self, debounce_seconds: float = 1.2):
        self.debounce_seconds = debounce_seconds
        self.last_trigger_time = 0.0
        self.last_gesture: GestureType = GestureType.NONE

        # History buffer for swipe detection: (timestamp, x_coord)
        self._pos_history = deque(maxlen=15)

    def _is_finger_extended(self, landmarks: Any, tip_idx: int, pip_idx: int) -> bool:
        """Returns True if the given finger is extended upward/outward."""
        try:
            tip = landmarks[tip_idx]
            pip = landmarks[pip_idx]
            # In normalized image coordinates, y=0 is top, so tip.y < pip.y means extended upward
            return tip.y < pip.y
        except Exception:
            return False

    def _classify_static_pose(self, landmarks: Any) -> GestureType:
        """Determines static finger configuration (Open Palm vs Pointing)."""
        # Landmark indices
        # 8: Index, 12: Middle, 16: Ring, 20: Pinky
        index_ext = self._is_finger_extended(landmarks, 8, 6)
        middle_ext = self._is_finger_extended(landmarks, 12, 10)
        ring_ext = self._is_finger_extended(landmarks, 16, 14)
        pinky_ext = self._is_finger_extended(landmarks, 20, 18)

        # Check Point Up (only index finger extended)
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return GestureType.POINT_UP

        # Check Open Palm (all 4 main fingers extended)
        if index_ext and middle_ext and ring_ext and pinky_ext:
            return GestureType.OPEN_PALM

        return GestureType.NONE

    def _detect_swipe(self, now: float) -> GestureType:
        """Analyzes recent wrist/palm horizontal velocity to detect swipes."""
        if len(self._pos_history) < 4:
            return GestureType.NONE

        oldest_time, oldest_x = self._pos_history[0]
        latest_time, latest_x = self._pos_history[-1]

        dt = latest_time - oldest_time
        if dt < 0.15 or dt > 0.6:
            return GestureType.NONE

        dx = latest_x - oldest_x
        # Velocity threshold (minimum 0.25 horizontal frame travel)
        if dx > 0.25:
            # Moving left-to-right
            self._pos_history.clear()
            return GestureType.SWIPE_RIGHT
        elif dx < -0.25:
            # Moving right-to-left
            self._pos_history.clear()
            return GestureType.SWIPE_LEFT

        return GestureType.NONE

    def process_hand_landmarks(
        self,
        landmarks: Any,
        current_time: Optional[float] = None,
    ) -> Optional[GestureEvent]:
        """Evaluates detected hand landmarks and emits debounced media gesture events."""
        now = time.time() if current_time is None else current_time

        if landmarks is None or len(landmarks) < 21:
            self._pos_history.clear()
            return None

        # Track wrist (idx 0) or palm center for swipe detection
        wrist_x = landmarks[0].x
        self._pos_history.append((now, wrist_x))

        # Check if currently in debounce cooldown
        if now - self.last_trigger_time < self.debounce_seconds:
            return None

        # 1. Check dynamic swipe gestures first (high priority for skips)
        swipe = self._detect_swipe(now)
        if swipe == GestureType.SWIPE_RIGHT:
            self.last_trigger_time = now
            self.last_gesture = swipe
            logger.info("Hand gesture recognized: SWIPE_RIGHT ➡️ (Next Track)")
            return GestureEvent(gesture=swipe, label="⏭️ Lagu Berikutnya")
        elif swipe == GestureType.SWIPE_LEFT:
            self.last_trigger_time = now
            self.last_gesture = swipe
            logger.info("Hand gesture recognized: SWIPE_LEFT ⬅️ (Previous Track)")
            return GestureEvent(gesture=swipe, label="⏮️ Lagu Sebelumnya")

        # 2. Check static hand pose
        pose = self._classify_static_pose(landmarks)
        if pose == GestureType.OPEN_PALM:
            self.last_trigger_time = now
            self.last_gesture = pose
            logger.info("Hand gesture recognized: OPEN_PALM 🖐️ (Toggle Pause/Play)")
            return GestureEvent(gesture=pose, label="🖐️ Jeda / Putar Musik")
        elif pose == GestureType.POINT_UP:
            self.last_trigger_time = now
            self.last_gesture = pose
            logger.info("Hand gesture recognized: POINT_UP ☝️ (Toggle Mute)")
            return GestureEvent(gesture=pose, label="🔇 Senyapkan / Bunyikan")

        return None

    def reset(self) -> None:
        """Clears history buffers and resets debounce."""
        self._pos_history.clear()
        self.last_trigger_time = 0.0
        self.last_gesture = GestureType.NONE
