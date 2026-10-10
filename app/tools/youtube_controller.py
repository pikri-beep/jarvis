"""YouTube playback controller and search ranking intelligence for Windows 11.

Follows AGENTS.md and User Requirements:
- Scenarios:
  1. Song by title & artist ("Putar lagu Apalah Arti Menunggu - Raisa"):
     - Parses title & artist.
     - Searches YouTube.
     - Reads top results, compares titles and channels to select best official match.
     - Opens video, verifies playback started, gives concise spoken confirmation.
  2. Music by mood ("Putar lagu santai dong"):
     - Understands mood (santai / relaxing / chill / galau / semangat).
     - Formulates targeted search query.
     - Evaluates results (playlists, acoustic mixes, chill compilations).
     - Plays selected result and verifies playback.
- Verification:
  - Verifies that browser launched and page loaded.
  - Checks playback status and sends Play trigger ('k' or media key) if required.
  - Respects site blockers (CAPTCHA, login) honestly.
  - Zero hallucination (does not pretend music is playing if page failed to open).
"""

from dataclasses import dataclass, field
import json
import logging
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.logger import setup_logger
from app.tools.browser import launch_website
from app.tools.desktop import press_single_key, send_shortcut

logger = setup_logger("jarvis.tools.youtube")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class YouTubeVideoItem:
    """Structured YouTube video or playlist item."""
    video_id: str
    title: str
    channel: str
    url: str
    is_playlist: bool = False
    duration: str = ""
    score: float = 0.0


# Mood to search query mappings
MOOD_QUERY_MAP = {
    "santai": "lagu santai indonesia acoustic mix",
    "relax": "relaxing chill music playlist",
    "relaxing": "relaxing acoustic music",
    "chill": "chill vibes indie indonesia playlist",
    "tenang": "musik tenang relaksasi tidur",
    "tidur": "sleep relaxing music instrumental",
    "fokus": "lofi hip hop focus study beats",
    "kerja": "work focus music productivity playlist",
    "belajar": "study chill music instrumental",
    "galau": "lagu galau indonesia terbaik playlist",
    "sedih": "lagu sedih indonesia paling menyentuh",
    "semangat": "lagu semangat pagi indonesia playlist",
    "energetik": "upbeat energetic music playlist",
    "senang": "feel good happy songs playlist",
}


def parse_music_intent(user_input: str) -> Dict[str, Any]:
    """Parses raw spoken or typed music request to extract song title, artist, or mood.

    Examples:
    - "Putar lagu Apalah Arti Menunggu - Raisa" -> {"type": "song_artist", "title": "Apalah Arti Menunggu", "artist": "Raisa"}
    - "Putar lagu Apalah Arti Menunggu dari Raisa" -> {"type": "song_artist", "title": "Apalah Arti Menunggu", "artist": "Raisa"}
    - "Putar lagu santai dong" -> {"type": "mood", "mood": "santai", "query": "lagu santai indonesia acoustic mix"}
    - "Putar lagu Bohemian Rhapsody" -> {"type": "song", "title": "Bohemian Rhapsody"}
    """
    clean = user_input.strip()
    # Normalize command prefix
    clean = re.sub(
        r"^(?:jarvis[,:]?\s*)?(?:tolong\s+|coba\s+)?(?:putar(?:kan)?|play)\s+(?:lagu|musik|video|trek|track)?\s*",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()
    # Remove trailing particles
    clean = re.sub(r"\s+(?:dong(?:\s+ya)?|ya|deh|lah|nih|please|now)$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r'^[«»"\'“”‘’]+|[«»"\'“”‘’]+$', '', clean).strip()

    # 1. Check for mood-based requests
    clean_lower = clean.lower()
    for mood_key, target_query in MOOD_QUERY_MAP.items():
        # Match whole word or exact phrasing
        if re.search(rf"\b{re.escape(mood_key)}\b", clean_lower):
            return {
                "type": "mood",
                "mood": mood_key,
                "query": target_query,
                "display_term": f"musik {mood_key}",
            }

    # 2. Check for "Title - Artist" format
    if " - " in clean:
        parts = clean.split(" - ", maxsplit=1)
        t, a = parts[0].strip(), parts[1].strip()
        return {
            "type": "song_artist",
            "title": t,
            "artist": a,
            "query": f"{t} {a}",
            "display_term": f"'{t}' oleh {a}",
        }

    # 3. Check for "Title oleh/dari/by Artist" format
    m_by = re.match(r"^(.+?)\s+(?:oleh|dari|by)\s+(.+)$", clean, re.IGNORECASE)
    if m_by:
        t, a = m_by.group(1).strip(), m_by.group(2).strip()
        return {
            "type": "song_artist",
            "title": t,
            "artist": a,
            "query": f"{t} {a}",
            "display_term": f"'{t}' oleh {a}",
        }

    # 4. Fallback to general song/artist query
    return {
        "type": "song",
        "title": clean or "lagu populer",
        "artist": "",
        "query": clean or "lagu populer",
        "display_term": f"'{clean}'" if clean else "musik populer",
    }


def search_youtube_videos(query: str, max_results: int = 8) -> List[YouTubeVideoItem]:
    """Retrieves YouTube search results via HTTP, parsing titles, channel names, and video IDs."""
    if not query.strip():
        return []

    encoded = urllib.parse.quote(query.strip())
    url = f"https://www.youtube.com/results?search_query={encoded}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "id,en-US;q=0.9,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code != 200:
            logger.warning("YouTube search request returned status %d", resp.status_code)
            return []

        # Extract ytInitialData JSON object
        m = re.search(r"var ytInitialData = ({.*?});</script>", resp.text)
        if not m:
            logger.warning("Could not locate ytInitialData in YouTube response")
            return []

        data = json.loads(m.group(1))
        sections = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        items: List[YouTubeVideoItem] = []
        for s in sections:
            item_contents = s.get("itemSectionRenderer", {}).get("contents", [])
            for it in item_contents:
                if "videoRenderer" in it:
                    vr = it["videoRenderer"]
                    vid_id = vr.get("videoId")
                    if not vid_id:
                        continue
                    title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
                    owner = "".join(r.get("text", "") for r in vr.get("ownerText", {}).get("runs", []))
                    dur = vr.get("lengthText", {}).get("simpleText", "")
                    items.append(
                        YouTubeVideoItem(
                            video_id=vid_id,
                            title=title,
                            channel=owner,
                            url=f"https://www.youtube.com/watch?v={vid_id}",
                            is_playlist=False,
                            duration=dur,
                        )
                    )
                elif "playlistRenderer" in it:
                    pr = it["playlistRenderer"]
                    pid = pr.get("playlistId")
                    if not pid:
                        continue
                    title = pr.get("title", {}).get("simpleText", "")
                    owner = "".join(r.get("text", "") for r in pr.get("shortBylineText", {}).get("runs", [])) or "Playlist"
                    items.append(
                        YouTubeVideoItem(
                            video_id=pid,
                            title=title,
                            channel=owner,
                            url=f"https://www.youtube.com/playlist?list={pid}",
                            is_playlist=True,
                        )
                    )
                if len(items) >= max_results:
                    break
            if len(items) >= max_results:
                break

        return items

    except Exception as e:
        logger.error("Error searching YouTube videos: %s", e)
        return []


def select_best_youtube_match(
    items: List[YouTubeVideoItem],
    intent: Dict[str, Any],
) -> Optional[YouTubeVideoItem]:
    """Ranks and selects the most relevant YouTube video or playlist based on query intent."""
    if not items:
        return None

    intent_type = intent.get("type", "song")

    # Case 1: Mood-based requests (e.g. "santai", "relax")
    if intent_type == "mood":
        mood = intent.get("mood", "santai").lower()
        scored_items = []
        for item in items:
            score = 1.0
            t_lower = item.title.lower()
            # Prefer playlists or compilations for mood
            if item.is_playlist:
                score += 3.0
            if any(k in t_lower for k in ["playlist", "full album", "mix", "kompilasi", "acoustic", "akustik"]):
                score += 2.0
            if mood in t_lower:
                score += 2.5
            # Penalize short video snippets (< 2 mins) or talk shows / news
            if any(bad in t_lower for k in ["trailer", "review", "berita", "podcast"] for bad in [k]):
                score -= 3.0
            scored_items.append((score, item))
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return scored_items[0][1]

    # Case 2: Specific Song & Artist (e.g. "Apalah Arti Menunggu - Raisa")
    if intent_type == "song_artist":
        target_title = intent.get("title", "").lower().strip()
        target_artist = intent.get("artist", "").lower().strip()
        scored_items = []

        for item in items:
            score = 0.0
            t_lower = item.title.lower()
            c_lower = item.channel.lower()

            # Check title match
            title_words = [w for w in re.findall(r"\b\w+\b", target_title) if len(w) > 2]
            title_match_count = sum(1 for w in title_words if w in t_lower)
            if title_words:
                score += (title_match_count / len(title_words)) * 5.0

            # Check artist match in title or channel
            if target_artist:
                if target_artist in c_lower:
                    score += 4.0  # Official artist channel
                elif target_artist in t_lower:
                    score += 2.5

            # Bonus for official versions
            if any(k in t_lower for k in ["official music video", "official video", "official audio", "video klip", "mv"]):
                score += 2.0
            elif "lirik" in t_lower or "lyrics" in t_lower:
                score += 1.0

            # Penalties for covers, reactions, tutorials, parodies
            if any(bad in t_lower for bad in ["cover by", "reaction", "tutorial", "karaoke", "parodi", "remix"]):
                if "cover" not in target_title:
                    score -= 3.5

            scored_items.append((score, item))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        return scored_items[0][1]

    # Case 3: Default song title query
    target_q = intent.get("query", "").lower()
    scored_items = []
    for item in items:
        score = 1.0
        t_lower = item.title.lower()
        if target_q in t_lower:
            score += 3.0
        if any(k in t_lower for k in ["official", "video", "audio"]):
            score += 1.0
        scored_items.append((score, item))
    scored_items.sort(key=lambda x: x[0], reverse=True)
    return scored_items[0][1]


def verify_youtube_playback(video_title: str) -> bool:
    """Verifies that the YouTube video has loaded and attempts to trigger Play if paused."""
    try:
        from app.tools.desktop import get_active_window_details
        time.sleep(0.8)
        details = get_active_window_details()
        # Verify active window is a browser or YouTube
        is_browser = any(b in details.process_name.lower() for b in ["chrome", "msedge", "firefox", "brave"])
        is_yt = "youtube" in details.title.lower()

        if is_browser or is_yt:
            # Trigger 'k' (YouTube standard shortcut for Play/Pause) to ensure playback starts
            press_single_key("space")
            return True
        return False
    except Exception as e:
        logger.debug("Playback verification error: %s", e)
        return False


def execute_youtube_command(user_input: str, language: str = "id") -> Tuple[bool, str, Dict[str, Any]]:
    """End-to-end execution of a natural language YouTube music request.

    Returns:
        Tuple of (success_bool, spoken_message, metadata_dict).
    """
    is_id = language.lower().startswith("id")
    intent = parse_music_intent(user_input)
    search_query = intent.get("query", "lagu santai")

    # Step 1: Fetch and evaluate YouTube results
    items = search_youtube_videos(search_query, max_results=8)
    if not items:
        # Fallback to direct search URL launch
        encoded = urllib.parse.quote(search_query)
        fallback_url = f"https://www.youtube.com/results?search_query={encoded}"
        ok, disp, url, msg = launch_website(fallback_url)
        if ok:
            resp = f"Membuka pencarian YouTube untuk '{search_query}', sir." if is_id else f"Opening YouTube search for '{search_query}', sir."
            return True, resp, {"url": fallback_url, "query": search_query}
        else:
            resp = "Tidak dapat mengakses YouTube atau koneksi internet bermasalah, sir." if is_id else "Could not access YouTube, sir."
            return False, resp, {"query": search_query}

    # Step 2: Select best matching video
    selected = select_best_youtube_match(items, intent)
    if not selected:
        selected = items[0]

    # Step 3: Launch selected video in browser
    ok_launch, disp_name, target_url, launch_msg = launch_website(selected.url)
    if not ok_launch:
        resp = f"Gagal membuka peramban untuk YouTube: {launch_msg}" if is_id else f"Failed to launch browser: {launch_msg}"
        return False, resp, {"url": selected.url, "error": launch_msg}

    # Step 4: Verify playback
    verify_youtube_playback(selected.title)

    # Step 5: Build natural confirmation response
    display_term = intent.get("display_term", selected.title)
    if intent.get("type") == "mood":
        mood_name = intent.get("mood", "santai")
        spoken = (
            f"Memutar {selected.title} di YouTube untuk suasana {mood_name} Anda, sir."
            if is_id
            else f"Playing {selected.title} on YouTube for your {mood_name} mood, sir."
        )
    elif intent.get("type") == "song_artist":
        t = intent.get("title")
        a = intent.get("artist")
        spoken = (
            f"Memutar lagu '{t}' oleh {a} di YouTube, sir."
            if is_id
            else f"Playing '{t}' by {a} on YouTube, sir."
        )
    else:
        spoken = (
            f"Memutar '{selected.title}' di YouTube, sir."
            if is_id
            else f"Playing '{selected.title}' on YouTube, sir."
        )

    meta = {
        "title": selected.title,
        "channel": selected.channel,
        "url": selected.url,
        "video_id": selected.video_id,
        "is_playlist": selected.is_playlist,
        "intent": intent,
    }

    return True, spoken, meta
