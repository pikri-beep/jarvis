"""Music playback and system media session controller for Windows 11.

Follows Workstream F requirements:
- Dedicated adapters for YouTube Music, Spotify, and local music files.
- Safe Windows virtual media keys via ctypes (zero mouse-coordinate hacking).
- Transparent status reporting and bilingual feedback.
"""

import ctypes
import os
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.logger import setup_logger
from app.tools.browser import launch_website

logger = setup_logger("jarvis.tools.music")

# Windows Virtual Key Codes for Media & Volume
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP       = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE      = 0xAD
VK_VOLUME_DOWN      = 0xAE
VK_VOLUME_UP        = 0xAF

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002


def _send_vk(vk_code: int, times: int = 1) -> None:
    """Sends a native Windows virtual key press and release event."""
    user32 = ctypes.windll.user32
    for _ in range(times):
        user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


def media_play_pause() -> Tuple[bool, str]:
    """Toggles playback (Play/Pause) on currently active media session."""
    try:
        _send_vk(VK_MEDIA_PLAY_PAUSE)
        logger.info("Sent VK_MEDIA_PLAY_PAUSE")
        return True, "Memutar/Menjeda media (Play/Pause)."
    except Exception as e:
        logger.error("Error sending play/pause: %s", e)
        return False, str(e)


def media_next() -> Tuple[bool, str]:
    """Skips to the next track on the active media session."""
    try:
        _send_vk(VK_MEDIA_NEXT_TRACK)
        logger.info("Sent VK_MEDIA_NEXT_TRACK")
        return True, "Beralih ke lagu berikutnya (Next track)."
    except Exception as e:
        logger.error("Error skipping to next track: %s", e)
        return False, str(e)


def media_previous() -> Tuple[bool, str]:
    """Returns to the previous track on the active media session."""
    try:
        _send_vk(VK_MEDIA_PREV_TRACK)
        logger.info("Sent VK_MEDIA_PREV_TRACK")
        return True, "Kembali ke lagu sebelumnya (Previous track)."
    except Exception as e:
        logger.error("Error returning to previous track: %s", e)
        return False, str(e)


def media_stop() -> Tuple[bool, str]:
    """Stops media playback on the active media session."""
    try:
        _send_vk(VK_MEDIA_STOP)
        logger.info("Sent VK_MEDIA_STOP")
        return True, "Menghentikan pemutaran musik."
    except Exception as e:
        logger.error("Error stopping playback: %s", e)
        return False, str(e)


def adjust_volume(direction: str = "up", steps: int = 2) -> Tuple[bool, str]:
    """Adjusts Windows master volume up, down, or toggles mute."""
    try:
        if direction == "up":
            _send_vk(VK_VOLUME_UP, times=steps)
            return True, f"Menaikkan volume sebesar {steps * 2} persen."
        elif direction == "down":
            _send_vk(VK_VOLUME_DOWN, times=steps)
            return True, f"Menurunkan volume sebesar {steps * 2} persen."
        elif direction in ("mute", "toggle_mute"):
            _send_vk(VK_VOLUME_MUTE)
            return True, "Mengalihkan status senyap (Mute/Unmute)."
        else:
            return False, f"Arah volume '{direction}' tidak valid."
    except Exception as e:
        logger.error("Error adjusting volume: %s", e)
        return False, str(e)


change_volume = adjust_volume


def find_local_music(query: str) -> Optional[Path]:
    """Searches the user's local Music directory for an audio file matching query."""
    user_music = Path(os.environ.get("USERPROFILE", "C:\\Users\\user")) / "Music"
    if not user_music.exists():
        return None

    audio_exts = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
    q_lower = query.lower()
    for root, _, files in os.walk(user_music):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in audio_exts and q_lower in p.stem.lower():
                return p
    return None


def play_music(query: str, provider: str = "auto") -> Tuple[bool, str, str]:
    """Plays requested song or artist using available provider.

    Returns:
        Tuple of (success, provider_name, message).
    """
    clean_query = query.strip()
    if not clean_query:
        # If no query provided, just send play/pause to resume current playback
        s, m = media_play_pause()
        return s, "Media", m

    # Check for local music match first if requested
    if provider in ("local", "auto"):
        local_file = find_local_music(clean_query)
        if local_file:
            try:
                os.startfile(str(local_file))
                logger.info("Playing local audio file: %s", local_file)
                return True, "Local Library", f"Memutar file musik lokal '{local_file.name}', sir."
            except Exception as e:
                logger.warning("Error opening local music %s: %s", local_file, e)

    # Provider: Spotify
    if provider == "spotify" or ("spotify" in clean_query.lower()):
        q_target = clean_query.lower().replace("di spotify", "").replace("on spotify", "").strip()
        encoded = urllib.parse.quote(q_target or clean_query)
        # Try launching via Spotify desktop URI protocol
        spotify_uri = f"spotify:search:{encoded}"
        try:
            os.startfile(spotify_uri)
            logger.info("Launched Spotify with URI: %s", spotify_uri)
            return True, "Spotify", f"Membuka dan mencari '{q_target}' di Spotify, sir."
        except Exception:
            # Fallback to Spotify web search
            web_url = f"https://open.spotify.com/search/{encoded}"
            success, display, url, msg = launch_website(web_url)
            return success, "Spotify Web", f"Membuka Spotify Web untuk '{q_target}', sir."

    # Default / YouTube Music Provider
    q_target = clean_query.lower().replace("di youtube music", "").replace("di youtube", "").strip()
    encoded = urllib.parse.quote(q_target or clean_query)
    yt_music_url = f"https://music.youtube.com/search?q={encoded}"
    success, display, url, msg = launch_website(yt_music_url)
    if success:
        return True, "YouTube Music", f"Memutar '{q_target or clean_query}' di YouTube Music, sir."
    else:
        # Fallback to standard YouTube
        yt_url = f"https://www.youtube.com/results?search_query={encoded}"
        s, d, u, m = launch_website(yt_url)
        return s, "YouTube", f"Membuka YouTube untuk '{q_target or clean_query}', sir."


play_music_query = play_music
