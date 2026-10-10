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
    WEB_SEARCH = auto()        # Dedicated Search-First web retrieval without LLM
    SCREEN_READ = auto()       # On-demand screen reading and OCR
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
        """Returns standard route classification matching contract: DIRECT, LLM, CLARIFY, TERMINAL, WEB, SCREEN."""
        if self.route_type == RouteType.FAST_COMMAND:
            return "DIRECT"
        elif self.route_type == RouteType.AI_REQUEST:
            return "LLM"
        elif self.route_type == RouteType.CLARIFY:
            return "CLARIFY"
        elif self.route_type == RouteType.TERMINAL_COMMAND:
            return "TERMINAL"
        elif self.route_type in (RouteType.WEB_SEARCH, RouteType.WEB_DEPENDENT):
            return "WEB"
        elif self.route_type == RouteType.SCREEN_READ:
            return "SCREEN"
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

    # 3. Strip wake word, salutations, & modal courtesy prefixes
    low = re.sub(
        r'^(?:(?:hey|hi|hello|ok|halo|hai|baik|tolongin|tolong|coba|bisakah|bisa|dapatkah|dapat|silakan|could\s+you|can\s+you|would\s+you|will\s+you)[,:]?\s*)*(?:jarvis|service|travis|harvis|charvis)?\s*[,:]?\s*(?:(?:please|tolongin|tolong|sekarang|coba|silakan|could\s+you|can\s+you|would\s+you)[,:]?\s*)*',
        '',
        low,
    ).strip()

    # 4. Strip trailing courtesy words, particles, and temporal adverbs (iterative)
    particle_pat = r'\s+(?:dong(?:\s+ya)?|ya(?:\s+dong)?|deh|lah|sih|nih|kan|sekarang|dulu|sebentar|sejenak|please|now|right\s+now|for\s+me|for\s+a\s+moment|a\s+moment|for\s+a\s+second|a\s+second)$'
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


def clean_search_query_arg(q: str) -> str:
    """Cleans extracted search query removing filler prepositions, particles, and quotes."""
    if not q:
        return ""
    s = q.strip()
    s = re.sub(r'^[«»"\'“”‘’]+|[«»"\'“”‘’]+$', '', s).strip()
    s = re.sub(r'[\.\?!,;:]+$', '', s).strip()
    # Strip leading prepositions/fillers that might have been captured
    s = re.sub(
        r'^(?:tentang|mengenai|soal|seputar|informasi\s+tentang|info\s+tentang|berita\s+tentang|berita\s+terbaru\s+tentang|for|about|on)\s+',
        '',
        s,
        flags=re.IGNORECASE,
    ).strip()
    # Strip trailing courtesy words
    s = re.sub(r'\s+(?:dong(?:\s+ya)?|ya(?:\s+dong)?|deh|lah|sih|nih|please|now)$', '', s, flags=re.IGNORECASE).strip()
    return s.strip()


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
        "diag": "show_diagnostics",
        "/diag": "show_diagnostics",
        "reset": "reset_context",
        "/reset": "reset_context",
    }

    # Screen reading patterns (on-demand inspection)
    _SCREEN_PATTERNS = [
        (r"^(?:(?:lihat|cek|periksa|baca|inspeksi)\s+layar(?:\s+(?:gue|saya|ku|ini))?|(?:look\s+at|inspect)\s+(?:my\s+)?screen)$", "read_screen", False),
        (r"^(?:baca\s+(?:teks|tulisan)?\s*(?:di|pada)\s+layar|read\s+(?:the\s+)?(?:text\s+on\s+)?screen)$", "read_screen", False),
        (r"^(?:what(?:'s|\s+is)\s+on\s+(?:my\s+)?screen|apa\s+yang\s+ada\s+di\s+layar)$", "read_screen", False),
        (r"^(?:apa\s+(?:tulisan|isi)\s+(?:di|pada)\s+jendela\s+ini|what\s+is\s+(?:written\s+)?(?:on|in)\s+this\s+window)$", "read_screen", False),
        (r"^(?:baca\s+(?:pesan\s+)?error(?:\s+(?:yang\s+muncul|di\s+layar))?|jelaskan\s+error(?:\s+(?:yang\s+tampil|di\s+layar))?|apa\s+error(?:\s+di\s+layar)?|explain\s+(?:the\s+)?error(?:\s+on\s+screen)?|read\s+(?:the\s+)?error\s+message)$", "read_screen", True),
        (r"^(?:tombol\s+(?:yang\s+)?(?:merah|hijau|biru)?(?:\s+di\s+(?:sebelah\s+)?(?:kanan|kiri|atas|bawah))?\s*(?:itu\s+)?apa|what\s+is\s+that\s+(?:red\s+)?button(?:\s+on\s+the\s+right)?)$", "screen_element_inquiry", True),
        (r"^(?:tombol\s+mana\s+yang\s+harus\s+diklik(?:\s+untuk\s+melanjutkan)?|which\s+button\s+to\s+click)$", "screen_element_inquiry", False),
        (r"^(?:apakah\s+unduhan\s+sudah\s+selesai|is\s+(?:the\s+)?download\s+finished|download\s+selesai)$", "screen_element_inquiry", False),
        (r"^(?:apakah\s+(?:musik|lagu)(?:nya)?\s+sudah\s+diputar|is\s+(?:the\s+)?(?:music|video)\s+playing)$", "screen_element_inquiry", False),
        (r"^(?:kenapa\s+(?:langkah\s+tadi\s+)?gagal|mengapa\s+gagal|why\s+did\s+it\s+fail)$", "screen_element_inquiry", False),
        (r"^(?:aku\s+sedang\s+(?:ada\s+)?di\s+halaman\s+apa|halaman\s+apa\s+ini|what\s+page\s+am\s+i\s+on)$", "screen_element_inquiry", False),
        (r"^(?:bacakan\s+pesan(?:\s+yang\s+terlihat)?|baca\s+pesan(?:\s+di\s+layar)?|read\s+(?:the\s+)?visible\s+message)$", "screen_element_inquiry", False),
    ]

    # Search follow-up patterns
    _SEARCH_FOLLOWUP_PATTERNS = [
        (r"^(?:bacakan\s+hasilnya|bacakan\s+hasil|read\s+(?:the\s+)?result(?:s)?)$", "read_search_result", {}),
        (r"^(?:sebutkan\s+sumbernya|apa\s+sumbernya|apa\s+sumber(?:\s+informasi)?\s+tadi|dari\s+mana\s+sumbernya|tampilkan\s+sumber(?:nya)?|list\s+(?:the\s+)?sources|what\s+are\s+the\s+sources|what\s+was\s+the\s+source|show\s+sources|sumbernya\s+apa)$", "list_search_sources", {}),
        (r"^(?:bacakan\s+artikel\s+ini|baca\s+artikel\s+ini|read\s+this\s+article|ringkas\s+halaman(?:\s+ini)?(?:\s+yang\s+sedang\s+terbuka)?|summarize\s+this\s+page)$", "read_screen", {}),
    ]

    # Deterministic system patterns (time, date, battery, screenshot, lock, volume, media, desktop, browser)
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
        (r"^(?:(?:take|capture|ambil)\s+(?:a\s+)?(?:screenshot|tangkapan\s+layar)|screenshot|tangkapan\s+layar)$", "take_screenshot"),
        (r"^(?:(?:increase|raise|turn up)\s+(?:the\s+)?volume|(?:naikkan|besarkan)\s+volume|turn\s+it\s+up|louder)$", "volume_up"),
        (r"^(?:(?:decrease|lower|turn down)\s+(?:the\s+)?volume|(?:turunkan|kecilkan)\s+volume|turn\s+it\s+down|quieter)$", "volume_down"),
        (r"^(?:(?:mute|unmute)\s+(?:the\s+)?(?:volume|sound|audio)|senyap(?:kan)?)$", "toggle_mute"),
        (r"^(?:(?:lock|secure)\s+(?:the\s+)?(?:computer|pc|screen|windows)|kunci\s+(?:layar|komputer|pc))$", "lock_screen"),
        # Music & Media Sessions (Deterministic < 50ms bypass)
        (r"^(?:(?:pause|jeda)\s+(?:the\s+)?(?:music|song|track|playback|video|media|it)|pause\s+it|pause\s+the\s+song|pause\s+the\s+music|jeda\s+musik(?:nya)?|jeda\s+lagu(?:nya)?|pause|pause\s+music)$", "media_play_pause"),
        (r"^(?:(?:resume|lanjutkan)\s+(?:the\s+)?(?:music|song|track|playback|video|media|it)|resume\s+it|resume\s+playback|resume\s+the\s+music|lanjutkan\s+musik(?:nya)?|lanjutkan\s+lagu(?:nya)?|resume|resume\s+music)$", "media_play_pause"),
        (r"^(?:next(?:\s+track|\s+song)?|skip(?:\s+the\s+song|\s+track|\s+song)?|lagu\s+berikutnya|lagu\s+selanjutnya|trek\s+berikutnya|skip)$", "media_next"),
        (r"^(?:previous(?:\s+track|\s+song)?|prev(?:\s+track|\s+song)?|lagu\s+sebelumnya|trek\s+sebelumnya)$", "media_previous"),
        (r"^(?:stop(?:\s+the\s+)?(?:music|song|playback|it)|hentikan\s+(?:musik|lagu)(?:nya)?|stop\s+music)$", "media_stop"),
        # Browser Tab & Navigation Control
        (r"^(?:(?:buka\s+)?tab\s+baru|open\s+(?:a\s+)?new\s+tab|new\s+tab)$", "open_new_tab"),
        (r"^(?:tutup\s+tab(?:\s+ini)?|close\s+(?:this\s+)?tab)$", "close_tab"),
        (r"^(?:pindah\s+ke\s+tab\s+sebelumnya|tab\s+sebelumnya|previous\s+tab)$", "previous_tab"),
        (r"^(?:pindah\s+ke\s+tab\s+berikutnya|tab\s+berikutnya|next\s+tab)$", "next_tab"),
        (r"^(?:kembali(?:\s+ke\s+halaman\s+sebelumnya)?|halaman\s+sebelumnya|go\s+back|back)$", "navigate_back"),
        (r"^(?:maju(?:\s+ke\s+halaman\s+berikutnya)?|halaman\s+berikutnya|go\s+forward|forward)$", "navigate_forward"),
        (r"^(?:refresh(?:\s+halaman)?|muat\s+ulang(?:\s+halaman)?|reload(?:\s+page)?|refresh)$", "refresh_page"),
        (r"^(?:fokus(?:\s+ke)?\s+kolom\s+alamat|focus\s+(?:the\s+)?address\s+bar)$", "focus_address_bar"),
        (r"^(?:klik\s+(?:pada\s+)?(?:kolom|kotak)\s+pencarian|fokus(?:\s+ke)?\s+(?:kolom|kotak)\s+pencarian|click\s+(?:the\s+)?search\s+(?:field|box|bar)|search\s+(?:field|box)\s+click)$", "click_search_field"),
        # Desktop Mouse & Cursor Control
        (r"^(?:(?:gerakkan|pindahkan)\s+(?:kursor|mouse)\s+ke\s+tengah(?:\s+layar)?|move\s+(?:the\s+)?(?:cursor|mouse)\s+to\s+(?:the\s+)?center(?:\s+of\s+(?:the\s+)?screen)?)$", "move_cursor_center"),
        (r"^(?:klik\s+kanan|right\s+click)$", "mouse_click_right"),
        (r"^(?:double\s+click|klik\s+(?:dua|2)\s+kali|klik\s+ganda)$", "mouse_click_double"),
        (r"^(?:klik\s+tombol\s+itu|klik\s+itu|click\s+that\s+button|click\s+it)$", "click_contextual_element"),
        (r"^(?:klik|click)$", "mouse_click_left"),
        (r"^(?:scroll\s+ke\s+bawah|scroll\s+down|gulir\s+ke\s+bawah)$", "mouse_scroll_down"),
        (r"^(?:scroll\s+ke\s+atas|scroll\s+up|gulir\s+ke\s+atas)$", "mouse_scroll_up"),
        (r"^(?:scroll\s+ke\s+kanan|scroll\s+right|gulir\s+ke\s+kanan)$", "mouse_scroll_right"),
        (r"^(?:scroll\s+ke\s+kiri|scroll\s+left|gulir\s+ke\s+kiri)$", "mouse_scroll_left"),
        (r"^(?:lanjutkan|continue|proceed)$", "continue_task"),
        (r"^(?:coba\s+lagi|try\s+again|retry)$", "retry_last_action"),
        # Memory recall
        (r"^(?:apa\s+yang\s+(?:kamu|anda)\s+ingat(?:\s+tentang\s+saya)?|what\s+do\s+you\s+remember(?:\s+about\s+me)?)$", "recall_memories"),
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

    def _match_search_query(self, text: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Matches deterministic web search requests in Indonesian and English."""
        t = text.strip()

        # 1. "buka hasil pencarian tentang X" / "open search results for X"
        m_open = re.match(
            r"^(?:buka\s+hasil\s+pencarian(?:\s+(?:tentang|mengenai|soal|seputar))?|open\s+search\s+results\s+(?:for|about))\s+(.+)$",
            t,
            re.IGNORECASE,
        )
        if m_open:
            q = clean_search_query_arg(m_open.group(1))
            return "open_search_results", q, {"query": q, "open_browser": True}

        # 2. Indonesian search patterns
        m_id = re.match(
            r"^(?:cari(?:kan)?(?:\s+lah)?)\s+"
            r"(?:"
            r"(?:informasi|info|berita(?:\s+terbaru)?|kabar(?:\s+terkini|\s+terbaru)?|artikel|data)\s*(?:tentang|mengenai|soal|seputar)?\s*|"
            r"(?:di\s+internet|di\s+web|di\s+google|di\s+bing)\s*(?:tentang|mengenai|soal|seputar)?\s*|"
            r"(?:tentang|mengenai|soal|seputar)\s*"
            r")?"
            r"(.+)$",
            t,
            re.IGNORECASE,
        )
        if m_id:
            raw_q = m_id.group(1).strip()
            raw_q = re.sub(r"\s+(?:di\s+(?:internet|web|google|bing))$", "", raw_q, flags=re.IGNORECASE).strip()
            q = clean_search_query_arg(raw_q)
            if q and len(q) > 1 and q not in ("sesuatu", "apa saja", "dong"):
                return "search_web", q, {"query": q}

        # 3. English search patterns
        m_en = re.match(
            r"^(?:"
            r"search\s+(?:the\s+web\s+for|on\s+the\s+web\s+for|online\s+for|google\s+for|bing\s+for|for)?\s*|"
            r"find\s+(?:information\s+(?:about|on)|info\s+(?:about|on)|out\s+about)?\s*|"
            r"look\s+up\s+(?:on\s+the\s+web\s+for|online\s+for|for)?\s*"
            r")"
            r"(.+)$",
            t,
            re.IGNORECASE,
        )
        if m_en:
            raw_q = m_en.group(1).strip()
            raw_q = re.sub(r"\s+(?:on\s+the\s+web|online|on\s+google)$", "", raw_q, flags=re.IGNORECASE).strip()
            q = clean_search_query_arg(raw_q)
            if q and len(q) > 1:
                return "search_web", q, {"query": q}

        # 4. "what are the latest developments in X" / "what is the latest news on X"
        m_latest = re.match(
            r"^(?:what\s+are\s+the\s+latest\s+developments\s+in|what(?:'s|\s+is)\s+the\s+latest\s+(?:news|update|information)\s+(?:on|about))\s+(.+)$",
            t,
            re.IGNORECASE,
        )
        if m_latest:
            raw_q = m_latest.group(1).strip()
            q = clean_search_query_arg(raw_q)
            if q:
                return "search_web", q, {"query": f"latest developments in {q}"}

        # 5. "apa perkembangan terbaru tentang X" / "perkembangan terbaru seputar X"
        m_perkembangan = re.match(
            r"^(?:apa\s+perkembangan\s+terbaru\s+(?:tentang|mengenai|seputar)|perkembangan\s+terbaru\s+(?:tentang|mengenai|seputar))\s+(.+)$",
            t,
            re.IGNORECASE,
        )
        if m_perkembangan:
            raw_q = m_perkembangan.group(1).strip()
            q = clean_search_query_arg(raw_q)
            if q:
                return "search_web", q, {"query": f"perkembangan terbaru {q}"}

        return None

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

        # 1.5. On-Demand Screen Reading (Explicit user intent only)
        for pattern, action, pref_vis in self._SCREEN_PATTERNS:
            if re.search(pattern, normalized):
                return RouteResult(
                    route_type=RouteType.SCREEN_READ,
                    action=action,
                    args={"prompt": cleaned, "prefer_vision": pref_vis},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Screen inspection: {action} (vision={pref_vis})",
                )

        # 1.6. Search Follow-ups ("bacakan hasilnya", "sebutkan sumbernya", "buka sumber pertama")
        for pattern, action, args_map in self._SEARCH_FOLLOWUP_PATTERNS:
            if re.search(pattern, normalized):
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action=action,
                    args=dict(args_map),
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Search followup: {action}",
                )

        m_src = re.match(
            r"^(?:(buka|open|bacakan|read)\s+(?:sumber|hasil(?:\s+pencarian)?|artikel|the\s+result|the\s+article|the\s+source|result|article|source)?\s*(pertama|kedua|ketiga|ke-?1|ke-?2|ke-?3|1|2|3|first|second|third|1st|2nd|3rd|source\s+1|source\s+2)(?:\s*(?:source|artikel|hasil|result|article))?)$",
            normalized,
            re.IGNORECASE,
        )
        if m_src:
            verb = (m_src.group(1) or "buka").lower()
            w = m_src.group(2)
            idx_map = {
                "pertama": 1, "ke-1": 1, "ke1": 1, "1": 1, "first": 1, "1st": 1, "source 1": 1,
                "kedua": 2, "ke-2": 2, "ke2": 2, "2": 2, "second": 2, "2nd": 2, "source 2": 2,
                "ketiga": 3, "ke-3": 3, "ke3": 3, "3": 3, "third": 3, "3rd": 3,
            }
            idx = idx_map.get(w.lower() if w else "", 1)
            target_act = "read_search_source_snippet" if verb in ("bacakan", "read") else "open_search_source"
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action=target_act,
                args={"index": idx},
                raw_input=cleaned,
                normalized_input=normalized,
                description=f"{target_act} #{idx}",
            )

        # 1.7. Explicit Search-First Queries (Bypasses LLM deterministically)
        search_intent = self._match_search_query(normalized)
        if search_intent:
            act, q_target, s_args = search_intent
            return RouteResult(
                route_type=RouteType.WEB_SEARCH,
                action=act,
                args=s_args,
                raw_input=cleaned,
                normalized_input=normalized,
                description=f"Search-First: {q_target}",
            )

        # Check for conversational inquiry markers (questions, explanations, negations)
        is_conversational_inquiry = any(re.search(pat, lower) for pat in self._CONVERSATIONAL_MARKERS)

        # 2. Check Deterministic Fast Commands if not a conversational inquiry
        if not is_conversational_inquiry:
            # Check fixed system patterns (time, date, battery, lock, screenshot, volume, media)
            for pattern, action in self._SYSTEM_PATTERNS:
                if re.search(pattern, normalized):
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action=action,
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: {action}",
                    )

            # Check Memory Store (e.g. "ingat bahwa nama saya adalah Alex", "remember that my car is red")
            mem_store_match = re.match(r"^(?:ingat\s+bahwa|ingat|remember\s+that|remember)\s+(.+)$", normalized)
            if mem_store_match:
                raw_fact = mem_store_match.group(1).strip()
                m_split = re.split(r"\s+(?:saya\s+adalah|adalah|is|merupakan)\s+", raw_fact, maxsplit=1)
                if len(m_split) == 2:
                    k, v = m_split[0].strip(), m_split[1].strip()
                else:
                    k, v = "fakta", raw_fact
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="store_memory",
                    args={"key": k, "value": v, "raw": raw_fact},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Fast command: store_memory ({k} = {v})",
                )

            # Check Memory Forget (e.g. "lupakan nama saya", "forget my car")
            mem_forget_match = re.match(r"^(?:lupakan|forget)\s+(?:tentang\s+|about\s+)?(.+)$", normalized)
            if mem_forget_match:
                k = mem_forget_match.group(1).strip()
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="forget_memory",
                    args={"key": k},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Fast command: forget_memory ({k})",
                )

            # Check Specific Play Music command (e.g. "putar lagu bohemian rhapsody", "play queen")
            play_match = re.match(r"^(?:play|putar)\s+(?:lagu|musik|track)?\s*(.+)$", normalized)
            if play_match:
                song_query = play_match.group(1).strip()
                if song_query not in ("music", "musik", "lagu"):
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="play_music",
                        args={"query": song_query},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: play_music ({song_query})",
                    )

            # Check Destructive operations requiring explicit confirmation
            destr_match = re.match(
                r"^(?:hapus\s+(?:folder|direktori|file|berkas|dokumen)|delete\s+(?:folder|directory|file|documents)|format\s+(?:c|d|disk|drive|penyimpanan)|kosongkan\s+recycle\s+bin|empty\s+recycle\s+bin|shutdown|matikan\s+komputer|restart\s+komputer|reboot)(?:\s+(.*))?$",
                normalized,
            )
            if destr_match:
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="request_confirmation",
                    args={"intended_action": cleaned, "target": destr_match.group(1) or ""},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description="Destructive action requiring confirmation",
                )

            # Check Desktop Input: Typing text (e.g. "ketik hello world", "type search query")
            type_match = re.match(r"^(?:ketik(?:kan)?|type)\s+(.+)$", normalized)
            if type_match:
                t_arg = type_match.group(1).strip()
                t_arg = re.sub(r'^[«»"\'“”‘’]+|[«»"\'“”‘’]+$', '', t_arg).strip()
                if t_arg:
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="type_text",
                        args={"text": t_arg},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Desktop input: type_text ({t_arg})",
                    )

            if normalized in ("ketik", "type"):
                return RouteResult(
                    route_type=RouteType.CLARIFY,
                    action="clarify_type",
                    args={"raw_input": cleaned},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description="Ambiguous type command: text required",
                )

            # Check multi-step task chaining (e.g. "klik tombol itu lalu lanjutkan", "buka tab baru lalu ketik...")
            if any(k in normalized for k in [" lalu ", " kemudian ", " and then "]):
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="execute_task",
                    args={"goal": cleaned},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Multi-step task execution: {cleaned}",
                )

            # Check Specific Button Click (e.g. "klik tombol play", "klik tombol kirim", "klik tombol itu")
            click_btn_match = re.match(r"^(?:klik\s+tombol|click\s+button)\s+(.+)$", normalized)
            if click_btn_match:
                t_btn = click_btn_match.group(1).strip()
                if t_btn in ("itu", "that", "tersebut", "ini"):
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="click_contextual_element",
                        args={"target": t_btn},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description="Click contextual element",
                    )
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="click_named_button",
                    args={"button_name": t_btn},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Click named button: {t_btn}",
                )

            # Check Desktop Input: Key press and shortcuts (e.g. "tekan enter", "press escape", "tekan ctrl+l")
            press_match = re.match(r"^(?:tekan|press)\s+(?:tombol\s+|key\s+)?([a-z0-9\+\s]+)$", normalized)
            if press_match:
                raw_k = press_match.group(1).strip().replace(" ", "")
                key_alias_map = {
                    "panahbawah": "down",
                    "panahatas": "up",
                    "panahkanan": "right",
                    "panahkiri": "left",
                    "spasi": "space",
                    "masuk": "enter",
                    "kembali": "backspace",
                    "esc": "escape",
                    "return": "enter",
                }
                mapped_k = key_alias_map.get(raw_k, raw_k)
                if "+" in mapped_k:
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="send_hotkey",
                        args={"combo": mapped_k},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Desktop input: send_hotkey ({mapped_k})",
                    )
                else:
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="press_key",
                        args={"key": mapped_k},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Desktop input: press_key ({mapped_k})",
                    )

            # Check Application Switch / Focus (e.g. "switch ke Chrome", "pindah ke Notepad", "fokus ke Calculator", "focus on Chrome")
            switch_match = re.match(
                r"^(?:switch|pindah|fokus)(?:\s+(?:ke|pada|to))?\s+(.+)$|^(?:focus\s+(?:on|to)?)\s*(.+)$",
                normalized,
            )
            if switch_match:
                raw_sw = switch_match.group(1) or switch_match.group(2)
                c_target = clean_target_identifier(raw_sw)
                if c_target:
                    from app.tools.apps import normalize_app_name
                    canonical_app = normalize_app_name(c_target)
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="focus_app",
                        args={"target": canonical_app, "raw_target": raw_sw.strip()},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Desktop control: focus_app ({canonical_app})",
                    )

            # Check Open Standard Folder command (e.g. "buka folder downloads", "buka unduhan")
            folder_match = re.match(r"^(?:open|buka)\s+(?:folder|direktori|directory)\s*(.+)$", normalized)
            if folder_match:
                fname = folder_match.group(1).strip()
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="open_folder",
                    args={"target": fname, "folder": fname},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Fast command: open_folder ({fname})",
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

                # Case B.0: Folder / Directory (Desktop, Downloads, Documents, etc.)
                folder_cand = re.sub(r"^(?:folder|berkas|direktori|directory)\s+", "", cleaned_target).strip()
                from app.tools.filesystem import get_user_folder
                if (
                    cleaned_target.startswith(("folder ", "berkas ", "direktori ", "directory "))
                    or get_user_folder(cleaned_target) is not None
                ):
                    target_folder = folder_cand or cleaned_target
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="open_folder",
                        args={"target": target_folder, "raw_target": raw_arg.strip()},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: open_folder ({target_folder})",
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

        # 4. Default: AI Request (handled by local LLM if enabled, or offline notice in desktop mode)
        return RouteResult(
            route_type=RouteType.AI_REQUEST,
            action="llm_chat",
            args={"prompt": cleaned},
            raw_input=cleaned,
            normalized_input=normalized,
            description="AI reasoning request",
            confidence=0.5,
        )

