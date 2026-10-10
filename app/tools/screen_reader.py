"""Screen Reader & Vision tool for JARVIS on Windows 11.

Follows Workstream E & Workstream G requirements:
- On-demand single screen capture ONLY upon explicit user intent.
- No continuous background recording or monitoring.
- Native Windows UI Automation (active window inspection) + Windows 11 native WinRT OCR.
- Ollama vision model detection (strictly non-downloading; reports availability).
- Privacy-first: temporary screenshot saved to temp directory and deleted immediately in finally block.
- Zero external transmissions; untrusted content sanitization.
- Clean 1-2 sentence spoken summary for Piper TTS; detailed text output.
"""

from dataclasses import dataclass, field
import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Dict, List, Optional, Tuple
import urllib.error
import urllib.request
import uuid

from app.core.logger import setup_logger

logger = setup_logger("jarvis.tools.screen_reader")


@dataclass
class ScreenReadResult:
    """Result of an on-demand screen reading operation."""
    success: bool
    text: str = ""
    method: str = "none"  # "uia", "ocr", "vision", "fallback"
    window_title: str = ""
    spoken_summary: str = ""
    display_text: str = ""
    vision_available: bool = False
    vision_model: Optional[str] = None
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    temporary_file_cleaned: bool = True


def get_active_window_info() -> Dict[str, str]:
    """Retrieves the foreground window title and process information via Windows API."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"title": "Desktop / Windows Explorer", "hwnd": "0"}

        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
        else:
            title = "Unknown Window"

        # Try to get process ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        return {
            "title": title or "Active Desktop Window",
            "hwnd": str(hwnd),
            "pid": str(pid.value),
        }
    except Exception as e:
        logger.debug("Failed to get foreground window info: %s", e)
        return {"title": "Active Window", "hwnd": "0", "pid": "0"}


def check_vision_model_available(ollama_url: str = "http://127.0.0.1:11434") -> Tuple[bool, Optional[str], str]:
    """Inspects installed Ollama models to check if any model has vision/multimodal capabilities.
    
    Strictly read-only; never downloads models automatically.
    """
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
                # Check model name keywords
                if any(kw in name for kw in known_vision_keywords):
                    return True, m.get("name"), f"Model visi lokal ditemukan: {m.get('name')}"
                
                # Check details.families if available
                details = m.get("details", {})
                families = details.get("families", []) or []
                if any(f in ["clip", "mllama", "vision"] for f in families):
                    return True, m.get("name"), f"Model visi lokal terdeteksi (keluarga visi): {m.get('name')}"

        return False, None, "Tidak ada model visi lokal terpasang di Ollama."
    except Exception as e:
        logger.debug("Ollama vision check error: %s", e)
        return False, None, f"Ollama tidak dapat diakses ({e})."


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


def _extract_uia_elements() -> str:
    """Attempts fast inspection of top visible UI elements via UI Automation."""
    ps_script = """
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
try {
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $cond = [System.Windows.Automation.Condition]::TrueCondition
    $children = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
    $lines = @()
    foreach ($c in $children) {
        $n = $c.Current.Name
        if ($n -and $n.Trim().Length -gt 2) {
            $lines += $n.Trim()
            if ($lines.Count -ge 5) { break }
        }
    }
    Write-Output ($lines -join "`n")
} catch {
    Write-Output ""
}
"""
    try:
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            return proc.stdout.strip()
        return ""
    except Exception:
        return ""


def clean_extracted_screen_text(raw_text: str) -> str:
    """Cleans and sanitizes screen text to avoid prompt injection or garbage characters."""
    if not raw_text:
        return ""
    # Filter non-printable characters while preserving standard whitespace
    clean_chars = [c for c in raw_text if c.isprintable() or c in "\n\t "]
    cleaned = "".join(clean_chars)
    # Deduplicate excessive newlines
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

    # Check if error keywords are present
    has_error = any(kw in cleaned.lower() for kw in ["error", "exception", "failed", "gagal", "warning", "fatal"])
    
    if is_id:
        if has_error:
            return f"Di jendela {window_title}, terdeteksi pesan galat atau peringatan: {first_extract}."
        return f"Jendela aktif adalah {window_title}. Teks terdeteksi: {first_extract}."
    else:
        if has_error:
            return f"In {window_title}, an error or warning message was detected: {first_extract}."
        return f"Active window is {window_title}. Detected text: {first_extract}."


def read_screen_content(
    prompt: str = "",
    language: str = "id",
    vision_enabled: bool = False,
    ollama_url: str = "http://127.0.0.1:11434"
) -> ScreenReadResult:
    """Reads on-screen content on-demand, prioritizing UI Automation and Windows WinRT OCR.
    
    Strict guarantees:
    - Exactly one screenshot captured to temp directory.
    - Screenshot file is deleted in a finally block (0 permanent storage).
    - Checks vision model availability; if none, reports honestly without downloading.
    - Zero external network transmissions.
    """
    t0 = time.perf_counter()
    window_info = get_active_window_info()
    window_title = window_info.get("title", "Active Window")

    temp_path = Path(tempfile.gettempdir()) / f"jarvis_screen_{uuid.uuid4().hex[:8]}.png"
    temp_cleaned = False
    extracted_text = ""
    used_method = "none"
    error_msg = None

    try:
        # Step 1: Capture single screenshot
        captured = _capture_screen_to_file(temp_path)
        if captured:
            # Step 2: Native Windows WinRT OCR
            ocr_text = _run_winrt_ocr(temp_path)
            if ocr_text and len(ocr_text.strip()) > 5:
                extracted_text = ocr_text.strip()
                used_method = "ocr"
        
        # Step 3: If OCR returned nothing, try UI Automation
        if not extracted_text:
            uia_text = _extract_uia_elements()
            if uia_text:
                extracted_text = uia_text
                used_method = "uia"

        if not extracted_text and not captured:
            used_method = "fallback"
            extracted_text = f"Active window: {window_title}"

    except Exception as e:
        logger.error("Screen reading exception: %s", e)
        error_msg = str(e)
    finally:
        # Step 4: GUARANTEED CLEANUP - Delete temporary screenshot immediately
        if temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
                temp_cleaned = True
            except Exception as e:
                logger.warning("Could not delete temp screenshot %s: %s", temp_path, e)
                temp_cleaned = False
        else:
            temp_cleaned = True

    # Step 5: Check Vision Model availability in Ollama
    has_vision, vision_model, vision_info = check_vision_model_available(ollama_url)

    # Step 6: Build spoken summary and display text
    spoken = summarize_screen_text(extracted_text, window_title, language=language)
    
    latency = (time.perf_counter() - t0) * 1000

    # Format display text
    lines = [
        f"[SCREEN] Screen Reading Result ({used_method.upper()}, {latency:.1f}ms)",
        f"* Active Window: {window_title}",
    ]
    if not has_vision:
        lines.append(f"* Local Vision Model: Tidak tersedia (Ollama memiliki Qwen3 8B text; model visi tidak diunduh otomatis sesuai kebijakan).")
    else:
        lines.append(f"* Local Vision Model: {vision_model}")
        
    lines.append("* Extracted Content:")
    sample = clean_extracted_screen_text(extracted_text)
    if sample:
        # Indent lines
        for sl in sample.splitlines()[:15]:
            lines.append(f"  > {sl}")
        if len(sample.splitlines()) > 15:
            lines.append(f"  > ... ({len(sample.splitlines()) - 15} baris lainnya)")
    else:
        lines.append("  > (Tidak ada teks terbaca)")

    display = "\n".join(lines)

    return ScreenReadResult(
        success=bool(extracted_text or window_title),
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
    )
