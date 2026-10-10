"""Command router for classifying user intent.

Bypasses LLM for deterministic fast commands, identifies web-dependent queries,
asks for clarification on ambiguous requests, and routes complex reasoning to the local model.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple


class RouteType(Enum):
    """Categorization of user input."""
    TERMINAL_COMMAND = auto()  # REPL commands (help, exit, clear, status)
    FAST_COMMAND = auto()      # Fast system/tool actions (open app, lock, volume)
    CLARIFY = auto()           # Ambiguous command requiring user clarification
    WEB_DEPENDENT = auto()     # Needs real-time external info (weather, news)
    AI_REQUEST = auto()        # General reasoning/knowledge handled by LLM


class ExecutionStatus(Enum):
    """Status of tool execution following execution contract."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class ToolExecutionResult:
    """Structured internal result separating classification from execution."""
    tool_name: str
    target: str = ""
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    message: str = ""
    error: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class RouteResult:
    """Result returned by the command router."""
    route_type: RouteType
    action: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""
    normalized_input: str = ""
    description: str = ""
    confidence: float = 1.0

    @property
    def route(self) -> str:
        """Returns standard route classification matching contract: DIRECT, LLM, CLARIFY, TERMINAL, WEB."""
        if self.route_type == RouteType.FAST_COMMAND:
            return "DIRECT"
        elif self.route_type == RouteType.AI_REQUEST:
            return "LLM"
        elif self.route_type == RouteType.CLARIFY:
            return "CLARIFY"
        elif self.route_type == RouteType.TERMINAL_COMMAND:
            return "TERMINAL"
        elif self.route_type == RouteType.WEB_DEPENDENT:
            return "WEB"
        return "UNKNOWN"

    @property
    def intent(self) -> Optional[str]:
        """Alias for action matching execution contract."""
        return self.action


def normalize_command_text(user_input: str) -> str:
    """Normalizes input text for consistent, deterministic intent classification.

    Handles:
    - Leading/trailing quotation marks and sentence punctuation.
    - Wake word, salutation, and courtesy prefixes ("Hey Jarvis", "Tolong", "Please").
    - Trailing colloquial particles and courtesy suffixes ("dong", "ya", "deh", "lah", "please", "now").
    - Indonesian colloquial verb morphology ("bukain" -> "buka", "tutupin" -> "tutup").
    """
    if not user_input:
        return ""

    s = user_input.strip()

    # 1. Strip quotation marks
    s = re.sub(r'^[«»"\'“”‘’]+|[«»"\'“”‘’]+$', '', s).strip()

    # 2. Strip trailing sentence punctuation
    s = re.sub(r'[\.\?!,;:]+$', '', s).strip()

    low = s.lower()

    # 3. Strip wake word & salutation prefixes
    low = re.sub(
        r'^(?:(?:hey|hi|hello|ok|halo|hai|baik|tolong|coba|bisa|silakan|tolongin)[,:]?\s*)*(?:jarvis|service|travis|harvis|charvis)?\s*[,:]?\s*(?:(?:please|tolong|sekarang|coba|silakan|tolongin)[,:]?\s*)*',
        '',
        low,
    ).strip()

    # 4. Strip trailing courtesy words, particles, and temporal adverbs (iterative)
    particle_pat = r'\s+(?:dong(?:\s+ya)?|ya(?:\s+dong)?|deh|lah|sih|nih|kan|sekarang|dulu|sebentar|please|now|right\s+now|for\s+me)$'
    for _ in range(3):
        m = re.search(particle_pat, low)
        if m:
            low = low[:m.start()].strip()
        else:
            break

    # 5. Normalize colloquial verb morphology
    low = re.sub(r'\bbukain\b', 'buka', low)
    low = re.sub(r'\btutupin\b', 'tutup', low)
    low = re.sub(r'\bmatiin\b', 'matikan', low)
    low = re.sub(r'\bnyalain\b', 'nyalakan', low)
    low = re.sub(r'\bjalanin\b', 'jalankan', low)

    # 6. Normalize internal multiple spaces
    low = re.sub(r'\s+', ' ', low).strip()

    return low


def clean_target_identifier(raw_target: str) -> str:
    """Extracts and cleans the canonical target app or website name from raw target phrasing."""
    if not raw_target:
        return ""

    t = raw_target.strip().lower()

    # Strip surrounding quotes and punctuation
    t = re.sub(r'^[«»"\'“”‘’]+|[«»"\'“”‘’]+$', '', t).strip()
    t = re.sub(r'[\.\?!,;:]+$', '', t).strip()

    # Strip leading descriptors (including 'browser', 'peramban', 'the')
    t = re.sub(r"^(?:the\s+)?(?:aplikasi|program|software|situs|website|web|laman|peramban|browser|tab|halaman)\s+", "", t)
    # Strip trailing descriptors
    t = re.sub(r"\s+(?:the\s+)?(?:app|aplikasi|program|software|site|website|web|laman|peramban|browser)$", "", t)

    # Strip compound descriptor wrappers
    t = re.sub(r"^the\s+", "", t)
    t = re.sub(r"^browser\s+", "", t)
    t = re.sub(r"\s+browser$", "", t)

    # Strip trailing particles if any leaked into target
    t = re.sub(r'\s+(?:dong(?:\s+ya)?|ya(?:\s+dong)?|deh|lah|sih|nih|kan|sekarang|dulu|sebentar|please|now|for\s+me)$', '', t)

    return t.strip()


class CommandRouter:
    """Routes user input to the optimal processing path."""

    # Terminal REPL built-in commands
    _TERMINAL_COMMANDS = {
        "exit": "exit",
        "quit": "exit",
        "/exit": "exit",
        "/quit": "exit",
        ":q": "exit",
        "help": "help",
        "/help": "help",
        "?": "help",
        "clear": "clear",
        "/clear": "clear",
        "cls": "clear",
        "status": "status",
        "/status": "status",
        "voice": "toggle_voice",
        "/voice": "toggle_voice",
        "ptt": "toggle_voice",
        "/ptt": "toggle_voice",
        "tts": "toggle_tts",
        "/tts": "toggle_tts",
        "wake": "toggle_wake",
        "/wake": "toggle_wake",
        "wakeword": "toggle_wake",
        "/wakeword": "toggle_wake",
        "mic": "list_devices",
        "/mic": "list_devices",
        "devices": "list_devices",
        "/devices": "list_devices",
    }

    # Deterministic system patterns (time, date, battery, screenshot, lock, volume)
    _SYSTEM_PATTERNS = [
        # System Time & Date
        (
            r"^(?:(?:tell\s+me\s+)?(?:the\s+)?time|what(?:'s|\s+is)?(?:\s+the)?\s+time(?:\s+is\s+it)?(?:\s+now)?|"
            r"current\s+time|time\s+now|"
            r"jam\s+berapa(?:\s+(?:sekarang|ini))?|sekarang\s+jam\s+berapa|"
            r"pukul\s+berapa(?:\s+(?:sekarang|ini))?|sekarang\s+pukul\s+berapa|"
            r"waktu(?:\s+sekarang)?)$",
            "get_time",
        ),
        (
            r"^(?:(?:tell\s+me\s+)?(?:the\s+)?date|what(?:'s|\s+is)?(?:\s+(?:today(?:'s)?|the))?\s+date(?:\s+today)?|"
            r"what\s+day\s+is\s+it(?:\s+today)?|current\s+date|today(?:'s)?\s+date|"
            r"tanggal\s+berapa(?:\s+hari\s+ini)?|hari\s+apa(?:\s+(?:sekarang|hari\s+ini))?|hari\s+ini\s+hari\s+apa)$",
            "get_date",
        ),
        # System & Battery Specs
        (r"^(?:system\s+(?:info|information|specs|status)|pc\s+info|info\s+sistem)$", "system_info"),
        (r"^(?:battery(?:\s+status|\s+level|\s+percentage)?|power\s+status|status\s+baterai)$", "battery_status"),
        # Screen & Audio control
        (r"^(?:(?:take|capture)\s+(?:a\s+)?screenshot|(?:ambil\s+)?tangkapan\s+layar|screenshot)$", "take_screenshot"),
        (r"^(?:(?:increase|raise|turn up)\s+(?:the\s+)?volume|(?:naikkan|besarkan)\s+volume)$", "volume_up"),
        (r"^(?:(?:decrease|lower|turn down)\s+(?:the\s+)?volume|(?:turunkan|kecilkan)\s+volume)$", "volume_down"),
        (r"^(?:(?:mute|unmute)\s+(?:the\s+)?(?:volume|sound|audio)|senyap(?:kan)?)$", "toggle_mute"),
        (r"^(?:(?:lock|secure)\s+(?:the\s+)?(?:computer|pc|screen|windows)|kunci\s+(?:layar|komputer|pc))$", "lock_screen"),
    ]

    # Web-dependent query patterns
    _WEB_PATTERNS = [
        r"\b(?:weather|temperature|forecast|cuaca|prakiraan\s+cuaca)\b",
        r"\b(?:latest news|breaking news|today'?s news|berita\s+terbaru|kabar\s+terkini)\b",
        r"\b(?:stock price|market price|crypto price|bitcoin price|harga\s+saham|harga\s+kripto)\b",
        r"\b(?:who won today|match score|game score|live score|skor\s+pertandingan)\b",
        r"\b(?:what happened today|today in history|peristiwa\s+hari\s+ini)\b",
    ]

    # Conversational markers: Prevent deterministic commands from triggering on inquiries or negations
    _CONVERSATIONAL_MARKERS = [
        r"\b(?:jangan|don'?t|do not|tidak usah|batal(?:kan)?|never|tidak boleh|stop)\b",
        r"\b(?:bagaimana(?:\s+cara)?|cara(?:\s+kerja|\s+buka|\s+menggunakan)?|how\s+to|how\s+do\s+i)\b",
        r"\b(?:kenapa|mengapa|why|apakah|perbedaan|difference|compare|versus|vs|definisi|definition)\b",
        r"\b(?:jelaskan|explain|ceritakan|tell\s+me\s+about|tell\s+me\s+(?!the\s+time|the\s+date|the\s+day|time|date))\b",
        r"\b(?:kalau|jika|if|seandainya)\b",
        r"\b(?:apa\s+itu|siapa\s+itu|who\s+is|what\s+is\s+(?!today|the\s+date|the\s+time|time|current|the\s+day))\b",
    ]

    def route(self, user_input: str) -> RouteResult:
        """Determines the appropriate routing for the given user input."""
        cleaned = user_input.strip()
        lower = cleaned.lower()

        # 1. Check Terminal Built-in Commands
        if lower in self._TERMINAL_COMMANDS:
            action = self._TERMINAL_COMMANDS[lower]
            return RouteResult(
                route_type=RouteType.TERMINAL_COMMAND,
                action=action,
                raw_input=cleaned,
                normalized_input=lower,
                description=f"Terminal command: {action}",
            )

        # Check language selection commands (/lang id, /lang en, /lang auto)
        if lower.startswith(("/lang", "lang ")):
            parts = lower.split()
            lang_val = parts[1].strip() if len(parts) > 1 else "toggle"
            return RouteResult(
                route_type=RouteType.TERMINAL_COMMAND,
                action="set_language",
                args={"language": lang_val},
                raw_input=cleaned,
                normalized_input=lower,
                description=f"Set language: {lang_val}",
            )

        # Normalize input consistently
        normalized = normalize_command_text(cleaned)

        # Check for conversational inquiry markers (questions, explanations, negations)
        is_conversational_inquiry = any(re.search(pat, lower) for pat in self._CONVERSATIONAL_MARKERS)

        # 2. Check Deterministic Fast Commands if not a conversational inquiry
        if not is_conversational_inquiry:
            # Check fixed system patterns (time, date, battery, lock, screenshot, volume)
            for pattern, action in self._SYSTEM_PATTERNS:
                if re.search(pattern, normalized):
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action=action,
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: {action}",
                    )

            # Check Application and Website Launch:
            # Matches: open, launch, start, run, buka, jalankan, nyalakan
            open_match = re.match(
                r"^(?:open|launch|start|run|buka|jalankan|nyalakan)(?:\s+(.*))?$",
                normalized,
            )
            if open_match:
                raw_arg = open_match.group(1) or ""
                cleaned_target = clean_target_identifier(raw_arg)

                # Case A: Ambiguous launch command with no target (e.g. "Open", "Buka")
                if not cleaned_target:
                    return RouteResult(
                        route_type=RouteType.CLARIFY,
                        action="clarify_open",
                        args={"raw_input": cleaned},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description="Ambiguous open command: target required",
                    )

                # Case B: Website or Web Service (YouTube, Google, Gmail, direct URLs, domains)
                from app.tools.browser import is_known_website, website_registry
                if is_known_website(cleaned_target):
                    canonical_site = website_registry.resolve_canonical_name(cleaned_target)
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="open_website",
                        args={"target": canonical_site, "raw_target": raw_arg.strip()},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: open_website ({canonical_site})",
                    )

                # Case C: Windows Application (Chrome, Edge, WhatsApp, Notepad, Calculator, etc.)
                from app.tools.apps import registry, find_application_executable, normalize_app_name
                canonical_app = normalize_app_name(cleaned_target)
                is_contextual_ref = cleaned_target in ("it", "aplikasinya", "programnya", "the app", "yang tadi", "aplikasi tadi")
                app_def = registry.get(canonical_app)

                is_valid_app = (
                    app_def is not None
                    or is_contextual_ref
                    or (find_application_executable(canonical_app) is not None)
                )

                if is_valid_app:
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="open_application",
                        args={"target": canonical_app, "raw_target": raw_arg.strip()},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: open_application ({canonical_app})",
                    )

            # Check Application Termination:
            # Matches: close, quit, exit, kill, terminate, stop, tutup, matikan, hentikan
            close_match = re.match(
                r"^(?:close|quit|exit|kill|terminate|stop|tutup|matikan|hentikan)(?:\s+(.*))?$",
                normalized,
            )
            if close_match:
                raw_arg = close_match.group(1) or ""
                cleaned_target = clean_target_identifier(raw_arg)

                # Case A: Ambiguous close command with no target (e.g. "Close", "Tutup")
                if not cleaned_target:
                    return RouteResult(
                        route_type=RouteType.CLARIFY,
                        action="clarify_close",
                        args={"raw_input": cleaned},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description="Ambiguous close command: target required",
                    )

                from app.tools.apps import registry, normalize_app_name
                canonical_app = normalize_app_name(cleaned_target)
                is_contextual_ref = cleaned_target in ("it", "aplikasinya", "programnya", "the app", "yang tadi", "aplikasi tadi")
                app_def = registry.get(canonical_app)

                if app_def is not None or is_contextual_ref:
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="close_application",
                        args={"target": canonical_app if not is_contextual_ref else cleaned_target, "raw_target": raw_arg.strip()},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: close_application ({canonical_app})",
                    )

        # 3. Check Web-dependent queries
        for pattern in self._WEB_PATTERNS:
            if re.search(pattern, lower):
                return RouteResult(
                    route_type=RouteType.WEB_DEPENDENT,
                    action="search_web",
                    args={"query": cleaned},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description="Web-dependent query requiring current data",
                )

        # 4. Default: AI Request (handled by local LLM)
        return RouteResult(
            route_type=RouteType.AI_REQUEST,
            action="llm_chat",
            args={"prompt": cleaned},
            raw_input=cleaned,
            normalized_input=normalized,
            description="AI reasoning request",
        )
