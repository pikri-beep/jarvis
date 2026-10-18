"""Vision Manager coordinating webcam capture, face presence, and hand gesture recognition."""

import threading
import time
from typing import Any, Callable, Optional

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger
from app.vision.gesture_detector import GestureDetector, GestureEvent, GestureType
from app.vision.presence_detector import PresenceDetector, PresenceEvent, PresenceEventType

logger = setup_logger("jarvis.vision.manager")


class VisionManager:
    """Coordinates webcam frame grabbing, face presence tracking, and hand gestures."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        on_presence_event: Optional[Callable[[PresenceEvent], None]] = None,
        on_gesture_event: Optional[Callable[[GestureEvent], None]] = None,
        on_status_change: Optional[Callable[[bool], None]] = None,
    ):
        self.settings = settings or get_settings()
        self.on_presence_event = on_presence_event
        self.on_gesture_event = on_gesture_event
        self.on_status_change = on_status_change

        self.presence_detector = PresenceDetector(
            autolock_seconds=getattr(self.settings, "vision_autolock_seconds", 90),
            return_greeting_threshold=60.0,
            warning_lead_seconds=10.0,
        )
        self.gesture_detector = GestureDetector(debounce_seconds=1.2)

        self._camera_index = getattr(self.settings, "vision_camera_index", 0)
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cap: Any = None
        self._media_active_provider: Optional[Callable[[], bool]] = None

    def set_media_active_provider(self, provider: Callable[[], bool]) -> None:
        """Sets a callable that reports whether audio/video media is currently active."""
        self._media_active_provider = provider

    def is_running(self) -> bool:
        """Returns True if the webcam background loop is active."""
        return self._is_running

    def start(self) -> bool:
        """Starts the background vision processing thread."""
        if self._is_running:
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="JarvisVisionThread", daemon=True)
        self._is_running = True
        self._thread.start()
        logger.info("VisionManager started background capture loop on camera %d", self._camera_index)
        if self.on_status_change:
            try:
                self.on_status_change(True)
            except Exception as e:
                logger.debug("Error in on_status_change callback: %s", e)
        return True

    def stop(self) -> None:
        """Stops the vision thread and releases the webcam device."""
        if not self._is_running:
            return

        self._stop_event.set()
        self._is_running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._release_camera()
        logger.info("VisionManager stopped and camera released.")
        if self.on_status_change:
            try:
                self.on_status_change(False)
            except Exception as e:
                logger.debug("Error in on_status_change callback: %s", e)

    def toggle(self) -> bool:
        """Toggles the vision monitoring on or off."""
        if self._is_running:
            self.stop()
            return False
        else:
            self.start()
            return True

    def _release_camera(self) -> None:
        """Releases the cv2 VideoCapture hardware device."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug("Error releasing camera: %s", e)
            self._cap = None

    def _is_media_playing(self) -> bool:
        """Determines whether media gesture recognition should be active."""
        if self._media_active_provider:
            try:
                return bool(self._media_active_provider())
            except Exception:
                pass

        # Heuristic check for common media players running on Windows
        try:
            import psutil
            media_procs = {"spotify.exe", "vlc.exe", "wmplayer.exe", "music.ui.exe"}
            for p in psutil.process_iter(attrs=["name"]):
                if p.info["name"] and p.info["name"].lower() in media_procs:
                    return True
        except Exception:
            pass
        return False

    def _run_loop(self) -> None:
        """Main camera acquisition and inference loop."""
        try:
            import cv2
            import mediapipe as mp
        except ImportError as e:
            logger.error("Vision dependencies missing (%s). Vision loop cannot run.", e)
            self._is_running = False
            return

        # Initialize MediaPipe detectors (optimized for CPU)
        mp_face = mp.solutions.face_detection
        mp_hands = mp.solutions.hands

        face_detector = None
        hands_detector = None

        try:
            face_detector = mp_face.FaceDetection(min_detection_confidence=0.5, model_selection=0)
            hands_detector = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            )
        except Exception as e:
            logger.error("Failed to initialize MediaPipe models: %s", e)
            self._is_running = False
            return

        # Open camera
        try:
            self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                # Fallback to default backend
                self._cap = cv2.VideoCapture(self._camera_index)
        except Exception as e:
            logger.error("Failed to open camera index %d: %s", self._camera_index, e)
            self._is_running = False
            return

        if not self._cap.isOpened():
            logger.warning("Camera index %d is not available or in use by another app.", self._camera_index)
            self._is_running = False
            return

        # Configure low capture resolution for maximum speed and minimum power consumption
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        last_face_check_time = 0.0

        try:
            while not self._stop_event.is_set():
                now = time.time()
                is_media_active = self._is_media_playing()

                # Read frame
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    time.sleep(0.5)
                    continue

                # Mirror frame for natural interaction
                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 1. Face Presence Checking (every 0.8s ~ 1.25 FPS to save battery)
                if now - last_face_check_time >= 0.8:
                    last_face_check_time = now
                    try:
                        face_res = face_detector.process(rgb_frame)
                        has_face = bool(face_res and face_res.detections)
                    except Exception as e:
                        logger.debug("Face detection process error: %s", e)
                        has_face = False

                    pres_evt = self.presence_detector.update(has_face, current_time=now)
                    if pres_evt and self.on_presence_event:
                        try:
                            self.on_presence_event(pres_evt)
                        except Exception as e:
                            logger.error("Error in on_presence_event callback: %s", e)

                # 2. Hand Gesture Detection (ONLY when media is actively playing)
                if is_media_active:
                    try:
                        hand_res = hands_detector.process(rgb_frame)
                        if hand_res and hand_res.multi_hand_landmarks:
                            landmarks = hand_res.multi_hand_landmarks[0].landmark
                            gest_evt = self.gesture_detector.process_hand_landmarks(landmarks, current_time=now)
                            if gest_evt and self.on_gesture_event:
                                try:
                                    self.on_gesture_event(gest_evt)
                                except Exception as e:
                                    logger.error("Error in on_gesture_event callback: %s", e)
                    except Exception as e:
                        logger.debug("Hand gesture process error: %s", e)

                    # Dynamic sleep when media is active (~12 FPS)
                    time.sleep(0.08)
                else:
                    # Power-saving sleep when no media is playing (~1.5 FPS)
                    time.sleep(0.6)

        except Exception as e:
            logger.error("Unexpected error in vision processing loop: %s", e)
        finally:
            self._release_camera()
            if face_detector:
                try:
                    face_detector.close()
                except Exception:
                    pass
            if hands_detector:
                try:
                    hands_detector.close()
                except Exception:
                    pass
            self._is_running = False
