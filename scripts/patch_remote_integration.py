"""Automated integration script for JARVIS <-> PocketDesk Remote (D:\\Project\\remote).

Updates:
1. D:\\Project\\remote\\main.py with JARVIS bridge endpoints.
2. D:\\Project\\remote\\static\\index.html with the dedicated JARVIS Deck UI,
   mobile audio recording (16kHz PCM WAV), audio playback, and status controls.
"""

import os
import re
import ast
import sys

REMOTE_MAIN_PY = r"D:\Project\remote\main.py"
REMOTE_INDEX_HTML = r"D:\Project\remote\static\index.html"


def patch_main_py():
    print(f"Reading {REMOTE_MAIN_PY}...")
    with open(REMOTE_MAIN_PY, "r", encoding="utf-8") as f:
        content = f.read()

    if "JarvisMessageRequest" in content and "/api/jarvis/status" in content:
        print("[main.py] JARVIS endpoints already present. Skipping.")
        return

    # 1. Insert Pydantic Model
    marker_screen_click = "class ScreenClickRequest(BaseModel):"
    idx_sc = content.find(marker_screen_click)
    if idx_sc == -1:
        raise ValueError("Could not find class ScreenClickRequest in main.py")

    end_sc = content.find("\n\n# ---", idx_sc)
    if end_sc == -1:
        raise ValueError("Could not find end of ScreenClickRequest block in main.py")

    model_code = """

class JarvisMessageRequest(BaseModel):
    text: str
    audio_target: Optional[str] = "laptop"
"""
    content = content[:end_sc] + model_code + content[end_sc:]

    # 2. Insert JARVIS Endpoints
    marker_banner = "# Server Startup Banner & QR Code"
    idx_banner = content.find(marker_banner)
    if idx_banner == -1:
        raise ValueError("Could not find Server Startup Banner in main.py")

    sep = "# ---------------------------------------------------------------------------"
    idx_sep = content.rfind(sep, 0, idx_banner)
    if idx_sep == -1:
        idx_sep = idx_banner

    endpoints_code = '''# ---------------------------------------------------------------------------
# JARVIS AI Voice & Chat Integration Endpoints
# ---------------------------------------------------------------------------

JARVIS_GATEWAY_URL = "http://127.0.0.1:8765"
JARVIS_DIR = r"D:\\JARVIS"


@app.get("/api/jarvis/status")
async def api_jarvis_status():
    """Check JARVIS IPC gateway status."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{JARVIS_GATEWAY_URL}/api/status")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "online": True,
                    "model": data.get("model", "qwen3:8b"),
                    "language": data.get("language", "id"),
                    "version": data.get("version", "2.5")
                }
    except Exception:
        pass
    return {"online": False, "model": None, "language": "id", "version": None}


@app.post("/api/jarvis/start")
async def api_jarvis_start():
    """Launch JARVIS on the laptop if it is not currently running."""
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{JARVIS_GATEWAY_URL}/api/status")
            if resp.status_code == 200:
                return {"success": True, "message": "JARVIS is already running"}
    except Exception:
        pass

    bat_path = os.path.join(JARVIS_DIR, "run_gui.bat")
    if not os.path.exists(bat_path):
        return {"success": False, "error": f"Launcher not found at {bat_path}"}

    try:
        flags = subprocess.CREATE_NEW_CONSOLE if platform.system() == "Windows" else 0
        subprocess.Popen(["cmd.exe", "/c", bat_path], cwd=JARVIS_DIR, creationflags=flags)
        return {"success": True, "message": "JARVIS is starting..."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/jarvis/message")
async def api_jarvis_message(req: JarvisMessageRequest):
    """Relay text command to JARVIS Gateway."""
    cmd_text = req.text.strip()
    if not cmd_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/process",
                json={"text": cmd_text, "audio_target": req.audio_target or "laptop"}
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                return JSONResponse(status_code=resp.status_code, content=resp.json())
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="JARVIS is offline. Start JARVIS first.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/jarvis/voice")
async def api_jarvis_voice(audio: UploadFile = File(...), audio_target: str = Form("laptop")):
    """Upload voice recording from phone, transcribe using JARVIS Whisper, and process command."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio recording")

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            # 1. Transcribe via JARVIS Gateway
            transcribe_resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/transcribe",
                content=audio_bytes,
                headers={"Content-Type": "audio/wav"}
            )
            if transcribe_resp.status_code != 200:
                detail = transcribe_resp.json().get("error", "Transcription failed")
                raise HTTPException(status_code=transcribe_resp.status_code, detail=detail)

            transcription = transcribe_resp.json().get("transcription", "").strip()
            if not transcription:
                return {
                    "success": False,
                    "transcription": "",
                    "reply": "Suara tidak terdengar jelas atau terlalu hening, sir.",
                    "audio_base64": ""
                }

            # 2. Process command
            process_resp = await client.post(
                f"{JARVIS_GATEWAY_URL}/api/process",
                json={"text": transcription, "audio_target": audio_target}
            )
            data = process_resp.json()
            data["transcription"] = transcription
            return data
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="JARVIS is offline. Start JARVIS first.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


'''
    content = content[:idx_sep] + endpoints_code + content[idx_sep:]

    # Syntax test
    ast.parse(content)

    with open(REMOTE_MAIN_PY, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[main.py] Successfully updated {REMOTE_MAIN_PY}")


def patch_index_html():
    print(f"Reading {REMOTE_INDEX_HTML}...")
    with open(REMOTE_INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    if "sheet-jarvis" in html:
        print("[index.html] JARVIS UI components already present. Skipping.")
        return

    # 1. Add JARVIS quick button to header (Row 1)
    # Search for Screen Off button
    screen_off_btn = '<button onclick="screenOff()"'
    idx_screen_off = html.find(screen_off_btn)
    if idx_screen_off != -1:
        header_jarvis_btn = """<button onclick="openJarvisDeck()" class="tactile-btn h-8 px-2.5 rounded-full text-xs font-semibold text-cyan-400 gap-1.5 border border-cyan-500/30 bg-cyan-950/20 hover:bg-cyan-900/40" title="Buka JARVIS AI">
        <span id="jarvis-header-dot" class="w-2 h-2 rounded-full bg-zinc-500"></span>
        <i data-lucide="bot" class="w-3.5 h-3.5 text-cyan-400"></i>
        <span class="text-[11px] tracking-tight">JARVIS</span>
      </button>

      """
        html = html[:idx_screen_off] + header_jarvis_btn + html[idx_screen_off:]
        print("[index.html] Added JARVIS button to header bar.")

    # 2. Add JARVIS button to bottom dock (Row 5)
    # Put it right after File Drop button or before Pesan
    drop_btn_marker = "<!-- 4. File Drop -->"
    idx_drop = html.find(drop_btn_marker)
    if idx_drop != -1:
        # Find closing tag of drop button
        idx_drop_end = html.find("</button>", idx_drop)
        if idx_drop_end != -1:
            idx_drop_end += len("</button>")
            dock_jarvis_btn = """

      <!-- JARVIS AI Voice & Chat -->
      <button onclick="openJarvisDeck()" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex-col gap-0.5 text-cyan-400 hover:text-white bg-cyan-950/30 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)]" title="JARVIS AI Voice & Chat Assistant">
        <i data-lucide="bot" class="w-4 h-4 text-cyan-400"></i>
        <span class="text-[9px] font-bold tracking-tight text-cyan-300">JARVIS</span>
      </button>"""
            html = html[:idx_drop_end] + dock_jarvis_btn + html[idx_drop_end:]
            print("[index.html] Added JARVIS button to bottom action dock.")

    # 3. Add sheet-jarvis modal bottom sheet
    # Insert right before modal-power
    marker_power = '<!-- MODAL 6: POWER & SYSTEM CONTROLS'
    idx_power = html.find(marker_power)
    if idx_power == -1:
        marker_power = '<div id="modal-power"'
        idx_power = html.find(marker_power)

    if idx_power == -1:
        raise ValueError("Could not find modal-power insertion point in index.html")

    sheet_jarvis_html = '''<!-- =================================================================== -->
  <!-- MODAL / BOTTOM SHEET: JARVIS AI VOICE & CHAT ASSISTANT -->
  <!-- =================================================================== -->
  <div id="sheet-jarvis" class="sheet-modal fixed inset-0 z-50 bg-black/85 backdrop-blur-md hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#141416] border-t sm:border border-cyan-500/30 rounded-t-3xl sm:rounded-2xl p-4 shadow-[0_0_35px_rgba(6,182,212,0.18)] flex flex-col gap-3 animate-sheet-up max-h-[90dvh] overflow-hidden">
      
      <!-- JARVIS Header -->
      <div class="flex items-center justify-between border-b border-[#242426] pb-2 shrink-0">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
            <i data-lucide="bot" class="w-3.5 h-3.5 text-cyan-400"></i>
          </div>
          <div>
            <h3 class="text-sm font-bold text-white tracking-wide">JARVIS AI</h3>
            <p id="jarvis-deck-subtitle" class="text-[9px] text-cyan-400/80 font-mono">Local Assistant</p>
          </div>
        </div>
        
        <div class="flex items-center gap-2">
          <!-- Status Pill -->
          <span id="jarvis-deck-badge" class="px-2 py-0.5 text-[10px] rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700 flex items-center gap-1 font-mono">
            <span class="w-1.5 h-1.5 rounded-full bg-zinc-400"></span> Memeriksa...
          </span>
          <!-- Close Button -->
          <button onclick="closeSheet('sheet-jarvis')" class="tactile-btn w-7 h-7 rounded-full text-remote-muted hover:text-white">
            <i data-lucide="x" class="w-4 h-4"></i>
          </button>
        </div>
      </div>

      <!-- Offline Wake Alert Banner (Hidden if Online) -->
      <div id="jarvis-offline-banner" class="hidden p-2.5 rounded-xl bg-red-950/40 border border-red-500/30 flex items-center justify-between gap-2 shrink-0">
        <div class="flex items-center gap-2 text-xs text-red-200">
          <i data-lucide="alert-triangle" class="w-4 h-4 text-red-400 shrink-0"></i>
          <span class="text-[11px] leading-tight">JARVIS di laptop sedang nonaktif.</span>
        </div>
        <button onclick="startJarvisFromPhone()" id="jarvis-start-btn" class="tactile-btn px-2.5 py-1.5 rounded-lg text-[10px] font-bold bg-red-500/20 hover:bg-red-500/40 border border-red-500/40 text-red-100 flex items-center gap-1 shrink-0">
          <i data-lucide="zap" class="w-3 h-3 text-amber-300"></i>
          <span>Nyalakan</span>
        </button>
      </div>

      <!-- Audio Output Target Selector -->
      <div class="flex items-center justify-between bg-[#19191d] p-1.5 rounded-xl border border-[#2b2b32] shrink-0">
        <span class="text-[10px] text-remote-muted font-medium ml-1">Suara Jawaban:</span>
        <div class="flex items-center gap-1">
          <button onclick="setJarvisAudioTarget('laptop')" id="target-btn-laptop" class="px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="speaker" class="w-3 h-3"></i>
            <span>Laptop</span>
          </button>
          <button onclick="setJarvisAudioTarget('phone')" id="target-btn-phone" class="px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-[#121214] text-zinc-400 border border-transparent hover:text-white flex items-center gap-1">
            <i data-lucide="smartphone" class="w-3 h-3"></i>
            <span>HP</span>
          </button>
        </div>
      </div>

      <!-- Scrollable Chat Bubble Log -->
      <div id="jarvis-chat-log" class="flex-1 min-h-[170px] max-h-[36dvh] overflow-y-auto space-y-2.5 p-2.5 rounded-xl bg-[#0e0e11] border border-[#222228] text-xs">
        <!-- Default Welcome Message -->
        <div class="flex gap-2 items-start">
          <div class="w-5 h-5 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="bot" class="w-3 h-3 text-cyan-400"></i>
          </div>
          <div class="bg-[#181820] border border-[#2a2a35] text-zinc-200 rounded-2xl rounded-tl-sm px-3 py-2 leading-relaxed shadow-sm">
            Halo sir! JARVIS siap menerima instruksi suara atau teks langsung dari smartphone Anda.
          </div>
        </div>
      </div>

      <!-- Quick Suggestion Chips -->
      <div class="flex items-center gap-1.5 overflow-x-auto pb-1 shrink-0 scrollbar-none text-[10px]">
        <button onclick="sendJarvisPreset('Buka Chrome')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#1b1b22] border border-[#2e2e3a] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          🌐 Chrome
        </button>
        <button onclick="sendJarvisPreset('Putar musik')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#1b1b22] border border-[#2e2e3a] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          🎵 Musik
        </button>
        <button onclick="sendJarvisPreset('Info sistem')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#1b1b22] border border-[#2e2e3a] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          ⚡ Info Spek
        </button>
        <button onclick="sendJarvisPreset('Ambil tangkapan layar')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#1b1b22] border border-[#2e2e3a] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          📸 Screenshot
        </button>
        <button onclick="sendJarvisPreset('Volume 50%')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#1b1b22] border border-[#2e2e3a] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          🔊 Vol 50%
        </button>
      </div>

      <!-- Voice Push-To-Talk Button & Recording HUD -->
      <div class="flex flex-col items-center justify-center gap-1.5 pt-1 shrink-0">
        <div id="jarvis-voice-status" class="text-[11px] font-mono text-remote-muted h-4 flex items-center gap-1">
          <span>Tahan atau ketuk mic untuk bicara</span>
        </div>

        <div class="flex items-center justify-center w-full gap-3">
          <!-- Voice Button -->
          <button id="jarvis-mic-btn" class="tactile-btn w-14 h-14 rounded-full bg-[#1a1a24] border-2 border-cyan-500/40 text-cyan-400 shadow-[0_0_18px_rgba(6,182,212,0.2)] active:scale-95 transition-all flex items-center justify-center relative select-none">
            <span id="jarvis-mic-glow" class="absolute inset-0 rounded-full border-2 border-cyan-400 animate-ping opacity-0 pointer-events-none"></span>
            <i id="jarvis-mic-icon" data-lucide="mic" class="w-6 h-6"></i>
          </button>
        </div>
      </div>

      <!-- Text Input & Send Row -->
      <div class="flex items-center gap-1.5 pt-1 border-t border-[#222228] shrink-0">
        <div class="relative flex-1">
          <input id="jarvis-text-input" type="text" placeholder="Ketik perintah ke JARVIS..." class="w-full bg-[#101014] border border-[#2b2b35] rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-cyan-400 pr-7 font-medium" onkeydown="if(event.key==='Enter') sendJarvisText();">
          <button onclick="document.getElementById('jarvis-text-input').value=''" class="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white">
            <i data-lucide="x" class="w-3 h-3"></i>
          </button>
        </div>
        <button onclick="sendJarvisText()" id="jarvis-send-btn" class="tactile-btn w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/30 flex items-center justify-center shrink-0">
          <i data-lucide="send" class="w-4 h-4"></i>
        </button>
      </div>

    </div>
  </div>

  '''

    html = html[:idx_power] + sheet_jarvis_html + html[idx_power:]
    print("[index.html] Added sheet-jarvis modal bottom sheet.")

    # 4. Add JARVIS JavaScript Engine at the end of the script tag
    end_script_marker = "window.addEventListener('DOMContentLoaded', () => {"
    idx_dom = html.find(end_script_marker)
    if idx_dom == -1:
        raise ValueError("Could not find DOMContentLoaded in index.html")

    jarvis_js_code = '''
    // =========================================================================
    // JARVIS AI ASSISTANT CLIENT ENGINE (Speech + Text + Phone TTS Routing)
    // =========================================================================
    let jarvisAudioTarget = 'laptop'; // 'laptop' | 'phone'
    let jarvisIsRecording = false;
    let jarvisAudioContext = null;
    let jarvisMediaStream = null;
    let jarvisAudioProcessor = null;
    let jarvisAudioChunks = [];
    let jarvisLastStatus = false;

    function openJarvisDeck() {
      openSheet('sheet-jarvis');
      checkJarvisStatus();
    }

    function setJarvisAudioTarget(target) {
      haptic(15);
      jarvisAudioTarget = target;
      const btnLaptop = document.getElementById('target-btn-laptop');
      const btnPhone = document.getElementById('target-btn-phone');
      if (target === 'phone') {
        btnPhone.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1';
        btnLaptop.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-[#121214] text-zinc-400 border border-transparent hover:text-white flex items-center gap-1';
        showToast('Suara JARVIS akan diputar di HP ini', 'info');
      } else {
        btnLaptop.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1';
        btnPhone.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-[#121214] text-zinc-400 border border-transparent hover:text-white flex items-center gap-1';
        showToast('Suara JARVIS diputar di laptop', 'info');
      }
      if (window.lucide) lucide.createIcons();
    }

    async function checkJarvisStatus() {
      try {
        const res = await apiGet('/api/jarvis/status');
        const badge = document.getElementById('jarvis-deck-badge');
        const headerDot = document.getElementById('jarvis-header-dot');
        const banner = document.getElementById('jarvis-offline-banner');
        const subtitle = document.getElementById('jarvis-deck-subtitle');

        if (res && res.online) {
          jarvisLastStatus = true;
          if (badge) {
            badge.className = 'px-2 py-0.5 text-[10px] rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-mono';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> ONLINE';
          }
          if (headerDot) {
            headerDot.className = 'w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]';
          }
          if (banner) banner.classList.add('hidden');
          if (subtitle && res.model) subtitle.innerText = `Model: ${res.model}`;
        } else {
          jarvisLastStatus = false;
          if (badge) {
            badge.className = 'px-2 py-0.5 text-[10px] rounded-full bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1 font-mono';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-red-400"></span> OFFLINE';
          }
          if (headerDot) {
            headerDot.className = 'w-2 h-2 rounded-full bg-zinc-500';
          }
          if (banner) banner.classList.remove('hidden');
          if (subtitle) subtitle.innerText = 'Offline (Laptop)';
        }
      } catch (e) {
        console.warn('Failed checking JARVIS status:', e);
      }
    }

    async function startJarvisFromPhone() {
      haptic(25);
      const btn = document.getElementById('jarvis-start-btn');
      if (btn) btn.innerHTML = '<i data-lucide="loader" class="w-3 h-3 animate-spin"></i><span>Memulai...</span>';
      if (window.lucide) lucide.createIcons();
      showToast('Menyalakan JARVIS di laptop...', 'info');

      try {
        const res = await apiPost('/api/jarvis/start');
        if (res && res.success) {
          showToast('JARVIS sedang booting di laptop!', 'success');
          setTimeout(checkJarvisStatus, 3000);
          setTimeout(checkJarvisStatus, 6000);
        } else {
          showToast(res.error || 'Gagal menyalakan JARVIS', 'error');
        }
      } catch (err) {
        showToast('Gagal menghubungi backend', 'error');
      } finally {
        if (btn) btn.innerHTML = '<i data-lucide="zap" class="w-3 h-3 text-amber-300"></i><span>Nyalakan</span>';
        if (window.lucide) lucide.createIcons();
      }
    }

    function appendJarvisBubble(sender, text) {
      const log = document.getElementById('jarvis-chat-log');
      if (!log) return;

      const bubbleWrap = document.createElement('div');
      bubbleWrap.className = 'flex gap-2 items-start' + (sender === 'user' ? ' justify-end' : '');

      if (sender === 'user') {
        bubbleWrap.innerHTML = `
          <div class="bg-cyan-600/30 border border-cyan-500/40 text-cyan-100 rounded-2xl rounded-tr-sm px-3 py-2 leading-relaxed max-w-[85%] shadow-sm font-medium">
            ${escapeHtml(text)}
          </div>
          <div class="w-5 h-5 rounded-full bg-cyan-500/30 border border-cyan-500/50 flex items-center justify-center shrink-0 mt-0.5 text-[10px] text-cyan-200">
            <i data-lucide="user" class="w-3 h-3"></i>
          </div>
        `;
      } else {
        bubbleWrap.innerHTML = `
          <div class="w-5 h-5 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="bot" class="w-3 h-3 text-cyan-400"></i>
          </div>
          <div class="bg-[#181820] border border-[#2a2a35] text-zinc-200 rounded-2xl rounded-tl-sm px-3 py-2 leading-relaxed max-w-[85%] shadow-sm">
            ${escapeHtml(text)}
          </div>
        `;
      }

      log.appendChild(bubbleWrap);
      log.scrollTop = log.scrollHeight;
      if (window.lucide) lucide.createIcons();
    }

    function escapeHtml(str) {
      return (str || '').replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
      });
    }

    function playBase64Wav(b64Data) {
      try {
        const byteCharacters = atob(b64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        audio.play().catch(e => console.warn('Mobile audio play error:', e));
      } catch (e) {
        console.error('Failed to decode/play base64 WAV:', e);
      }
    }

    async function sendJarvisPreset(text) {
      const input = document.getElementById('jarvis-text-input');
      if (input) input.value = text;
      await sendJarvisText();
    }

    async function sendJarvisText() {
      const input = document.getElementById('jarvis-text-input');
      const text = input ? input.value.trim() : '';
      if (!text) return;

      input.value = '';
      haptic(20);
      appendJarvisBubble('user', text);

      const statusEl = document.getElementById('jarvis-voice-status');
      if (statusEl) statusEl.innerHTML = '<span class="text-cyan-400 animate-pulse font-semibold">JARVIS sedang berpikir...</span>';

      try {
        const res = await apiPost('/api/jarvis/message', {
          text: text,
          audio_target: jarvisAudioTarget
        });

        if (res && res.reply) {
          appendJarvisBubble('jarvis', res.reply);
          if (jarvisAudioTarget === 'phone' && res.audio_base64) {
            playBase64Wav(res.audio_base64);
          }
        } else if (res && res.error) {
          appendJarvisBubble('jarvis', `Error: ${res.error}`);
        } else {
          appendJarvisBubble('jarvis', 'Perintah berhasil dikirim ke JARVIS.');
        }
      } catch (err) {
        appendJarvisBubble('jarvis', `Koneksi gagal: ${err.message}`);
      } finally {
        if (statusEl) statusEl.innerHTML = '<span>Tahan atau ketuk mic untuk bicara</span>';
      }
    }

    // --- Web Audio 16kHz PCM WAV Microphone Pipeline ---
    function encode16kMonoWav(samples, sampleRate) {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);

      function writeString(offset, string) {
        for (let i = 0; i < string.length; i++) {
          view.setUint8(offset + i, string.charCodeAt(i));
        }
      }

      writeString(0, 'RIFF');
      view.setUint32(4, 36 + samples.length * 2, true);
      writeString(8, 'WAVE');
      writeString(12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true); // PCM format
      view.setUint16(22, 1, true); // 1 channel (mono)
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeString(36, 'data');
      view.setUint32(40, samples.length * 2, true);

      let offset = 44;
      for (let i = 0; i < samples.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      }

      return new Blob([view], { type: 'audio/wav' });
    }

    async function startJarvisRecording() {
      if (jarvisIsRecording) return;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true
          }
        });

        jarvisMediaStream = stream;
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        jarvisAudioContext = new AudioContextClass({ sampleRate: 16000 });
        const source = jarvisAudioContext.createMediaStreamSource(stream);
        jarvisAudioProcessor = jarvisAudioContext.createScriptProcessor(4096, 1, 1);
        jarvisAudioChunks = [];

        jarvisAudioProcessor.onaudioprocess = (e) => {
          if (!jarvisIsRecording) return;
          const inputData = e.inputBuffer.getChannelData(0);
          jarvisAudioChunks.push(new Float32Array(inputData));
        };

        source.connect(jarvisAudioProcessor);
        jarvisAudioProcessor.connect(jarvisAudioContext.destination);

        jarvisIsRecording = true;
        haptic(35);

        // Visual update
        const glow = document.getElementById('jarvis-mic-glow');
        const micBtn = document.getElementById('jarvis-mic-btn');
        const statusEl = document.getElementById('jarvis-voice-status');

        if (glow) glow.classList.remove('opacity-0');
        if (micBtn) {
          micBtn.classList.remove('border-cyan-500/40', 'text-cyan-400');
          micBtn.classList.add('border-red-500', 'text-red-400', 'bg-red-950/30');
        }
        if (statusEl) {
          statusEl.innerHTML = '<span class="text-red-400 animate-pulse font-bold flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span> Merekam suara... Lepas untuk mengirim</span>';
        }
      } catch (err) {
        console.error('Microphone access denied:', err);
        showToast('Izin mikrofon diperlukan: ' + err.message, 'error');
      }
    }

    async function stopJarvisRecording() {
      if (!jarvisIsRecording) return;
      jarvisIsRecording = false;
      haptic(20);

      const glow = document.getElementById('jarvis-mic-glow');
      const micBtn = document.getElementById('jarvis-mic-btn');
      const statusEl = document.getElementById('jarvis-voice-status');

      if (glow) glow.classList.add('opacity-0');
      if (micBtn) {
        micBtn.classList.add('border-cyan-500/40', 'text-cyan-400');
        micBtn.classList.remove('border-red-500', 'text-red-400', 'bg-red-950/30');
      }
      if (statusEl) {
        statusEl.innerHTML = '<span class="text-cyan-400 animate-pulse font-semibold">Mengirim & mentranskripsi suara...</span>';
      }

      // Cleanup stream
      if (jarvisAudioProcessor) {
        try { jarvisAudioProcessor.disconnect(); } catch (e) {}
      }
      if (jarvisAudioContext) {
        try { jarvisAudioContext.close(); } catch (e) {}
      }
      if (jarvisMediaStream) {
        jarvisMediaStream.getTracks().forEach(t => t.stop());
      }

      // Flatten audio chunks
      let totalLength = 0;
      for (const chunk of jarvisAudioChunks) totalLength += chunk.length;
      if (totalLength < 1600) {
        if (statusEl) statusEl.innerHTML = '<span>Rekaman terlalu singkat</span>';
        setTimeout(() => {
          if (statusEl) statusEl.innerHTML = '<span>Tahan atau ketuk mic untuk bicara</span>';
        }, 1500);
        return;
      }

      const mergedSamples = new Float32Array(totalLength);
      let offset = 0;
      for (const chunk of jarvisAudioChunks) {
        mergedSamples.set(chunk, offset);
        offset += chunk.length;
      }

      const wavBlob = encode16kMonoWav(mergedSamples, 16000);
      const formData = new FormData();
      formData.append('audio', wavBlob, 'recording.wav');
      formData.append('audio_target', jarvisAudioTarget);

      try {
        const res = await fetch('/api/jarvis/voice', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();

        if (data.transcription) {
          appendJarvisBubble('user', data.transcription);
        }
        if (data.reply) {
          appendJarvisBubble('jarvis', data.reply);
        } else if (data.response) {
          appendJarvisBubble('jarvis', data.response);
        }
        if (jarvisAudioTarget === 'phone' && data.audio_base64) {
          playBase64Wav(data.audio_base64);
        }
      } catch (err) {
        appendJarvisBubble('jarvis', `Gagal memproses suara: ${err.message}`);
      } finally {
        if (statusEl) statusEl.innerHTML = '<span>Tahan atau ketuk mic untuk bicara</span>';
      }
    }

    function setupJarvisMicListeners() {
      const btn = document.getElementById('jarvis-mic-btn');
      if (!btn) return;

      // Mobile Touch events for Push-to-Talk
      btn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startJarvisRecording();
      }, { passive: false });

      btn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopJarvisRecording();
      }, { passive: false });

      btn.addEventListener('touchcancel', (e) => {
        e.preventDefault();
        stopJarvisRecording();
      }, { passive: false });

      // Desktop Click / Hold events
      let mousePressed = false;
      btn.addEventListener('mousedown', (e) => {
        mousePressed = true;
        startJarvisRecording();
      });
      window.addEventListener('mouseup', () => {
        if (mousePressed) {
          mousePressed = false;
          stopJarvisRecording();
        }
      });
    }

'''

    html = html[:idx_dom] + jarvis_js_code + html[idx_dom:]

    # Also register checkJarvisStatus and setupJarvisMicListeners in DOMContentLoaded
    dom_init_marker = "setupModalScreenTouch();"
    idx_dom_init = html.find(dom_init_marker)
    if idx_dom_init != -1:
        idx_dom_init += len(dom_init_marker)
        dom_jarvis_calls = """
      setupJarvisMicListeners();
      checkJarvisStatus();
      setInterval(checkJarvisStatus, 5000);"""
        html = html[:idx_dom_init] + dom_jarvis_calls + html[idx_dom_init:]
        print("[index.html] Registered JARVIS setup and status polling in DOMContentLoaded.")

    with open(REMOTE_INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[index.html] Successfully updated {REMOTE_INDEX_HTML}")


if __name__ == "__main__":
    patch_main_py()
    patch_index_html()
    print("ALL PATCHES APPLIED SUCCESSFULLY!")
