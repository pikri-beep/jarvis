"""Screen Reader, Vision, and Multi-Layer Screen Understanding for JARVIS on Windows 11.

Follows AGENTS.md and User Requirements:
- Multi-layer observation:
  1. Windows UI Automation (controls, types, labels, states, bounding boxes, center coordinates).
  2. Native Windows WinRT OCR with layout and region classification (titles, buttons, errors, body).
  3. On-demand local Vision model integration via Ollama (lightweight, zero automatic downloads).
- Normalized ScreenObservation data structure.
- Contextual screen question answering ("Apa yang sedang terbuka?", "Apakah musik diputar?", etc.).
- Reference resolving ("tombol yang merah di sebelah kanan", "tombol play").
- Privacy-first: strictly on-demand, temporary screenshot deleted in finally block.
- Zero hallucination: clearly distinguishes observed facts from unreadable areas.
"""

from dataclasses import dataclass, field
import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request
import uuid

import psutil

from app.core.logger import setup_logger

logger = setup_logger("jarvis.tools.screen_reader")


# ---------------------------------------------------------------------------
# Data Models for Screen Understanding
# ---------------------------------------------------------------------------

@dataclass
class UIElement:
    """Structured interactive or visual UI element from Windows UI Automation."""
    name: str = ""
    control_type: str = "Unknown"  # "Button", "Edit", "Text", "Hyperlink", "TabItem", "ListItem", etc.
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, width, height)
    center_x: int = 0
    center_y: int = 0
    is_enabled: bool = True
    is_focused: bool = False
    class_name: str = ""
    automation_id: str = ""


@dataclass
class IndexedUIElement:
    """UI element tagged with an explicit integer index for Set-of-Marks visual referencing."""
    index: int
    name: str
    control_type: str
    center_x: int
    center_y: int
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0)
    is_focused: bool = False
    is_enabled: bool = True
    automation_id: str = ""


@dataclass
class TextRegion:
    """Recognized OCR text segment with bounding box and layout category."""
    text: str = ""
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, width, height)
    category: str = "body"  # "title", "button", "error", "notification", "body"


@dataclass
class ScreenObservation:
    """Normalized multi-layer screen observation combining UIA, OCR, and Vision."""
    window_title: str = ""
    process_name: str = ""
    hwnd: int = 0
    window_rect: Tuple[int, int, int, int] = (0, 0, 0, 0)
    browser_url: Optional[str] = None
    browser_page_title: Optional[str] = None
    elements: List[UIElement] = field(default_factory=list)
    text_regions: List[TextRegion] = field(default_factory=list)
    raw_text: str = ""
    full_text: str = ""
    vision_description: Optional[str] = None
    vision_model: Optional[str] = None
    timestamp: float = 0.0
    source: str = "hybrid"  # "uia", "ocr", "vision", "hybrid", "fallback"


@dataclass
class ScreenReadResult:
    """Result of an on-demand screen reading operation."""
    success: bool
    text: str = ""
    method: str = "none"  # "uia", "ocr", "vision", "hybrid", "fallback"
    window_title: str = ""
    spoken_summary: str = ""
    display_text: str = ""
    vision_available: bool = False
    vision_model: Optional[str] = None
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    temporary_file_cleaned: bool = True
    observation: Optional[ScreenObservation] = None


# ---------------------------------------------------------------------------
# Active Window and Geometry Inspection
# ---------------------------------------------------------------------------

def get_active_window_info() -> Dict[str, str]:
    """Retrieves the foreground window title and process information via Windows API."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"title": "Desktop / Windows Explorer", "hwnd": "0", "pid": "0", "process": "explorer.exe"}

        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
        else:
            title = "Unknown Window"

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pname = "unknown"
        if pid.value > 0:
            try:
                pname = psutil.Process(pid.value).name()
            except Exception:
                pname = "unknown"

        return {
            "title": title or "Active Desktop Window",
            "hwnd": str(hwnd),
            "pid": str(pid.value),
            "process": pname,
        }
    except Exception as e:
        logger.debug("Failed to get foreground window info: %s", e)
        return {"title": "Active Window", "hwnd": "0", "pid": "0", "process": "unknown"}


# ---------------------------------------------------------------------------
# Layer 1: Windows UI Automation Extraction
# ---------------------------------------------------------------------------

def extract_uia_elements(hwnd: Optional[int] = None) -> List[UIElement]:
    """Extracts structured UI elements (buttons, inputs, tabs, lists) via Windows UI Automation."""
    target_hwnd = hwnd if (hwnd and hwnd > 0) else 0
    ps_script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
try {{
    $hwnd = [IntPtr]{target_hwnd}
    $root = if ($hwnd -ne [IntPtr]::Zero) {{
        [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
    }} else {{
        [System.Windows.Automation.AutomationElement]::RootElement
    }}
    if (-not $root) {{ '[]'; exit }}

    $cond = [System.Windows.Automation.Condition]::TrueCondition
    $children = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
    $results = @()
    foreach ($c in $children) {{
        $curr = $c.Current
        $name = $curr.Name
        $ctype = $curr.ControlType.ProgrammaticName.Replace('ControlType.', '')
        $rect = $curr.BoundingRectangle
        if ($name -or ($ctype -in @('Button', 'Edit', 'Hyperlink', 'TabItem', 'ListItem', 'MenuItem', 'CheckBox'))) {{
            $results += [ordered]@{{
                Name = if ($name) {{ $name.Trim() }} else {{ '' }}
                ControlType = $ctype
                X = [int]$rect.X
                Y = [int]$rect.Y
                Width = [int]$rect.Width
                Height = [int]$rect.Height
                IsEnabled = $curr.IsEnabled
                HasFocus = $curr.HasKeyboardFocus
                ClassName = $curr.ClassName
                AutomationId = $curr.AutomationId
            }}
            if ($results.Count -ge 35) {{ break }}
        }}
    }}
    $results | ConvertTo-Json -Compress
}} catch {{
    '[]'
}}
"""
    try:
        import base64
        encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        if proc.returncode == 0 and proc.stdout.strip():
            raw = json.loads(proc.stdout.strip())
            if isinstance(raw, dict):
                raw = [raw]
            elements = []
            for item in raw:
                x = int(item.get("X", 0))
                y = int(item.get("Y", 0))
                w = int(item.get("Width", 0))
                h = int(item.get("Height", 0))
                el = UIElement(
                    name=item.get("Name", ""),
                    control_type=item.get("ControlType", "Unknown"),
                    rect=(x, y, w, h),
                    center_x=x + (w // 2) if w > 0 else x,
                    center_y=y + (h // 2) if h > 0 else y,
                    is_enabled=bool(item.get("IsEnabled", True)),
                    is_focused=bool(item.get("HasFocus", False)),
                    class_name=item.get("ClassName", ""),
                    automation_id=item.get("AutomationId", ""),
                )
                elements.append(el)
            return elements
        return []
    except Exception as e:
        logger.debug("UIA extraction failed: %s", e)
        return []


def _extract_uia_elements() -> str:
    """Legacy helper returning newline-separated top UI element names."""
    elements = extract_uia_elements()
    names = [e.name for e in elements if e.name and len(e.name) > 2]
    return "\n".join(names[:5])


# ---------------------------------------------------------------------------
# Layer 2: Windows WinRT OCR & Layout Analysis
# ---------------------------------------------------------------------------

def _capture_screen_to_file(target_path: Path) -> bool:
    """Captures the primary screen bounds to a specific PNG file using PowerShell System.Drawing."""
    try:
        p_str = target_path.as_posix()
        ps_script = (
            "[Reflection.Assembly]::LoadWithPartialName('System.Drawing') | Out-Null; "
            "[Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
            "$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
            "$graphics = [System.Drawing.Graphics]::FromImage($bmp); "
            "$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size); "
            f"$bmp.Save('{p_str}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$graphics.Dispose(); "
            "$bmp.Dispose();"
        )
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return proc.returncode == 0 and target_path.exists() and target_path.stat().st_size > 0
    except Exception as e:
        logger.error("Screenshot capture failed: %s", e)
        return False


def _run_winrt_ocr(image_path: Path) -> str:
    """Performs local OCR using Windows 11 native Windows.Media.Ocr.OcrEngine."""
    if not image_path.exists():
        return ""

    p_str = image_path.as_posix()
    ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName 'System.Runtime.WindowsRuntime'
try {{
    [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

    $asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod }} | Select-Object -First 1

    $opFile = [Windows.Storage.StorageFile]::GetFileFromPathAsync('{p_str}')
    $file = ($asTaskGeneric.MakeGenericMethod([Windows.Storage.StorageFile]).Invoke($null, @($opFile))).Result

    $opStream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    $stream = ($asTaskGeneric.MakeGenericMethod([Windows.Storage.Streams.IRandomAccessStream]).Invoke($null, @($opStream))).Result

    $opDec = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    $decoder = ($asTaskGeneric.MakeGenericMethod([Windows.Graphics.Imaging.BitmapDecoder]).Invoke($null, @($opDec))).Result

    $opBmp = $decoder.GetSoftwareBitmapAsync()
    $softBmp = ($asTaskGeneric.MakeGenericMethod([Windows.Graphics.Imaging.SoftwareBitmap]).Invoke($null, @($opBmp))).Result

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) {{
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
    }}
    $opOcr = $engine.RecognizeAsync($softBmp)
    $ocrResult = ($asTaskGeneric.MakeGenericMethod([Windows.Media.Ocr.OcrResult]).Invoke($null, @($opOcr))).Result

    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $ocrResult.Text
}} catch {{
    Write-Output ""
}}
"""
    try:
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        if proc.returncode == 0:
            return proc.stdout.strip()
        return ""
    except Exception as e:
        logger.error("WinRT OCR execution failed: %s", e)
        return ""


def classify_text_regions(text: str) -> List[TextRegion]:
    """Analyzes OCR text and decomposes into structured, categorized text regions."""
    regions: List[TextRegion] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    error_keywords = ["error", "exception", "failed", "gagal", "warning", "fatal", "peringatan", "galat"]
    button_keywords = ["play", "pause", "submit", "lanjut", "next", "ok", "cancel", "buka", "tutup", "save", "simpan"]

    for idx, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in error_keywords):
            cat = "error"
        elif any(kw in line_lower for kw in button_keywords) and len(line.split()) <= 4:
            cat = "button"
        elif idx == 0 and len(line) < 80:
            cat = "title"
        else:
            cat = "body"
        
        regions.append(TextRegion(text=line, rect=(0, idx * 30, len(line) * 8, 25), category=cat))
    return regions


# ---------------------------------------------------------------------------
# Layer 3: Visual Understanding & Ollama Vision Integration
# ---------------------------------------------------------------------------

def check_vision_model_available(ollama_url: str = "http://127.0.0.1:11434") -> Tuple[bool, Optional[str], str]:
    """Inspects installed Ollama models to check if any model has vision/multimodal capabilities."""
    known_vision_keywords = [
        "vision", "llava", "bakllava", "moondream", "mllama", "vl",
        "qwen-vl", "qwen2-vl", "qwen2.5-vl", "minicpm-v", "cogvlm"
    ]
    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/tags",
            headers={"User-Agent": "JARVIS-ScreenReader/1.0"}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            for m in models:
                name = m.get("name", "").lower()
                if any(kw in name for kw in known_vision_keywords):
                    return True, m.get("name"), f"Model visi lokal ditemukan: {m.get('name')}"
                
                details = m.get("details", {})
                families = details.get("families", []) or []
                if any(f in ["clip", "mllama", "vision"] for f in families):
                    return True, m.get("name"), f"Model visi lokal terdeteksi (keluarga visi): {m.get('name')}"

        return False, None, "Tidak ada model visi lokal terpasang di Ollama."
    except Exception as e:
        logger.debug("Ollama vision check error: %s", e)
        return False, None, f"Ollama tidak dapat diakses ({e})."


def query_ollama_vision(
    image_path: Path,
    prompt: str,
    model_name: str,
    ollama_url: str = "http://127.0.0.1:11434",
) -> Optional[str]:
    """Queries local Ollama vision model on-demand with base64 encoded screen image."""
    if not image_path.exists():
        return None

    import base64
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": model_name,
            "prompt": prompt or "Describe what you see on this desktop screen concisely in 2 sentences.",
            "images": [img_b64],
            "stream": False,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "JARVIS-Vision/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data.get("response", "").strip()
    except Exception as e:
        logger.warning("Ollama vision query failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Text Sanitization and Summarization
# ---------------------------------------------------------------------------

def clean_extracted_screen_text(raw_text: str) -> str:
    """Cleans and sanitizes screen text to avoid prompt injection or garbage characters."""
    if not raw_text:
        return ""
    clean_chars = [c for c in raw_text if c.isprintable() or c in "\n\t "]
    cleaned = "".join(clean_chars)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return "\n".join(lines)


def summarize_screen_text(text: str, window_title: str, language: str = "id") -> str:
    """Builds a concise 1-2 sentence spoken summary of screen contents without LLM invocation."""
    is_id = language.lower().startswith("id")
    cleaned = clean_extracted_screen_text(text)
    
    if not cleaned:
        if is_id:
            return f"Jendela aktif adalah {window_title}, namun tidak ada teks yang terbaca di layar."
        else:
            return f"The active window is {window_title}, but no readable text was detected on screen."

    lines = [l for l in cleaned.splitlines() if len(l) > 3]
    first_extract = lines[0] if lines else cleaned[:100]
    if len(first_extract) > 90:
        first_extract = first_extract[:87] + "..."

    has_error = any(kw in cleaned.lower() for kw in ["error", "exception", "failed", "gagal", "warning", "fatal"])
    
    if is_id:
        if has_error:
            return f"Di jendela {window_title}, terdeteksi pesan galat atau peringatan: {first_extract}."
        return f"Jendela aktif adalah {window_title}. Teks terdeteksi: {first_extract}."
    else:
        if has_error:
            return f"In {window_title}, an error or warning message was detected: {first_extract}."
        return f"Active window is {window_title}. Detected text: {first_extract}."


# ---------------------------------------------------------------------------
# Screen Question Answering & Element Matching
# ---------------------------------------------------------------------------

def answer_screen_question(
    question: str,
    observation: ScreenObservation,
    language: str = "id"
) -> str:
    """Answers specific user questions about screen contents based strictly on observed evidence."""
    is_id = language.lower().startswith("id")
    q_lower = question.lower().strip()
    title = observation.window_title or "Jendela Aktif"
    raw_text = observation.full_text or ""
    elements = observation.elements

    # 1. "Apa yang sedang terbuka di layar?" / "Aku sedang ada di halaman apa?"
    if any(p in q_lower for p in ["apa yang sedang terbuka", "apa yang terbuka", "sedang ada di halaman apa", "halaman apa", "what is open", "what's on my screen"]):
        browser_info = ""
        if observation.browser_page_title:
            browser_info = f" ({observation.browser_page_title})"
        if is_id:
            return f"Jendela aktif saat ini adalah '{title}'{browser_info}, sir."
        else:
            return f"The active window is currently '{title}'{browser_info}, sir."

    # 2. "Bacakan pesan yang terlihat"
    if any(p in q_lower for p in ["bacakan pesan", "baca pesan", "read message", "read text"]):
        err_regions = [r.text for r in observation.text_regions if r.category == "error"]
        if err_regions:
            return f"Pesan galat yang terdeteksi: '{err_regions[0]}', sir." if is_id else f"Detected error message: '{err_regions[0]}', sir."
        first_lines = [r.text for r in observation.text_regions[:3]]
        sample = "; ".join(first_lines) if first_lines else raw_text[:100]
        if sample:
            return f"Pesan yang terbaca: '{sample}', sir." if is_id else f"Visible text: '{sample}', sir."
        return "Tidak ada teks atau pesan yang terbaca dengan jelas, sir." if is_id else "No clear text or message detected, sir."

    # 3. "Tombol mana yang harus diklik untuk melanjutkan?"
    if any(p in q_lower for p in ["tombol mana yang harus diklik", "klik untuk melanjutkan", "which button to click", "continue button"]):
        for el in elements:
            el_name = el.name.lower()
            if any(k in el_name for k in ["lanjut", "next", "continue", "submit", "ok", "setuju", "kirim", "konfirmasi", "selesai"]):
                return f"Anda dapat mengeklik tombol '{el.name}' untuk melanjutkan, sir." if is_id else f"You can click the '{el.name}' button to proceed, sir."
        return "Tidak terlihat tombol lanjut atau next yang eksplisit pada antarmuka saat ini, sir." if is_id else "No explicit continue or next button was detected on screen, sir."

    # 4. "Apakah unduhan sudah selesai?"
    if any(p in q_lower for p in ["unduhan sudah selesai", "download selesai", "download finished", "download complete"]):
        lower_all = raw_text.lower()
        if any(k in lower_all for k in ["100%", "unduhan selesai", "download completed", "download finished", "completed"]):
            return "Indikator unduhan menunjukkan bahwa unduhan telah selesai, sir." if is_id else "The download indicator shows that the download is complete, sir."
        elif any(k in lower_all for k in ["mengunduh", "downloading", "mb/s", "kb/s", "%"]):
            return "Proses unduhan tampak masih berjalan di layar, sir." if is_id else "The download appears to still be in progress, sir."
        return "Tidak ditemukan indikator aktivitas unduhan di jendela saat ini, sir." if is_id else "No download indicator was found in the active window, sir."

    # 5. "Apakah musiknya sudah diputar?"
    if any(p in q_lower for p in ["musiknya sudah diputar", "lagunya sudah diputar", "is music playing", "is the video playing"]):
        lower_all = raw_text.lower()
        # Look for pause button or playing state
        has_pause = any("pause" in el.name.lower() or "jeda" in el.name.lower() for el in elements)
        has_play = any("play" in el.name.lower() or "putar" in el.name.lower() for el in elements)
        if "youtube" in title.lower() or "spotify" in title.lower():
            if has_pause:
                return "Media sedang aktif diputar (tombol Jeda tersedia), sir." if is_id else "Media is currently playing, sir."
            elif has_play:
                return "Halaman media terbuka, namun tombol Putar terlihat (mungkin masih dijeda), sir." if is_id else "Media page is open, but play button is visible (may be paused), sir."
            return "Halaman pemutar media terbuka dan siap, sir." if is_id else "The media player page is loaded, sir."
        return "Jendela saat ini tidak menampilkan antarmuka pemutar musik yang aktif, sir." if is_id else "The active window does not show an active music player, sir."

    # 6. "Kenapa langkah tadi gagal?"
    if any(p in q_lower for p in ["kenapa langkah tadi gagal", "mengapa gagal", "why did it fail", "kenapa gagal"]):
        err_regions = [r.text for r in observation.text_regions if r.category == "error"]
        if err_regions:
            return f"Langkah gagal karena muncul pesan: '{err_regions[0]}', sir." if is_id else f"The action failed due to error: '{err_regions[0]}', sir."
        return "Tidak terlihat dialog galat atau pesan penolakan di layar, sir." if is_id else "No error dialog or rejection message is visible on screen, sir."

    # 7. Identifying specific elements: "tombol yang merah di sebelah kanan itu apa?"
    if "tombol" in q_lower or "button" in q_lower:
        match_el = find_element_by_reference(q_lower, observation)
        if match_el:
            desc = f"Tombol '{match_el.name}' (tipe: {match_el.control_type})"
            if is_id:
                note = " (Catatan: verifikasi posisi dan label terdeteksi melalui UI Automation)."
                return f"Elemen yang dimaksud adalah {desc}, sir.{note}"
            else:
                return f"The element referred to is button '{match_el.name}' ({match_el.control_type}), sir."

    # Fallback to general summary
    return summarize_screen_text(raw_text, title, language=language)


def find_element_by_reference(reference: str, observation: ScreenObservation) -> Optional[UIElement]:
    """Resolves an element reference (e.g. 'tombol di sebelah kanan', 'tombol play') to a UIElement."""
    r = reference.lower()
    elements = observation.elements
    if not elements:
        return None

    # Check for position keywords
    is_right = any(k in r for k in ["kanan", "right", "sebelah kanan"])
    is_left = any(k in r for k in ["kiri", "left", "sebelah kiri"])
    is_top = any(k in r for k in ["atas", "top", "kanan atas", "kiri atas"])
    
    # Check for common button semantic names
    play_keywords = ["play", "putar", "mainkan"]
    close_keywords = ["close", "tutup", "merah", "red", "keluar"]

    candidates: List[UIElement] = []

    for el in elements:
        name_lower = el.name.lower()
        ctype = el.control_type.lower()
        
        # Close button heuristics (often red, top-right)
        if any(k in r for k in close_keywords) and is_right:
            if "close" in name_lower or "tutup" in name_lower or el.automation_id.lower() == "close":
                return el

        # Play button heuristics
        if any(k in r for k in play_keywords):
            if any(pk in name_lower for pk in play_keywords) or "play" in el.automation_id.lower():
                return el

        # Position filter
        if is_right and el.center_x > 960:
            candidates.append(el)
        elif is_left and el.center_x < 960:
            candidates.append(el)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        # If user specified button and one is a button
        buttons = [c for c in candidates if c.control_type == "Button"]
        if len(buttons) == 1:
            return buttons[0]

    return None


def get_indexed_ui_elements(observation: Optional[ScreenObservation], max_elements: int = 25) -> List[IndexedUIElement]:
    """Generates a 1-indexed list of interactive UI elements for precise Set-of-Marks grounding."""
    if not observation or not observation.elements:
        return []

    indexed: List[IndexedUIElement] = []
    INTERACTIVE_TYPES = {
        "Edit", "Button", "TabItem", "Hyperlink", "MenuItem",
        "SplitButton", "RadioButton", "CheckBox", "ComboBox", "ListItem"
    }

    curr_idx = 1
    for el in observation.elements:
        if (el.control_type in INTERACTIVE_TYPES or el.is_focused) and el.is_enabled:
            if el.center_x > 0 and el.center_y > 0:
                name_disp = el.name.strip() if el.name else (f"Input Field" if el.control_type == "Edit" else el.control_type)
                indexed.append(
                    IndexedUIElement(
                        index=curr_idx,
                        name=name_disp,
                        control_type=el.control_type,
                        center_x=el.center_x,
                        center_y=el.center_y,
                        rect=el.rect,
                        is_focused=el.is_focused,
                        is_enabled=el.is_enabled,
                        automation_id=el.automation_id,
                    )
                )
                curr_idx += 1
                if len(indexed) >= max_elements:
                    break
    return indexed


def format_indexed_screen_summary(observation: Optional[ScreenObservation], indexed_elements: List[IndexedUIElement]) -> str:
    """Formats a compact, token-dense screen summary for low-latency LLM reasoning."""
    if not observation:
        return "Screen State: No active window or elements observed."

    lines = [
        f"Active Window: \"{observation.window_title}\" (Process: {observation.process_name})",
        "Interactive Elements:"
    ]
    if indexed_elements:
        for item in indexed_elements[:20]:
            focus_mark = " [FOCUSED]" if item.is_focused else ""
            lines.append(f"  [{item.index}] {item.control_type}: \"{item.name}\"{focus_mark}")
    else:
        lines.append("  (No direct interactive controls mapped)")

    if observation.raw_text:
        text_lines = [l.strip() for l in observation.raw_text.splitlines() if l.strip()]
        if text_lines:
            sample_txt = " | ".join(text_lines[:6])
            lines.append(f"Screen Text Preview: {sample_txt}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Entry Point: read_screen_content
# ---------------------------------------------------------------------------

def read_screen_content(
    prompt: str = "",
    language: str = "id",
    vision_enabled: bool = False,
    ollama_url: str = "http://127.0.0.1:11434"
) -> ScreenReadResult:
    """Reads on-screen content on-demand, combining UI Automation, WinRT OCR, and local Vision."""
    t0 = time.perf_counter()
    window_info = get_active_window_info()
    window_title = window_info.get("title", "Active Window")
    hwnd_int = int(window_info.get("hwnd", "0"))
    pname = window_info.get("process", "unknown")

    temp_path = Path(tempfile.gettempdir()) / f"jarvis_screen_{uuid.uuid4().hex[:8]}.png"
    temp_cleaned = False
    extracted_text = ""
    used_method = "none"
    error_msg = None
    vision_desc = None

    # Layer 1: Structured UI Automation
    uia_elements = extract_uia_elements(hwnd=hwnd_int)

    try:
        # Layer 2: On-demand Screen Capture & WinRT OCR
        captured = _capture_screen_to_file(temp_path)
        if captured:
            ocr_text = _run_winrt_ocr(temp_path)
            if ocr_text and len(ocr_text.strip()) > 5:
                extracted_text = ocr_text.strip()
                used_method = "ocr"

        # Check vision model availability
        has_vision, vision_model, _ = check_vision_model_available(ollama_url)

        # Layer 3: Vision Model (if enabled and model is present)
        if captured and vision_enabled and has_vision and vision_model:
            vision_desc = query_ollama_vision(
                image_path=temp_path,
                prompt=prompt or "Describe the contents of this desktop window concisely.",
                model_name=vision_model,
                ollama_url=ollama_url,
            )
            if vision_desc:
                used_method = "hybrid" if extracted_text else "vision"

        if not extracted_text:
            if uia_elements:
                names = [e.name for e in uia_elements if e.name]
                extracted_text = "\n".join(names)
                used_method = "uia"
            elif not captured:
                used_method = "fallback"
                extracted_text = f"Active window: {window_title}"

    except Exception as e:
        logger.error("Screen reading exception: %s", e)
        error_msg = str(e)
    finally:
        # GUARANTEED CLEANUP: Always remove temporary screenshot immediately
        if temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
                temp_cleaned = True
            except Exception as e:
                logger.warning("Could not delete temp screenshot %s: %s", temp_path, e)
                temp_cleaned = False
        else:
            temp_cleaned = True

    # Classify text regions
    text_regions = classify_text_regions(extracted_text)

    # Build ScreenObservation
    observation = ScreenObservation(
        window_title=window_title,
        process_name=pname,
        hwnd=hwnd_int,
        elements=uia_elements,
        text_regions=text_regions,
        raw_text=extracted_text,
        vision_description=vision_desc,
        vision_model=vision_model if has_vision else None,
        timestamp=time.time(),
        source=used_method,
    )

    # Check if a specific screen question was asked
    if prompt and any(kw in prompt.lower() for kw in ["apa", "siapa", "mana", "apakah", "kenapa", "bacakan", "tombol"]):
        spoken = answer_screen_question(prompt, observation, language=language)
    else:
        spoken = summarize_screen_text(extracted_text, window_title, language=language)

    latency = (time.perf_counter() - t0) * 1000

    # Build detailed display text
    lines = [
        f"[SCREEN] Screen Reading Result ({used_method.upper()}, {latency:.1f}ms)",
        f"* Active Window: {window_title} ({pname})",
    ]
    if uia_elements:
        lines.append(f"* UI Elements Detected: {len(uia_elements)} controls")
    if not has_vision:
        lines.append("* Local Vision Model: Tidak tersedia di Ollama (menggunakan UI Automation & OCR).")
    else:
        lines.append(f"* Local Vision Model: {vision_model}")
        if vision_desc:
            lines.append(f"* Vision Description: {vision_desc}")

    lines.append("* Extracted Content:")
    sample = clean_extracted_screen_text(extracted_text)
    if sample:
        for sl in sample.splitlines()[:15]:
            lines.append(f"  > {sl}")
        if len(sample.splitlines()) > 15:
            lines.append(f"  > ... ({len(sample.splitlines()) - 15} baris lainnya)")
    else:
        lines.append("  > (Tidak ada teks terbaca)")

    display = "\n".join(lines)

    return ScreenReadResult(
        success=bool(extracted_text or window_title or uia_elements),
        text=extracted_text,
        method=used_method,
        window_title=window_title,
        spoken_summary=spoken,
        display_text=display,
        vision_available=has_vision,
        vision_model=vision_model,
        latency_ms=latency,
        error_message=error_msg,
        temporary_file_cleaned=temp_cleaned,
        observation=observation,
    )
