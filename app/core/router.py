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

    # 2.5. Remove stray mid-utterance punctuation from STT early, preserving colons in times (e.g. '14:20')
    low = re.sub(r'(?<!\d):|:(?!\d)|[,;]+', ' ', low)

    # 3. Strip wake word, salutations, & modal courtesy prefixes
    low = re.sub(
        r'^(?:(?:hey|hi|hello|ok|oke|halo|hai|baik|iya|ya|tolongin|tolong|coba|bisakah|bisa|dapatkah|dapat|silakan|could\s+you|can\s+you|would\s+you|will\s+you)[,:]?\s*)*(?:jarvis|jarpis|service|travis|harvis|charvis)?\s*[,:]?\s*(?:(?:please|tolongin|tolong|sekarang|coba|silakan|could\s+you|can\s+you|would\s+you)[,:]?\s*)*',
        '',
        low,
    ).strip()

    # 4. Strip trailing courtesy words, particles, benefactive phrases, and temporal adverbs (iterative)
    particle_pat = (
        r'\s+(?:untuk\s+(?:ku|saya|aku|kita|kami|dia)|buat\s+(?:ku|saya|aku|kita|kami|dia)|bagi\s+(?:ku|saya|aku)|'
        r'untukku|buatku|untuksaya|buatsaya|for\s+(?:me|us|him|her)|'
        r'dong(?:\s+ya)?|ya(?:\s+dong)?|deh|lah|sih|nih|kan|sekarang|dulu|sebentar|sejenak|'
        r'please|now|right\s+now|for\s+a\s+moment|a\s+moment|for\s+a\s+second|a\s+second)$'
    )
    for _ in range(4):
        m = re.search(particle_pat, low)
        if m:
            low = low[:m.start()].strip()
        else:
            break

    # 5. Normalize colloquial verb morphology & common Indonesian STT phonetic confusions
    low = re.sub(r'\b(?:bukakan|bukain)\b', 'buka', low)
    low = re.sub(r'\b(?:tutupkan|tutupin)\b', 'tutup', low)
    low = re.sub(r'\bmatiin\b', 'matikan', low)
    low = re.sub(r'\bnyalain\b', 'nyalakan', low)
    low = re.sub(r'\b(?:jalankan|jalanin)\b', 'jalankan', low)
    low = re.sub(r'\b(?:charikan|cariin|carikan)\b', 'cari', low)
    low = re.sub(r'\bchari\b', 'cari', low)
    low = re.sub(r'\bchabesok\b', 'cuaca besok', low)
    low = re.sub(r'\bchaca\b', 'cuaca', low)
    low = re.sub(r'\bphutar(?:kan)?\b', 'putar', low)
    low = re.sub(r'\bputer(?:in|kan)?\b', 'putar', low)
    low = re.sub(r'\bputarin\b', 'putar', low)
    low = re.sub(r'\bputarkan\b', 'putar', low)
    low = re.sub(r'\bplaykan\b', 'play', low)
    low = re.sub(r'\bsetelin\b', 'setel', low)
    low = re.sub(r'\bmainin\b', 'mainkan', low)
    low = re.sub(r'\bopem\b', 'open', low)
    # Common command verb typos
    low = re.sub(r'\b(?:oen|opn|oepn|oppen|oepen|openn|opne)\b', 'open', low)
    low = re.sub(r'\b(?:bka|bukaa|bukak|bukka|buak|vuka|bkua)\b', 'buka', low)
    low = re.sub(r'\b(?:clsoe|clse|cloe|clos|klose|clsoed)\b', 'close', low)
    low = re.sub(r'\b(?:tutp|tutu|ttup|tutupp|tutuup|tutub)\b', 'tutup', low)
    low = re.sub(r'\b(?:paly|ply|plei|pley|playy)\b', 'play', low)
    low = re.sub(r'\b(?:putra|ptr|putarr|putaer)\b', 'putar', low)
    low = re.sub(r'\b(?:cri|carii|chari|serach|searh|searc)\b', 'cari', low)
    low = re.sub(r'\bbatrai\b', 'baterai', low)
    low = re.sub(r'\bbatre\b', 'baterai', low)
    low = re.sub(r'\bbatere\b', 'baterai', low)
    # Music & song phonetic corrections (e.g. "play clip", "putar grip", "grip by run")
    low = re.sub(r'\b(?:play|putar|setel|mainkan)\s+(?:lagu\s+|musik\s+)?(?:grip|clip|kripp?|crip|kripik)\b', 'play creep', low)
    low = re.sub(r'\blay\s+(?:creep|kripp|clip|grip)\b', 'play creep', low)
    low = re.sub(r'\b(?:grip|clip|krip)\s+(?:by|oleh|dari|buy)\s+(?:run|ran|radio\s*head|radio\s*hed|rediohead)\b', 'creep by radiohead', low)
    low = re.sub(r'\b(?:by|oleh|dari|buy)\s+(?:run|ran|radio\s*head|radio\s*hed|rediohead)\b', 'by radiohead', low)
    low = re.sub(r'\bradio\s*hed\b', 'radiohead', low)
    low = re.sub(r'\brediohead\b', 'radiohead', low)

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
    t = re.sub(r"^(?:the[\s_]+)?(?:aplikasi|program|software|situs|website|web|laman|peramban|browser|tab|halaman)[\s_]+", "", t)
    # Strip trailing descriptors
    t = re.sub(r"[\s_]+(?:the[\s_]+)?(?:app|aplikasi|program|software|site|website|web|laman|peramban|browser)$", "", t)

    # Strip compound descriptor wrappers
    t = re.sub(r"^the\s+", "", t)
    t = re.sub(r"^browser\s+", "", t)
    t = re.sub(r"\s+browser$", "", t)
    t = re.sub(r"\s+(?:di|in|pada)\s+(?:google\s+)?(?:chrome|krom|browser|peramban|edge)$", "", t)

    # Strip trailing particles and benefactive phrases if any leaked into target (iterative)
    target_particle_pat = (
        r'\s+(?:untuk\s+(?:ku|saya|aku|kita|kami|dia)|buat\s+(?:ku|saya|aku|kita|kami|dia)|bagi\s+(?:ku|saya|aku)|'
        r'untukku|buatku|untuksaya|buatsaya|for\s+(?:me|us|him|her)|'
        r'dong(?:\s+ya)?|ya(?:\s+dong)?|deh|lah|sih|nih|kan|sekarang|dulu|sebentar|please|now)$'
    )
    for _ in range(3):
        m = re.search(target_particle_pat, t, flags=re.IGNORECASE)
        if m:
            t = t[:m.start()].strip()
        else:
            break

    return t.strip()


def clean_search_query_arg(q: str) -> str:
    """Cleans extracted search query removing search command verbs, platform references, fillers, and quotes."""
    if not q:
        return ""
    s = q.strip()
    s = re.sub(r'^[«»"\'“”‘’]+|[«»"\'“”‘’]+$', '', s).strip()
    s = re.sub(r'[\.\?!,;:]+$', '', s).strip()

    # Iteratively strip leading command verbs and prepositions
    leading_verbs_pat = (
        r'^(?:(?:tolong\s+)?(?:search|cari(?:kan)?|googling|google|find|look\s+up)(?:\s+(?:di|in|on)\s+(?:google|internet|web|browser))?'
        r'(?:\s+(?:the\s+web\s+for|on\s+the\s+web\s+for|online\s+for|google\s+for|for|about|on))?\s*|'
        r'(?:tentang|mengenai|soal|seputar|informasi\s+tentang|info\s+tentang|berita\s+tentang|berita\s+terbaru\s+tentang|for|about|on)\s+)'
    )
    for _ in range(3):
        m = re.match(leading_verbs_pat, s, flags=re.IGNORECASE)
        if m:
            s = s[m.end():].strip()
        else:
            break

    # Strip trailing platform terms and courtesy words
    trailing_pat = (
        r'\s+(?:di\s+(?:google|internet|web|bing|browser)|in\s+google|on\s+google|lewat\s+google|on\s+the\s+web|online|'
        r'dong(?:\s+ya)?|ya(?:\s+dong)?|deh|lah|sih|nih|please|now)$'
    )
    for _ in range(3):
        m = re.search(trailing_pat, s, flags=re.IGNORECASE)
        if m:
            s = s[:m.start()].strip()
        else:
            break

    s = re.sub(r'^[«»"\'“”‘’]+|[«»"\'“”‘’]+$', '', s).strip()
    return s.strip()


def is_multi_step_or_implicit_intent(normalized: str, raw_input: str) -> bool:
    """Detects multi-step commands, complex goals, or implicit situation/error statements.

    Routes these to the Autonomous AI Agent Loop (AI_REQUEST) rather than forcing rigid
    single-step fast commands or failing with app_not_found.
    """
    low = normalized.lower().strip()

    # Exception: Contextual button chaining handled deterministically by TaskExecutor ("klik tombol ... lalu lanjutkan")
    if low.startswith("klik") and ("lalu lanjutkan" in low or "kemudian lanjutkan" in low):
        return False

    # 1. Multi-step conjunctions (e.g. 'lalu', 'kemudian', 'setelah itu', 'terus', 'sambil', 'dan lalu', 'and then', 'then')
    if re.search(r"\b(?:lalu|kemudian|setelah\s+itu|terus|sambil|dan\s+lalu|dan\s+kemudian)\b", low):
        return True
    if re.search(r"\b(?:and\s+then|then|after\s+that|followed\s+by)\b", low):
        return True

    # 2. Implicit user situation or open-ended goals (e.g. 'aku mau lanjut ngerjain tugas', 'mau belajar', 'mau kerja')
    if re.search(
        r"\b(?:aku|saya|gue|gw)?\s*mau\s+(?:lanjut\s+)?(?:ngerjain\s+tugas|kerja|belajar|ngoding|kuliah|tugas|bikin|buat\s+proyek)\b",
        low,
    ):
        return True
    if re.search(
        r"\b(?:i\s+want\s+to|i\s+need\s+to|let's)\s+(?:continue\s+)?(?:work|my\s+task|homework|study|coding)\b",
        low,
    ):
        return True

    # 3. Implicit screen error, glitch, or diagnostic statements (e.g. 'layarku kok error gini ya', 'layar error')
    if re.search(
        r"\b(?:layar(?:ku)?\s+(?:kok|kenapa|ada|lagi)?\s*error|error\s+(?:gini|ini|di\s+layar)|kok\s+error|kenapa\s+(?:layar|muncul\s+error)|ada\s+masalah\s+di\s+layar|screen\s+(?:error|glitch|freeze|issue)|why\s+is\s+my\s+screen|something\s+wrong\s+with\s+(?:my\s+)?screen)\b",
        low,
    ):
        return True

    return False


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
        "cheat": "cheatsheet",
        "/cheat": "cheatsheet",
        "cheatsheet": "cheatsheet",
        "/cheatsheet": "cheatsheet",
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
        (r"^(?:sebutkan\s+sumbernya|apa\s+sumbernya|apa\s+sumber(?:\s+informasi)?(?:\s+tadi)?|dari\s*mana\s+sumbernya|darimana\s+sumbernya|sumbernya\s+dari\s*mana|tampilkan\s+sumber(?:nya)?|list\s+(?:the\s+)?sources|what\s+are\s+the\s+sources|what\s+was\s+the\s+source|show\s+sources|sumbernya\s+apa)$", "list_search_sources", {}),
        (r"^(?:bacakan\s+artikel\s+ini|baca\s+artikel\s+ini|read\s+this\s+article|ringkas\s+halaman(?:\s+ini)?(?:\s+yang\s+sedang\s+terbuka)?|summarize\s+this\s+page)$", "read_screen", {}),
    ]

    # Deterministic system patterns (time, date, battery, screenshot, lock, volume, media, desktop, browser)
    _SYSTEM_PATTERNS = [
        # System Time & Date
        (
            r"^(?:(?:tell\s+me\s+)?(?:the\s+)?time|what(?:'s|\s+is)?(?:\s+the)?\s+time(?:\s+is\s+it)?(?:\s+now)?|"
            r"what\s+time(?:\s+is\s+it)?(?:\s+now)?.*|"
            r"current\s+time.*|time\s+now.*|"
            r"jam\s+berapa(?:\s+(?:sekarang|ini))?.*|sekarang\s+jam\s+berapa.*|"
            r"pukul\s+berapa(?:\s+(?:sekarang|ini))?.*|sekarang\s+pukul\s+berapa.*|"
            r"waktu(?:\s+sekarang)?.*)$",
            "get_time",
        ),
        (
            r"^(?:(?:tell\s+me\s+)?(?:the\s+)?date|what(?:'s|\s+is)?(?:\s+(?:today(?:'s)?|the))?\s+date.*|"
            r"what\s+date.*|"
            r"what\s+day\s+is\s+it.*|current\s+date.*|today(?:'s)?\s+date.*|"
            r"date\s+today.*|"
            r"tanggal\s+berapa(?:\s+(?:sekarang|hari\s+ini))?.*|hari\s+apa(?:\s+(?:sekarang|hari\s+ini))?.*|hari\s+ini\s+hari\s+apa.*)$",
            "get_date",
        ),
        # System & Battery Specs
        (
            r"^(?:(?:cek|lihat|tampilkan|periksa|check|show|view|get)\s+)?(?:info|informasi|spesifikasi|status|spek|specs|information)\s*(?:sistem|komputer|laptop|pc|system|device|perangkat)?$|"
            r"^(?:system\s+(?:info|information|specs|status)|pc\s+info|info\s+sistem|spesifikasi(?:\s+sistem)?|spek(?:\s+sistem)?|spek\s+laptop|spek\s+pc)$",
            "system_info",
        ),
        (r"^(?:(?:cek|lihat|periksa|berapa|status|sisa|info)\s+baterai(?:\s+(?:ku|saya|laptop|ini|sekarang))?|baterai(?:\s+(?:ku|saya|sekarang))?|battery(?:\s+(?:status|level|percentage|info|now))?|power\s+status|status\s+baterai|how\s+much\s+battery)$", "battery_status"),
        # Screen & Audio control
        (r"^(?:(?:take|capture|ambil)\s+(?:a\s+)?(?:screenshot|tangkapan\s+layar)(?:\s+(?:layar(?:ku|\s+ku)?|screen|my\s+screen))?|screenshot(?:\s+(?:layar(?:ku|\s+ku)?|screen|my\s+screen))?|tangkapan\s+layar(?:\s+(?:ku|saya))?)$", "take_screenshot"),
        (r"^(?:(?:increase|raise|turn up)\s+(?:the\s+)?volume|(?:naikkan|besarkan)\s+volume|turn\s+it\s+up|louder)$", "volume_up"),
        (r"^(?:(?:decrease|lower|turn down)\s+(?:the\s+)?volume|(?:turunkan|kecilkan)\s+volume|turn\s+it\s+down|quieter)$", "volume_down"),
        (r"^(?:(?:mute|unmute)\s+(?:the\s+)?(?:volume|sound|audio)|senyap(?:kan)?)$", "toggle_mute"),
        (r"^(?:(?:lock|secure)\s+(?:the|my)?\s*(?:computer|pc|screen|windows|laptop)|kunci\s+(?:layar|komputer|pc|laptop|windows)(?:\s+(?:saya|ku)|ku)?|lock\s+screen)$", "lock_screen"),
        # Music & Media Sessions (Deterministic < 50ms bypass)
        (r"^(?:(?:pause|jeda)\s+(?:the\s+)?(?:music|song|track|playback|video|media|lagu(?:nya)?|musik(?:nya)?|it)|pause\s+it|pause\s+the\s+song|pause\s+the\s+music|jeda\s+musik(?:nya)?|jeda\s+lagu(?:nya)?|pause\s+lagu(?:nya)?|pause|pause\s+music)$", "media_play_pause"),
        (r"^(?:(?:resume|lanjutkan)\s+(?:the\s+)?(?:music|song|track|playback|video|media|lagu(?:nya)?|musik(?:nya)?|it)|resume\s+it|resume\s+playback|resume\s+the\s+music|lanjutkan\s+musik(?:nya)?|lanjutkan\s+lagu(?:nya)?|resume\s+lagu(?:nya)?|resume|resume\s+music)$", "media_play_pause"),
        (r"^(?:next(?:\s+track|\s+song)?|skip(?:\s+the\s+song|\s+track|\s+song)?|lagu\s+berikutnya|lagu\s+selanjutnya|trek\s+berikutnya|skip)$", "media_next"),
        (r"^(?:stop(?:\s+the\s+)?(?:music|song|playback|it)|hentikan\s+(?:musik|lagu)(?:nya)?|stop\s+music)$", "media_stop"),
        (r"^(?:stop|berhenti|cukup|diam|cancel|batal|stop\s+bicara|jangan\s+bicara|berhenti\s+ngomong|stop\s+talking|shut\s+up|hush|silent)$", "stop_speech"),
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
        r"^(?:jangan|don'?t|do\s+not|tidak\s+usah|batal(?:kan)?|tidak\s+boleh)\s+",
        r"^(?:jangan|batal|cancel|stop)$",
        r"\b(?:bagaimana(?:\s+cara)?|cara(?:\s+kerja|\s+buka|\s+menggunakan)?|how\s+to|how\s+do\s+i|how\s+does)\b",
        r"\b(?:kenapa|mengapa|why|apakah|perbedaan|difference|compare|versus|vs|definisi|definition)\b",
        r"\b(?:jelaskan|explain|ceritakan|tell\s+me\s+about|tell\s+me\s+(?!the\s+time|the\s+date|the\s+day|time|date))\b",
        r"\b(?:kalau|jika|if|seandainya)\b",
        r"\b(?:apa\s+itu|siapa\s+itu|who\s+is|what\s+is\s+(?!today|the\s+date|the\s+time|time|current|the\s+day))\b",
        r"\b(?:what\s+(?:do|does|did|can|would|should|could|will|are|were))\b",
        r"\b(?:siapa|who|whose|whom)\b",
        r"\b(?:adalah|merupakan|artinya|maksudnya|is\s+a|is\s+an)\b",
        r"\b(?:saya\s+suka|aku\s+suka|i\s+like|i\s+love|i\s+prefer)\b",
        r"\b(?:diskusi|discussion|debate|debat|pintu|door)\b",
    ]

    def _match_search_query(self, text: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Matches deterministic web search requests in Indonesian and English."""
        t = text.strip()

        # 0. Trailing search engines: "<query> open in google", "<query> cari di google", "<query> di google"
        m_trail = re.match(
            r"^(.+?)\s+(?:(?:buka|open|search|cari)(?:\s+(?:di|in|on))?\s+google|(?:di|in|on)\s+google)$",
            t,
            re.IGNORECASE,
        )
        if m_trail:
            raw_q = m_trail.group(1).strip()
            q = clean_search_query_arg(raw_q)
            if q and len(q) > 1:
                return "search_web", q, {"query": q, "open_browser": True}

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
            r"^(?:cari(?:kan|in)?(?:\s+lah)?)\s+"
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

    def strip_wake_word(self, user_input: str) -> str:
        """Normalizes input and strips wake word prefixes and courtesy markers."""
        return normalize_command_text(user_input)

    def route(self, user_input: str) -> RouteResult:
        """Determines the appropriate routing for the given user input."""
        cleaned = user_input.strip()
        lower = cleaned.lower()

        # 0. Instant Greetings Fast Command (< 0.05s bypass, avoids 15s Ollama latency)
        # Matches: halo, hello, hi, hai, hey jarvis, halo jarvis, selamat pagi/siang/sore/malam, etc.
        m_greet = re.match(
            r"^(?:halo|hello|hi|hai|hey|hei|assalamu\s*alaikum)(?:\s+(?:jarvis|jarpis|there|semua|bro|sir))?[!\.\?]*$|"
            r"^(?:selamat\s+(?:pagi|siang|sore|malam)|good\s+(?:morning|afternoon|evening|day))(?:\s+(?:jarvis|jarpis|sir))?[!\.\?]*$|"
            r"^(?:apa\s+kabar|how\s+are\s+you|how\s+are\s+you\s+doing)(?:\s+(?:jarvis|jarpis|today))?[!\.\?]*$",
            cleaned,
            re.IGNORECASE,
        )
        if m_greet:
            is_kabar = bool(re.search(r"\b(?:kabar|how\s+are\s+you)\b", cleaned, re.IGNORECASE))
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="greeting_status" if is_kabar else "greeting",
                raw_input=cleaned,
                normalized_input=cleaned.lower(),
                description="Fast command: greeting",
                confidence=1.0,
            )

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

        # Check explicit vision task command (/vision <goal>)
        if lower.startswith(("/vision", "vision ")):
            v_goal = cleaned[7:].strip() if lower.startswith("/vision") else cleaned[6:].strip()
            if not v_goal:
                return RouteResult(
                    route_type=RouteType.CLARIFY,
                    action="clarify_vision",
                    raw_input=cleaned,
                    normalized_input=lower,
                    description="Vision task clarification required: goal missing",
                )
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="vision_task",
                args={"goal": v_goal},
                raw_input=cleaned,
                normalized_input=lower,
                description=f"Vision Agent task: {v_goal}",
            )

        # Normalize input consistently
        normalized = normalize_command_text(cleaned)

        # 1.1 Immediate Speech Interruption / Barge-In Fast Command
        if re.match(r"^(?:stop|berhenti|cukup|diam|cancel|batal|stop\s+bicara|jangan\s+bicara)$", normalized):
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="stop_speech",
                raw_input=cleaned,
                normalized_input=normalized,
                description="Fast command: stop_speech",
            )

        # 1.4. Natural Vision Agent Triggers ("lihat layar dan ...", "setel timer ...", "timer ...")
        m_vis_nl = re.match(
            r"^(?:lihat|cek|periksa|baca|inspeksi)\s+layar\s+(?:dan|lalu|kemudian)\s+(.+)$|^(?:look\s+at\s+screen\s+and\s+)(.+)$",
            normalized,
        )
        if m_vis_nl:
            v_goal = (m_vis_nl.group(1) or m_vis_nl.group(2)).strip()
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="vision_task",
                args={"goal": v_goal},
                raw_input=cleaned,
                normalized_input=normalized,
                description=f"Vision Agent natural task: {v_goal}",
            )

        m_timer = re.match(r"^(?:setel|pasang|buat|set|atur|hidupkan)\s+timer(?:\s+(.*))?$|^timer(?:\s+(.*))?$", normalized)
        if m_timer:
            t_arg = (m_timer.group(1) or m_timer.group(2) or "").strip()
            t_full_goal = f"setel timer {t_arg}".strip() if t_arg else "setel timer"
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="vision_task",
                args={"goal": t_full_goal},
                raw_input=cleaned,
                normalized_input=normalized,
                description=f"Vision Agent Timer: {t_full_goal}",
            )

        # PocketDesk Remote Control (e.g. "nyalakan remote", "aktifkan remote server", "matikan remote", "status remote", "apakah remote aktif")
        if re.search(
            r"^(?:(?:tolong\s+)?(?:nyalakan|aktifkan|hidupkan|jalankan|buka|start|launch)\s+(?:server\s+remote|remote\s+server|remote|pocketdesk(?:\s+remote)?)|"
            r"(?:server\s+remote|remote\s+server|remote|pocketdesk)\s+on)$",
            normalized,
            re.IGNORECASE,
        ):
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="start_remote_server",
                args={},
                raw_input=cleaned,
                normalized_input=normalized,
                description="Start PocketDesk Remote server",
            )

        if re.search(
            r"^(?:(?:tolong\s+)?(?:matikan|nonaktifkan|hentikan|tutup|stop|close)\s+(?:server\s+remote|remote\s+server|remote|pocketdesk(?:\s+remote)?)|"
            r"(?:server\s+remote|remote\s+server|remote|pocketdesk)\s+off)$",
            normalized,
            re.IGNORECASE,
        ):
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="stop_remote_server",
                args={},
                raw_input=cleaned,
                normalized_input=normalized,
                description="Stop PocketDesk Remote server",
            )

        if re.search(
            r"^(?:(?:cek|lihat|status|periksa|apakah)\s+(?:server\s+remote|remote\s+server|remote|pocketdesk(?:\s+remote)?)(?:\s+(?:aktif|hidup|jalan|running))?|"
            r"(?:server\s+remote|remote\s+server|remote|pocketdesk)\s+status)$",
            normalized,
            re.IGNORECASE,
        ):
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="get_remote_server_status",
                args={},
                raw_input=cleaned,
                normalized_input=normalized,
            )

        # Workspace Janitor Commands (e.g. "rapikan folder downloads", "rapikan desktop", "organize downloads")
        m_janitor = re.match(
            r"^(?:rapikan|bersihkan|organisir|organize|clean)\s+(?:folder\s+)?(downloads?|unduhan|desktop|layar\s+utama)$",
            normalized,
            re.IGNORECASE,
        )
        if m_janitor:
            raw_target = m_janitor.group(1).lower()
            target_folder = "desktop" if "desktop" in raw_target or "layar" in raw_target else "downloads"
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="clean_workspace",
                args={"target": target_folder},
                raw_input=cleaned,
                normalized_input=normalized,
                description=f"Workspace Janitor: clean {target_folder}",
            )

        # 1.44. Todo & Notes Commands
        # A. Todo Listing / Inquiries (e.g. "daftar tugas", "daftar todo", "lihat tugas", "cek todo", "ada tugas apa", "show todos", "task list", "/todo")
        is_list_todos = bool(
            re.match(
                r"^(?:(?:tolong\s+)?(?:tampilkan|lihat|cek|buka|show|view|get|list)\s+(?:daftar\s+)?(?:tugas|todos?|to-do|to\s+do|catatan|tasks?)|"
                r"daftar\s+(?:tugas|todos?|to-do|to\s+do|catatan|tasks?)|"
                r"(?:task|tasks|todo|todos|to-do|to\s+do)\s+list|"
                r"(?:ada\s+)?(?:tugas|todo|catatan)\s+apa(?:\s+saja)?|"
                r"apa(?:\s+saja)?\s+(?:daftar\s+)?(?:tugas(?:ku)?|todo(?:ku)?|catatan(?:ku)?)(?:\s+(?:saya|aku|gue|gw))?(?:\s+hari\s+ini)?|"
                r"(?:tugas(?:ku)?|todo(?:ku)?)(?:\s+(?:saya|aku|gue|gw))?\s+apa(?:\s+saja)?|"
                r"(?:my\s+tasks?|my\s+todos?|all\s+tasks?|all\s+todos?)|"
                r"(?:/todo|/todos|/tasks|todo|todos|tasks))$",
                normalized,
                re.IGNORECASE,
            )
        )
        if is_list_todos:
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="list_todos",
                args={},
                raw_input=cleaned,
                normalized_input=normalized,
                description="List active user todos",
            )

        # B. Todo Completion (e.g. "selesaikan tugas 1", "centang todo 2")
        m_complete_todo = re.match(
            r"^(?:(?:tolong\s+)?(?:selesaikan|centang|tandai\s+selesai|complete|finish|check\s+off)\s+(?:tugas|todo|task)?\s*(?:#|nomor|no)?\s*(\d+))$",
            normalized,
            re.IGNORECASE,
        )
        if m_complete_todo:
            num = int(m_complete_todo.group(1))
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="complete_todo",
                args={"task_number": num},
                raw_input=cleaned,
                normalized_input=normalized,
                description=f"Complete todo #{num}",
            )

        # C1. Clear All Todos (e.g. "hapus semua todo", "hapus semua tugas", "kosongkan todo", "clear all todos")
        if re.search(
            r"^(?:(?:tolong\s+)?(?:hapus|bersihkan|kosongkan|clear|delete)\s+(?:semua\s+)?(?:daftar\s+)?(?:tugas|todo|todos|to-do|to\s+do|tasks?)|"
            r"(?:clear|delete)\s+all(?:\s+(?:todos?|tasks?))?)$",
            normalized,
            re.IGNORECASE,
        ):
            if "selesai" not in normalized.lower() and "completed" not in normalized.lower() and not re.search(r"\d+", normalized):
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="clear_all_todos",
                    args={},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description="Clear all user todos",
                )

        # C2. Clear Completed Todos (e.g. "hapus todo selesai", "bersihkan tugas yang selesai")
        if re.search(
            r"^(?:(?:tolong\s+)?(?:hapus|bersihkan|clear)\s+(?:semua\s+)?(?:tugas|todo|tasks?)\s+(?:yang\s+)?(?:sudah\s+)?selesai|clear\s+completed(?:\s+todos?)?)$",
            normalized,
            re.IGNORECASE,
        ):
            return RouteResult(
                route_type=RouteType.FAST_COMMAND,
                action="clear_completed_todos",
                args={},
                raw_input=cleaned,
                normalized_input=normalized,
                description="Clear completed todos",
            )

        # D. Todo Capture (e.g. "catat todo: bayar tagihan", "tambah tugas: kirim email", "ingatkan saya jam 14.20 beli makan")
        m_todo = re.match(
            r"^(?:(?:tolong\s+)?(?:catat(?:kan)?|tambah(?:kan)?)\s*(?:todo|to-do|to\s+do|tugas|catatan)?|todo|tugas|catatan)(?:\s*:\s*|\s+)(.+)$",
            normalized,
            re.IGNORECASE,
        )
        if not m_todo:
            m_remind = re.match(
                r"^(?:tolong\s+)?ingatkan\s+(?:saya|aku|kami)?\s*(?:untuk\s+)?(.+)$",
                normalized,
                re.IGNORECASE,
            )
            if m_remind:
                m_todo = m_remind

        if m_todo:
            task_text = m_todo.group(1).strip()
            if not re.match(r"^(?:apa(?:\s+saja)?|yang\s+ada|hari\s+ini)$", task_text, re.IGNORECASE):
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="add_todo",
                    args={"task": task_text},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Todo add: {task_text}",
                )

        # 1.45. Multi-step Instructions, Complex Goals, or Implicit Diagnostic Intent -> Autonomous Agentic Loop
        if is_multi_step_or_implicit_intent(normalized, cleaned):
            return RouteResult(
                route_type=RouteType.AI_REQUEST,
                action="agentic_task",
                args={"goal": cleaned},
                raw_input=cleaned,
                normalized_input=normalized,
                description=f"Autonomous Agentic Task: {cleaned}",
                confidence=0.95,
            )

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
            r"^(?:(?:(buka|open|bacakan|read|tampilkan|lihat|ke|menuju|pindah\s+ke|go\s+to)\s+)?(?:ke\s+)?(?:sumber|hasil(?:\s+pencarian)?|artikel|link|tautan|the\s+result|the\s+article|the\s+source|result|article|source|nomor|no)?\s*(?:ke-?|nomor\s+|no\.?\s*)?(pertama|kedua|ketiga|1|2|3|first|second|third|1st|2nd|3rd|source\s+1|source\s+2)(?:\s*(?:source|artikel|hasil|result|article|link|tautan))?)$",
            normalized,
            re.IGNORECASE,
        )
        if m_src:
            raw_verb = m_src.group(1) or ""
            verb = raw_verb.lower().strip()
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
            # Check Mute / Unmute fast commands
            m_mute = re.match(r"^(?:mute|unmute|senyap(?:kan)?|bisu|matikan\s+suara|nyalakan\s+suara|hidupkan\s+suara|aktifkan\s+suara)(?:\s+(?:the\s+)?(?:volume|sound|audio|suara))?$", normalized)
            if m_mute:
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="toggle_mute",
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description="Fast command: toggle_mute",
                )

            # Check Volume Up/Down with percentage or steps (e.g. "kecilkan suara 20%", "turunkan volume 20%")
            m_vol = re.match(
                r"^(?:(turunkan|kecilkan|decrease|lower|turn\s+down|quieter)|(naikkan|besarkan|increase|raise|turn\s+up|louder))\s+"
                r"(?:the\s+)?(?:volume|suara|audio|sound)?\s*"
                r"(?:sebesar\s+)?(\d+)?\s*(?:%|persen|percent)?$",
                normalized,
            )
            if m_vol:
                is_down = bool(m_vol.group(1))
                act = "volume_down" if is_down else "volume_up"
                pct_str = m_vol.group(3)
                steps = 2
                if pct_str:
                    pct = int(pct_str)
                    steps = max(1, round(pct / 2))
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action=act,
                    args={"steps": steps, "percentage": int(pct_str) if pct_str else steps * 2},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Fast command: {act} (steps={steps})",
                )

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

            # Check User Profile View / Management (/profile, siapa aku, apa yang kamu ingat tentang saya)
            m_profile = re.match(
                r"^(?:/profile|profil(?:ku| saya)?|who\s+am\s+i|siapa\s+aku|tampilkan\s+profil|kartu\s+profil|apa\s+yang\s+(?:kamu|anda)\s+ingat(?:\s+tentang\s+saya)?|what\s+do\s+you\s+remember(?:\s+about\s+me)?)$",
                normalized,
                re.IGNORECASE,
            )
            if m_profile:
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="show_profile",
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description="Show user profile and habits card",
                )

            # Check Universal Learning Engine: /learn <text>, or voice "pelajari ini: <text>", "pelajari tentang aku"
            learn_match = re.match(
                r"^(?:/learn(?:\s+(.+))?|(?:jarvis\s+)?(?:tolong\s+)?pelajari\s+ini(?:\s*:\s*|\s+)(.+)|(?:jarvis\s+)?(?:tolong\s+)?(?:pelajari\s+tentang\s+aku|mari\s+belajar\s+tentang\s+aku|pelajari\s+kebiasaanku)(?:\s*:\s*|\s+)?(.*))$",
                normalized,
                re.IGNORECASE,
            )
            if learn_match:
                l_text = learn_match.group(1) or learn_match.group(2) or learn_match.group(3)
                l_text = (l_text or "").strip()
                if not l_text:
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="interactive_learn_session",
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description="Start interactive memory learning session",
                    )
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="learn_memory",
                    args={"text": l_text},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Universal learn memory: {l_text[:40]}",
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

            # Check Contextual Media Play Follow-up (e.g. "yes play it for me", "play it", "putar sekarang", "iya putarkan", "yes play it")
            m_followup_play = re.match(
                r"^(?:yes\s+|ya\s+|ok\s+|oke\s+|iya\s+)?(?:play\s+it(?:\s+for\s+me)?|putar(?:kan)?(?:\s+(?:lagunya|lagu|musik(?:nya)?|it))?(?:\s+sekarang)?|mainkan(?:\s+(?:lagunya|lagu|musik(?:nya)?|it))?(?:\s+sekarang)?|tolong\s+putar|yes\s+play|play\s+the\s+song)$",
                normalized,
                re.IGNORECASE,
            )
            if m_followup_play:
                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="play_contextual_music",
                    args={"query": ""},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description="Fast command: play_contextual_music",
                    confidence=1.0,
                )

            # Check Specific Play Music command (e.g. "putar lagu bohemian rhapsody", "play queen", "setel denada")
            play_match = re.match(r"^(?:play|putar|setel|mainkan)\s+(?:lagu|musik|track)?\s*(.+)$", normalized)
            if play_match:
                song_query = play_match.group(1).strip()
                if song_query not in ("music", "musik", "lagu"):
                    if song_query in ("it", "lagunya", "the song", "song"):
                        return RouteResult(
                            route_type=RouteType.FAST_COMMAND,
                            action="play_contextual_music",
                            args={"query": ""},
                            raw_input=cleaned,
                            normalized_input=normalized,
                            description="Fast command: play_contextual_music",
                            confidence=1.0,
                        )
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

            # Fuzzy Verb Recovery for Open commands (tolerate typos: 'oen', 'bka', 'opn', 'bukaa', 'bukak', etc.)
            if not open_match:
                toks = normalized.split()
                if toks:
                    first_tok = toks[0]
                    if len(first_tok) >= 3:
                        import difflib
                        for v in ("open", "buka", "launch", "start", "jalankan", "nyalakan"):
                            if difflib.SequenceMatcher(None, first_tok, v).ratio() >= 0.72:
                                rest_arg = " ".join(toks[1:])
                                normalized_open = f"{v} {rest_arg}".strip()
                                open_match = re.match(
                                    r"^(?:open|launch|start|run|buka|jalankan|nyalakan)(?:\s+(.*))?$",
                                    normalized_open,
                                )
                                if open_match:
                                    normalized = normalized_open
                                    break

            # Standalone Application or Website Launch (e.g. user says "chrome", "spotify", "crome", "youtube")
            _CLOSE_VERB_PREFIXES = (
                "close", "quit", "exit", "kill", "terminate", "stop",
                "tutup", "matikan", "hentikan", "clsoe", "clse", "tutp", "tutu", "ttup"
            )
            is_close_prefix = any(normalized.startswith(p) for p in _CLOSE_VERB_PREFIXES)
            if not open_match and not is_close_prefix and len(normalized.split()) <= 3:
                cand_target = clean_target_identifier(normalized)
                if cand_target and not any(cand_target.startswith(p) for p in ("tab ", "folder ", "lagu ", "musik ", "layar ", "screen ")):
                    from app.tools.browser import is_known_website
                    from app.tools.apps import registry, find_application_executable, normalize_app_name, find_best_app_or_site_candidate

                    canon_cand = normalize_app_name(cand_target)
                    is_valid_direct = (
                        registry.get(canon_cand) is not None
                        or is_known_website(cand_target)
                        or (find_application_executable(canon_cand) is not None)
                    )
                    if not is_valid_direct:
                        fuzzy_c = find_best_app_or_site_candidate(cand_target, cutoff=0.75)
                        if fuzzy_c is not None:
                            is_valid_direct = True

                    if is_valid_direct:
                        normalized_open = f"open {normalized}"
                        open_match = re.match(
                            r"^(?:open|launch|start|run|buka|jalankan|nyalakan)(?:\s+(.*))?$",
                            normalized_open,
                        )
                        if open_match:
                            normalized = normalized_open

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

                # Case A.5: Non-computer conversational topic / discussion / physical objects
                if any(k in cleaned_target for k in ["diskusi", "discussion", "debat", "debate", "topik", "topic", "pintu", "door"]):
                    return RouteResult(
                        route_type=RouteType.AI_REQUEST,
                        action="llm_chat",
                        args={"prompt": cleaned},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description="Conversational non-app request",
                        confidence=0.5,
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
                from app.memory.memory import memory_manager

                # Deep Personalization: Dynamic resolution of generic tool requests
                if cleaned_target in ("browser", "peramban", "web browser"):
                    preferred = memory_manager.get_preferred_tool("browser", "chrome")
                    if preferred:
                        cleaned_target = preferred.lower()
                elif cleaned_target in ("editor", "code editor", "text editor", "ide"):
                    preferred = memory_manager.get_preferred_tool("editor", "code")
                    if preferred:
                        cleaned_target = preferred.lower()
                elif cleaned_target in ("musik", "music", "pemutar musik", "music player"):
                    preferred = memory_manager.get_preferred_tool("music", "spotify")
                    if preferred:
                        cleaned_target = preferred.lower()

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

                # Case D: Strict Intent Guard & Fuzzy Matching
                # The user explicitly used an opening imperative verb ("buka", "open", "jalankan"),
                # but the target had a typo or was not an exact match. Never fall through to LLM!
                from app.tools.apps import find_best_app_or_site_candidate, scan_start_menu_apps

                fuzzy_cand = find_best_app_or_site_candidate(cleaned_target, cutoff=0.55)
                if fuzzy_cand is not None:
                    t_type, c_canon, c_disp, c_score = fuzzy_cand
                    return RouteResult(
                        route_type=RouteType.CLARIFY,
                        action="clarify_open_fuzzy",
                        args={
                            "target": c_canon,
                            "display_name": c_disp,
                            "target_type": t_type,
                            "raw_target": raw_arg.strip(),
                            "score": c_score,
                        },
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fuzzy open clarification for '{cleaned_target}' -> '{c_disp}' (score={c_score:.2f})",
                        confidence=c_score,
                    )

                # Case E: Windows Start Menu dynamic scan
                start_hit = scan_start_menu_apps(cleaned_target)
                if start_hit is not None:
                    hit_name, hit_path = start_hit
                    return RouteResult(
                        route_type=RouteType.FAST_COMMAND,
                        action="open_application",
                        args={"target": str(hit_path), "raw_target": raw_arg.strip(), "display_name": hit_name},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fast command: open_start_menu_app ({hit_name})",
                    )

                # Case F: Unknown target or complex phrase
                if is_multi_step_or_implicit_intent(cleaned_target, cleaned) or len(cleaned_target.split()) >= 3:
                    return RouteResult(
                        route_type=RouteType.AI_REQUEST,
                        action="agentic_task",
                        args={"goal": cleaned},
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Autonomous Agentic Task: {cleaned}",
                        confidence=0.85,
                    )

                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="app_not_found",
                    args={"target": cleaned_target, "raw_target": raw_arg.strip(), "operation": "open"},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Target application not found: {cleaned_target}",
                )

            # Check Application Termination:
            # Matches: close, quit, exit, kill, terminate, stop, tutup, matikan, hentikan
            close_match = re.match(
                r"^(?:close|quit|exit|kill|terminate|stop|tutup|matikan|hentikan)(?:\s+(.*))?$",
                normalized,
            )

            # Fuzzy Verb Recovery for Close commands (tolerate typos: 'clsoe', 'tutp', 'clse', etc.)
            if not close_match:
                toks = normalized.split()
                if toks:
                    first_tok = toks[0]
                    if len(first_tok) >= 3:
                        import difflib
                        for v in ("close", "tutup", "matikan", "quit", "exit", "hentikan"):
                            if difflib.SequenceMatcher(None, first_tok, v).ratio() >= 0.72:
                                rest_arg = " ".join(toks[1:])
                                normalized_close = f"{v} {rest_arg}".strip()
                                close_match = re.match(
                                    r"^(?:close|quit|exit|kill|terminate|stop|tutup|matikan|hentikan)(?:\s+(.*))?$",
                                    normalized_close,
                                )
                                if close_match:
                                    normalized = normalized_close
                                    break

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

                from app.tools.apps import registry, normalize_app_name, find_best_app_or_site_candidate
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

                # Strict Intent Guard for Close commands:
                fuzzy_cand = find_best_app_or_site_candidate(cleaned_target, cutoff=0.55)
                if fuzzy_cand is not None and fuzzy_cand[0] == "app":
                    _, c_canon, c_disp, c_score = fuzzy_cand
                    return RouteResult(
                        route_type=RouteType.CLARIFY,
                        action="clarify_close_fuzzy",
                        args={
                            "target": c_canon,
                            "display_name": c_disp,
                            "raw_target": raw_arg.strip(),
                            "score": c_score,
                        },
                        raw_input=cleaned,
                        normalized_input=normalized,
                        description=f"Fuzzy close clarification for '{cleaned_target}' -> '{c_disp}' (score={c_score:.2f})",
                        confidence=c_score,
                    )

                return RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action="app_not_found",
                    args={"target": cleaned_target, "raw_target": raw_arg.strip(), "operation": "close"},
                    raw_input=cleaned,
                    normalized_input=normalized,
                    description=f"Close target not found: {cleaned_target}",
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

        # 3.5. Tier 2: Machine Learning Intent Classifier (Trained on Desktop Commands & Slang)
        # Bypasses LLM for novel phrasing, slang, and phonetic variations with < 1ms CPU inference
        if not is_conversational_inquiry:
            try:
                from app.ai.ml_classifier import get_ml_classifier
                ml_clf = get_ml_classifier()
                ml_pred = ml_clf.predict(normalized)
                if ml_pred is not None:
                    # Threshold A: High Confidence (>= 0.80) -> Direct instant execution!
                    if ml_pred.confidence >= 0.80:
                        r_type = RouteType.WEB_SEARCH if ml_pred.intent == "search_web" else RouteType.FAST_COMMAND
                        return RouteResult(
                            route_type=r_type,
                            action=ml_pred.action,
                            args=dict(ml_pred.args),
                            raw_input=cleaned,
                            normalized_input=normalized,
                            description=f"ML intent direct: {ml_pred.intent} (conf={ml_pred.confidence:.2f})",
                            confidence=ml_pred.confidence,
                        )

                    # Threshold B: Medium Confidence (0.45 <= conf < 0.80) -> Clarify & Active Learn!
                    elif ml_pred.confidence >= 0.45:
                        return RouteResult(
                            route_type=RouteType.CLARIFY,
                            action="clarify_ml_intent",
                            args={
                                "intent": ml_pred.intent,
                                "action": ml_pred.action,
                                "target": ml_pred.target,
                                "args": ml_pred.args,
                                "confidence": ml_pred.confidence,
                                "raw_input": cleaned,
                            },
                            raw_input=cleaned,
                            normalized_input=normalized,
                            description=f"ML intent clarification: {ml_pred.intent} (conf={ml_pred.confidence:.2f})",
                            confidence=ml_pred.confidence,
                        )
            except Exception as ml_err:
                logger.debug("ML Intent Classifier check failed: %s", ml_err)

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

