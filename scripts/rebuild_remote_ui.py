"""Rebuild PocketDesk Remote (D:\\Project\\remote\\static\\index.html) into an authentic tactile hardware remote.

Features:
1. Native Two-Deck Switcher (Zero-Modal, Zero Touch Glitches):
   - [ 🎮 REMOT HARDWARE ]
   - [ 🤖 JARVIS AI ]
2. Real Physical Remote Layout:
   - Tactile Circular D-Pad Navigation Ring (Up, Down, Left, Right, OK, Back, Win).
   - Compact Virtual Trackpad & Clicks (shrunk from 200px to ~64px).
   - Real Tactile Dual Rockers (Volume +/- and Brightness +/-).
   - Tactile Media & System Quick Keys (Alt+Tab, F11, Ctrl+W, Desktop).
3. JARVIS AI Deck:
   - Full live synced chat log with laptop screen.
   - Prominent glowing Push-To-Talk Mic button (16kHz PCM WAV).
   - Audio routing toggle: [ 🔊 Laptop ] (with laptop speaker TTS) vs [ 📱 HP ].
   - Preset chips and text input with send button.
   - Status badge and 1-tap "Nyalakan JARVIS" if offline.
"""

import os

INDEX_PATH = r"D:\Project\remote\static\index.html"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="id" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
  <title>PocketDesk Remote v2.5 // JARVIS</title>

  <!-- Google Fonts: Inter & JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Lucide Icons CDN -->
  <script src="https://unpkg.com/lucide@latest"></script>

  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            remote: {
              body: '#0f0f11',
              chassis: '#16161a',
              surface: '#1f1f26',
              surfaceHover: '#2a2a35',
              border: '#2e2e3a',
              borderLight: '#3f3f50',
              accent: '#d97757',
              accentHover: '#e28567',
              cyan: '#06b6d4',
              text: '#f3f4f6',
              muted: '#9ca3af',
              dim: '#6b7280',
            }
          }
        }
      }
    }
  </script>

  <style>
    * {
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
      margin: 0;
      padding: 0;
    }

    html, body {
      height: 100dvh;
      width: 100%;
      overflow: hidden;
      background-color: #09090b;
      color: #f3f4f6;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      user-select: none;
      -webkit-user-select: none;
      touch-action: manipulation;
    }

    input, textarea {
      user-select: text;
      -webkit-user-select: text;
    }

    /* Tactile hardware button styles */
    .tactile-btn {
      background: linear-gradient(180deg, #24242e 0%, #17171d 100%);
      border-top: 1px solid rgba(255, 255, 255, 0.12);
      border-bottom: 2px solid rgba(0, 0, 0, 0.7);
      box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05), 0 2px 4px rgba(0, 0, 0, 0.5);
      transition: all 0.08s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }

    .tactile-btn:active {
      transform: scale(0.94);
      background: linear-gradient(180deg, #16161c 0%, #101014 100%);
      border-top: 1px solid rgba(255, 255, 255, 0.04);
      border-bottom: 1px solid rgba(0, 0, 0, 0.85);
      box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.7);
      filter: brightness(0.95);
    }

    /* Primary Accent Button */
    .tactile-btn-accent {
      background: linear-gradient(180deg, #e28567 0%, #c96545 100%);
      border-top: 1px solid rgba(255, 255, 255, 0.25);
      border-bottom: 2px solid rgba(0, 0, 0, 0.6);
      box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.15), 0 2px 6px rgba(217, 119, 87, 0.35);
      color: #ffffff;
      transition: all 0.08s ease;
    }

    .tactile-btn-accent:active {
      transform: scale(0.94);
      background: linear-gradient(180deg, #c96545 0%, #ab5033 100%);
      box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
    }

    /* Danger / Power Button */
    .tactile-btn-danger {
      background: linear-gradient(180deg, rgba(239, 68, 68, 0.25) 0%, rgba(185, 28, 28, 0.3) 100%);
      border: 1px solid rgba(239, 68, 68, 0.5);
      border-top: 1px solid rgba(255, 120, 120, 0.4);
      color: #f87171;
      box-shadow: 0 0 12px rgba(239, 68, 68, 0.2);
      transition: all 0.08s ease;
    }

    .tactile-btn-danger:active {
      transform: scale(0.92);
      background: rgba(239, 68, 68, 0.4);
    }

    /* Cyan AI Button */
    .tactile-btn-cyan {
      background: linear-gradient(180deg, rgba(6, 182, 212, 0.25) 0%, rgba(14, 116, 144, 0.3) 100%);
      border: 1px solid rgba(6, 182, 212, 0.5);
      border-top: 1px solid rgba(103, 232, 249, 0.45);
      color: #67e8f9;
      box-shadow: 0 0 12px rgba(6, 182, 212, 0.25);
      transition: all 0.08s ease;
    }

    .tactile-btn-cyan:active {
      transform: scale(0.92);
      background: rgba(6, 182, 212, 0.4);
    }

    /* Trackpad Textured Surface */
    .trackpad-surface {
      background-color: #121217;
      background-image: radial-gradient(rgba(255, 255, 255, 0.12) 1px, transparent 1px);
      background-size: 14px 14px;
      touch-action: none;
      box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.7);
    }

    /* Animations */
    @keyframes sheetUp {
      from { transform: translateY(100%); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .animate-sheet-up {
      animation: sheetUp 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    /* Scrollbar styling */
    ::-webkit-scrollbar {
      width: 4px;
      height: 4px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: #333340;
      border-radius: 2px;
    }
  </style>
</head>
<body class="flex items-center justify-center bg-[#070709]">

  <!-- =================================================================== -->
  <!-- MAIN HARDWARE REMOTE CHASSIS (100dvh Zero-Scroll) -->
  <!-- =================================================================== -->
  <div class="h-[100dvh] w-full max-w-sm mx-auto flex flex-col justify-between p-2.5 sm:p-3 overflow-hidden select-none bg-[#111115] border-x border-[#23232c] shadow-[0_0_50px_rgba(0,0,0,0.8)] relative">

    <!-- ----------------------------------------------------------------- -->
    <!-- ROW 1: TOP HARDWARE BAR (Status, Host IP, Baterai, Power) -->
    <!-- ----------------------------------------------------------------- -->
    <header class="flex items-center justify-between shrink-0 h-9 px-1">
      <div class="flex items-center gap-1.5">
        <a href="/" onclick="haptic(15)" class="tactile-btn w-7 h-7 rounded-lg text-remote-muted hover:text-white" title="Scan QR Code / Ganti Host">
          <i data-lucide="qr-code" class="w-3.5 h-3.5"></i>
        </a>

        <!-- LED Status + Info -->
        <div class="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#17171d] border border-[#282833]">
          <span id="led-indicator" class="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
          <span id="led-label" class="text-[9px] font-mono text-remote-muted font-medium">Connecting</span>
        </div>

        <!-- Baterai Laptop -->
        <div id="bat-box" class="hidden items-center gap-1 text-[10px] font-mono text-emerald-400 bg-[#17171d] border border-[#282833] px-2 py-0.5 rounded-full">
          <i data-lucide="battery-charging" class="w-3 h-3"></i>
          <span id="bat-text">--%</span>
        </div>
      </div>

      <div class="flex items-center gap-1.5">
        <!-- Screen Off -->
        <button onclick="screenOff()" class="tactile-btn h-7 px-2.5 rounded-full text-xs font-medium text-amber-400 gap-1 border border-amber-500/25" title="Matikan Lampu Layar Laptop">
          <i data-lucide="monitor-off" class="w-3 h-3 text-amber-400"></i>
          <span class="text-[10px] tracking-tight">Screen</span>
        </button>

        <!-- Tombol Bulat Power Merah -->
        <button onclick="openPowerModal()" class="tactile-btn tactile-btn-danger w-7 h-7 rounded-full" title="Menu Daya & Sistem">
          <i data-lucide="power" class="w-3.5 h-3.5"></i>
        </button>
      </div>
    </header>

    <!-- ----------------------------------------------------------------- -->
    <!-- ROW 2: TACTILE SEGMENTED DECK SWITCHER (Zero-Modal / Instant Switch) -->
    <!-- ----------------------------------------------------------------- -->
    <div class="flex items-center bg-[#15151a] p-1 rounded-xl border border-[#262632] shadow-inner shrink-0 my-1">
      <button id="tab-btn-remote" onclick="switchDeck('remote')" class="flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 bg-[#252530] text-white shadow-md border border-white/10">
        <i data-lucide="gamepad-2" class="w-3.5 h-3.5 text-remote-accent"></i>
        <span>REMOT PC</span>
      </button>
      <button id="tab-btn-jarvis" onclick="switchDeck('jarvis')" class="flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white">
        <span id="tab-jarvis-dot" class="w-2 h-2 rounded-full bg-zinc-500"></span>
        <i data-lucide="bot" class="w-3.5 h-3.5 text-cyan-400"></i>
        <span>JARVIS AI</span>
      </button>
    </div>

    <!-- ================================================================= -->
    <!-- DECK 1: AUTHENTIC HARDWARE REMOTE CONTROLLER (Full Physical Remote) -->
    <!-- ================================================================= -->
    <div id="deck-remote" class="flex-1 flex flex-col justify-between overflow-hidden my-0.5">

      <!-- 1. TOP QUICK FUNCTION ROW -->
      <div class="grid grid-cols-4 gap-1.5 shrink-0 my-0.5">
        <button onclick="pressKey('esc')" class="tactile-btn h-7 rounded-lg text-[10px] font-mono font-semibold text-rose-400" title="Escape">
          ESC
        </button>
        <button onclick="sendShortcut('win')" class="tactile-btn h-7 rounded-lg text-[10px] font-mono font-semibold text-blue-400" title="Windows Key">
          ⊞ WIN
        </button>
        <button onclick="sendShortcut('alt_tab')" class="tactile-btn h-7 rounded-lg text-[10px] font-mono font-semibold text-amber-400" title="Ganti Aplikasi">
          ALT+TAB
        </button>
        <button onclick="volumeMute()" class="tactile-btn h-7 rounded-lg text-[10px] font-mono font-semibold text-emerald-400" title="Mute/Unmute Audio">
          <i data-lucide="volume-x" class="w-3 h-3"></i>
        </button>
      </div>

      <!-- 2. CIRCULAR HARDWARE D-PAD DIRECTIONAL RING (Centerpiece of Remote) -->
      <div class="flex items-center justify-center my-1 shrink-0">
        <div class="relative w-44 h-44 flex items-center justify-center">
          <!-- Outer Circular Ring Background -->
          <div class="absolute inset-0 rounded-full bg-[#181820] border-2 border-[#2b2b38] shadow-[inset_0_2px_8px_rgba(0,0,0,0.8),0_4px_12px_rgba(0,0,0,0.6)]"></div>

          <!-- D-Pad UP Button -->
          <button onclick="pressKey('up')" class="tactile-btn absolute top-1.5 w-12 h-11 rounded-t-2xl rounded-b-md text-white hover:text-remote-accent" title="Atas (Arrow Up)">
            <i data-lucide="chevron-up" class="w-6 h-6"></i>
          </button>

          <!-- D-Pad DOWN Button -->
          <button onclick="pressKey('down')" class="tactile-btn absolute bottom-1.5 w-12 h-11 rounded-b-2xl rounded-t-md text-white hover:text-remote-accent" title="Bawah (Arrow Down)">
            <i data-lucide="chevron-down" class="w-6 h-6"></i>
          </button>

          <!-- D-Pad LEFT Button -->
          <button onclick="pressKey('left')" class="tactile-btn absolute left-1.5 w-11 h-12 rounded-l-2xl rounded-r-md text-white hover:text-remote-accent" title="Kiri (Arrow Left)">
            <i data-lucide="chevron-left" class="w-6 h-6"></i>
          </button>

          <!-- D-Pad RIGHT Button -->
          <button onclick="pressKey('right')" class="tactile-btn absolute right-1.5 w-11 h-12 rounded-r-2xl rounded-l-md text-white hover:text-remote-accent" title="Kanan (Arrow Right)">
            <i data-lucide="chevron-right" class="w-6 h-6"></i>
          </button>

          <!-- Center OK Button (Enter / Select) -->
          <button onclick="pressKey('enter')" class="tactile-btn tactile-btn-accent z-10 w-14 h-14 rounded-full text-xs font-extrabold uppercase tracking-widest shadow-xl flex items-center justify-center border-2 border-white/20 active:scale-95" title="OK / Enter">
            OK
          </button>
        </div>
      </div>

      <!-- 3. COMPACT VIRTUAL TOUCHPAD (Shrunk to ~60px, Clean & Non-Intrusive) -->
      <div class="shrink-0 my-0.5 space-y-1">
        <div class="relative h-16 w-full rounded-xl overflow-hidden border border-[#2b2b36] bg-[#141418] flex">
          
          <!-- Trackpad Surface -->
          <div id="touchpad-area" class="flex-1 h-full trackpad-surface flex items-center justify-center cursor-crosshair relative">
            <div class="pointer-events-none flex items-center gap-1.5 opacity-35">
              <i data-lucide="mouse-pointer-2" class="w-3.5 h-3.5 text-white"></i>
              <span class="text-[9px] tracking-wider font-mono text-white">TOUCHPAD STRIP</span>
            </div>
          </div>

          <!-- Vertical Scroll Strip (1-Thumb) -->
          <div id="scroll-strip" class="w-6 h-full bg-[#181820] border-l border-white/5 flex flex-col items-center justify-between py-1 cursor-ns-resize touch-none z-10 hover:bg-[#22222c] transition-colors" title="Geser 1 Jempol Naik/Turun untuk Scroll">
            <i data-lucide="chevron-up" class="w-3 h-3 text-white/30 shrink-0"></i>
            <div class="w-0.5 h-3.5 rounded-full bg-remote-accent/60"></div>
            <i data-lucide="chevron-down" class="w-3 h-3 text-white/30 shrink-0"></i>
          </div>
        </div>

        <!-- Physical Mouse Clicks (Left & Right) -->
        <div class="grid grid-cols-2 gap-1.5 h-8">
          <button onclick="mouseClick('left')" class="tactile-btn h-full rounded-lg text-[10px] font-bold text-remote-text gap-1">
            <i data-lucide="mouse" class="w-3 h-3 text-remote-accent"></i>
            <span>KLIK KIRI</span>
          </button>
          <button onclick="mouseClick('right')" class="tactile-btn h-full rounded-lg text-[10px] font-bold text-remote-muted gap-1">
            <span>KLIK KANAN</span>
            <i data-lucide="corner-down-right" class="w-3 h-3 text-remote-dim"></i>
          </button>
        </div>
      </div>

      <!-- 4. HARDWARE ROCKERS & MEDIA DECK -->
      <div class="grid grid-cols-4 gap-1.5 shrink-0 my-0.5 h-24">
        
        <!-- Volume Rocker (Column 1) -->
        <div class="col-span-1 bg-[#16161d] p-1 rounded-xl border border-[#292936] flex flex-col justify-between items-center shadow-inner">
          <button onclick="volumeStep(5)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-remote-accent">
            <i data-lucide="plus" class="w-3.5 h-3.5"></i>
          </button>
          <div class="flex flex-col items-center my-0.5">
            <span class="text-[8px] font-mono text-remote-muted uppercase tracking-wider">VOL</span>
            <span id="vol-level-text" class="text-[10px] font-mono font-bold text-white">--%</span>
          </div>
          <button onclick="volumeStep(-5)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-remote-accent">
            <i data-lucide="minus" class="w-3.5 h-3.5"></i>
          </button>
        </div>

        <!-- Center Media & App Controls (Columns 2 & 3) -->
        <div class="col-span-2 flex flex-col justify-between gap-1">
          <!-- Media Buttons -->
          <div class="grid grid-cols-3 gap-1 h-11">
            <button onclick="mediaAction('prev')" class="tactile-btn h-full rounded-lg text-white" title="Lagu Sebelumnya">
              <i data-lucide="skip-back" class="w-4 h-4"></i>
            </button>
            <button onclick="mediaAction('playpause')" class="tactile-btn tactile-btn-accent h-full rounded-lg text-white shadow-md" title="Putar / Jeda">
              <i data-lucide="play" class="w-4 h-4 fill-current"></i>
            </button>
            <button onclick="mediaAction('next')" class="tactile-btn h-full rounded-lg text-white" title="Lagu Berikutnya">
              <i data-lucide="skip-forward" class="w-4 h-4"></i>
            </button>
          </div>

          <!-- Quick App & Screen Launchers -->
          <div class="grid grid-cols-2 gap-1 h-11">
            <button onclick="openBrowser('https://www.google.com')" class="tactile-btn h-full rounded-lg text-[10px] font-semibold text-white gap-1 bg-gradient-to-r from-blue-950/40 to-sky-950/40 border border-sky-500/30" title="Buka Google Chrome">
              <i data-lucide="chrome" class="w-3.5 h-3.5 text-sky-400"></i>
              <span>Chrome</span>
            </button>
            <button onclick="sendShortcut('win_d')" class="tactile-btn h-full rounded-lg text-[10px] font-semibold text-white gap-1 bg-[#1c1c24]" title="Tampilkan Desktop">
              <i data-lucide="layout-grid" class="w-3.5 h-3.5 text-amber-400"></i>
              <span>Desktop</span>
            </button>
          </div>
        </div>

        <!-- Brightness Rocker (Column 4) -->
        <div class="col-span-1 bg-[#16161d] p-1 rounded-xl border border-[#292936] flex flex-col justify-between items-center shadow-inner">
          <button onclick="brightnessStep(10)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-amber-400">
            <i data-lucide="sun-medium" class="w-3.5 h-3.5"></i>
          </button>
          <div class="flex flex-col items-center my-0.5">
            <span class="text-[8px] font-mono text-remote-muted uppercase tracking-wider">BRT</span>
            <span id="brt-level-text" class="text-[10px] font-mono font-bold text-amber-300">--%</span>
          </div>
          <button onclick="brightnessStep(-10)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-amber-400">
            <i data-lucide="sun-dim" class="w-3.5 h-3.5"></i>
          </button>
        </div>

      </div>

      <!-- 5. BOTTOM SHORTCUT PILLS -->
      <div class="grid grid-cols-3 gap-1.5 shrink-0 my-0.5">
        <button onclick="sendShortcut('f11')" class="tactile-btn h-7 rounded-lg text-[10px] font-mono text-zinc-300" title="Layar Penuh">
          F11 Fullscreen
        </button>
        <button onclick="sendShortcut('ctrl_w')" class="tactile-btn h-7 rounded-lg text-[10px] font-mono text-rose-400" title="Tutup Tab">
          Ctrl+W Close
        </button>
        <button onclick="openSheet('sheet-peek')" class="tactile-btn h-7 rounded-lg text-[10px] font-mono text-emerald-400 gap-1" title="Lihat Layar Laptop">
          <i data-lucide="eye" class="w-3 h-3"></i>
          <span>Peek Screen</span>
        </button>
      </div>

    </div>


    <!-- ================================================================= -->
    <!-- DECK 2: DEDICATED JARVIS AI VOICE & CHAT DECK (Synced to Laptop) -->
    <!-- ================================================================= -->
    <div id="deck-jarvis" class="hidden flex-1 flex flex-col justify-between overflow-hidden my-0.5 gap-1.5 animate-sheet-up">
      
      <!-- JARVIS Subheader (Model & Status) -->
      <div class="flex items-center justify-between bg-[#15151c] px-3 py-1.5 rounded-xl border border-[#272733] shrink-0">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
            <i data-lucide="bot" class="w-3.5 h-3.5 text-cyan-400"></i>
          </div>
          <div>
            <h4 class="text-xs font-bold text-white tracking-wide">JARVIS ASSISTANT</h4>
            <p id="jarvis-model-sub" class="text-[9px] text-cyan-400 font-mono">Sync Real-Time Laptop</p>
          </div>
        </div>

        <div class="flex items-center gap-1.5">
          <span id="jarvis-status-badge" class="px-2 py-0.5 text-[9px] rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700 flex items-center gap-1 font-mono">
            <span class="w-1.5 h-1.5 rounded-full bg-zinc-400"></span> Memeriksa...
          </span>
        </div>
      </div>

      <!-- Offline Wake Alert Banner (Hidden if Online) -->
      <div id="jarvis-offline-banner" class="hidden p-2 rounded-xl bg-red-950/40 border border-red-500/30 flex items-center justify-between gap-2 shrink-0">
        <div class="flex items-center gap-1.5 text-xs text-red-200">
          <i data-lucide="alert-triangle" class="w-4 h-4 text-red-400 shrink-0"></i>
          <span class="text-[10px] leading-tight">JARVIS laptop sedang offline.</span>
        </div>
        <button onclick="startJarvisFromPhone()" id="jarvis-start-btn" class="tactile-btn px-2.5 py-1 rounded-lg text-[10px] font-bold bg-red-500/20 hover:bg-red-500/40 border border-red-500/40 text-red-100 flex items-center gap-1 shrink-0">
          <i data-lucide="zap" class="w-3 h-3 text-amber-300"></i>
          <span>Nyalakan</span>
        </button>
      </div>

      <!-- Audio Output Target Selector -->
      <div class="flex items-center justify-between bg-[#15151c] px-2.5 py-1 rounded-xl border border-[#272733] shrink-0">
        <span class="text-[10px] text-zinc-400 font-medium">Output Suara:</span>
        <div class="flex items-center gap-1">
          <button onclick="setJarvisAudioTarget('laptop')" id="target-btn-laptop" class="px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="speaker" class="w-3 h-3"></i>
            <span>Speaker Laptop</span>
          </button>
          <button onclick="setJarvisAudioTarget('phone')" id="target-btn-phone" class="px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-[#121216] text-zinc-400 border border-transparent hover:text-white flex items-center gap-1">
            <i data-lucide="smartphone" class="w-3 h-3"></i>
            <span>Speaker HP</span>
          </button>
        </div>
      </div>

      <!-- LIVE CHAT BUBBLE LOG (Synced with Laptop Screen) -->
      <div id="jarvis-chat-log" class="flex-1 min-h-[140px] max-h-[38dvh] overflow-y-auto space-y-2 p-2 rounded-xl bg-[#0d0d12] border border-[#22222d] text-xs">
        <!-- Default Welcome Message -->
        <div class="flex gap-2 items-start">
          <div class="w-5 h-5 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="bot" class="w-3 h-3 text-cyan-400"></i>
          </div>
          <div class="bg-[#181822] border border-[#2b2b3a] text-zinc-200 rounded-2xl rounded-tl-sm px-3 py-1.5 leading-relaxed shadow-sm">
            Halo sir! JARVIS siap menerima instruksi suara atau teks dari HP ini dan langsung disinkronkan ke layar laptop Anda.
          </div>
        </div>
      </div>

      <!-- Quick Command Chips -->
      <div class="flex items-center gap-1 overflow-x-auto pb-0.5 shrink-0 scrollbar-none text-[10px]">
        <button onclick="sendJarvisPreset('Buka Chrome')" class="tactile-btn shrink-0 px-2 py-0.5 rounded-full bg-[#1c1c26] border border-[#2f2f3e] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          🌐 Chrome
        </button>
        <button onclick="sendJarvisPreset('Putar musik')" class="tactile-btn shrink-0 px-2 py-0.5 rounded-full bg-[#1c1c26] border border-[#2f2f3e] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          🎵 Musik
        </button>
        <button onclick="sendJarvisPreset('Info sistem')" class="tactile-btn shrink-0 px-2 py-0.5 rounded-full bg-[#1c1c26] border border-[#2f2f3e] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          ⚡ Info Spek
        </button>
        <button onclick="sendJarvisPreset('Ambil tangkapan layar')" class="tactile-btn shrink-0 px-2 py-0.5 rounded-full bg-[#1c1c26] border border-[#2f2f3e] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          📸 Screenshot
        </button>
        <button onclick="sendJarvisPreset('Volume 50%')" class="tactile-btn shrink-0 px-2 py-0.5 rounded-full bg-[#1c1c26] border border-[#2f2f3e] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          🔊 Vol 50%
        </button>
        <button onclick="sendJarvisPreset('Daftar tugas')" class="tactile-btn shrink-0 px-2 py-0.5 rounded-full bg-[#1c1c26] border border-[#2f2f3e] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40">
          📝 Todo
        </button>
      </div>

      <!-- Push-To-Talk Voice Button & Status Indicator -->
      <div class="flex flex-col items-center justify-center gap-1 shrink-0 pt-0.5">
        <div id="jarvis-voice-status" class="text-[10px] font-mono text-zinc-400 h-3.5 flex items-center justify-center gap-1">
          <span>Tahan mic untuk bicara (Whisper AI)</span>
        </div>

        <button id="jarvis-mic-btn" class="tactile-btn tactile-btn-cyan w-13 h-13 rounded-full text-cyan-300 relative select-none shadow-[0_0_20px_rgba(6,182,212,0.3)] active:scale-95 transition-all flex items-center justify-center p-3.5">
          <span id="jarvis-mic-glow" class="absolute inset-0 rounded-full border-2 border-cyan-400 animate-ping opacity-0 pointer-events-none"></span>
          <i id="jarvis-mic-icon" data-lucide="mic" class="w-6 h-6"></i>
        </button>
      </div>

      <!-- Text Input & Send Row -->
      <div class="flex items-center gap-1.5 pt-1 border-t border-[#232330] shrink-0">
        <div class="relative flex-1">
          <input id="jarvis-text-input" type="text" placeholder="Ketik perintah ke JARVIS..." class="w-full bg-[#13131a] border border-[#2b2b3a] rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-cyan-400 pr-7 font-medium" onkeydown="if(event.key==='Enter') sendJarvisText();">
          <button onclick="document.getElementById('jarvis-text-input').value=''" class="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white">
            <i data-lucide="x" class="w-3 h-3"></i>
          </button>
        </div>
        <button onclick="sendJarvisText()" id="jarvis-send-btn" class="tactile-btn tactile-btn-cyan w-9 h-9 rounded-xl flex items-center justify-center shrink-0">
          <i data-lucide="send" class="w-4 h-4"></i>
        </button>
      </div>

    </div>

    <!-- ----------------------------------------------------------------- -->
    <!-- ROW 6: BOTTOM ACTION DOCK (6 Tombol Pembuka Deck & Sheet) -->
    <!-- ----------------------------------------------------------------- -->
    <footer class="shrink-0 h-13 bg-[#15151a] rounded-2xl border border-[#262632] p-1 flex items-center justify-between shadow-2xl mt-1">
      
      <!-- 1. Remot Deck Button -->
      <button onclick="switchDeck('remote')" id="dock-btn-remote" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex-col gap-0.5 text-remote-accent font-semibold" title="Kontrol Hardware Remot">
        <i data-lucide="gamepad-2" class="w-4 h-4"></i>
        <span class="text-[9px] tracking-tight">Remot</span>
      </button>

      <!-- 2. JARVIS AI Deck Button -->
      <button onclick="switchDeck('jarvis')" id="dock-btn-jarvis" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex-col gap-0.5 text-cyan-400 font-semibold" title="JARVIS AI Voice & Chat">
        <i data-lucide="bot" class="w-4 h-4 text-cyan-400"></i>
        <span class="text-[9px] tracking-tight text-cyan-300">JARVIS</span>
      </button>

      <!-- 3. Keyboard Sheet -->
      <button onclick="openSheet('sheet-keyboard')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex-col gap-0.5 text-remote-muted hover:text-white" title="Ketik Teks & Clipboard">
        <i data-lucide="keyboard" class="w-4 h-4 text-sky-400"></i>
        <span class="text-[9px] tracking-tight">Ketik</span>
      </button>

      <!-- 4. Peek Screen Sheet -->
      <button onclick="openSheet('sheet-peek')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex-col gap-0.5 text-remote-muted hover:text-white" title="Intip Layar Laptop">
        <i data-lucide="eye" class="w-4 h-4 text-emerald-400"></i>
        <span class="text-[9px] tracking-tight">Peek</span>
      </button>

      <!-- 5. File Drop Sheet -->
      <button onclick="openSheet('sheet-drop')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex-col gap-0.5 text-remote-muted hover:text-white" title="Kirim Berkas ke Laptop">
        <i data-lucide="folder-up" class="w-4 h-4 text-purple-400"></i>
        <span class="text-[9px] tracking-tight">Drop</span>
      </button>

      <!-- 6. Play & Cari Sheet -->
      <button onclick="openSheet('sheet-search')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex-col gap-0.5 text-remote-muted hover:text-white" title="Pencarian YouTube & Google">
        <i data-lucide="search" class="w-4 h-4 text-amber-400"></i>
        <span class="text-[9px] tracking-tight">Cari</span>
      </button>
    </footer>

  </div>


  <!-- =================================================================== -->
  <!-- FLOATING TOAST HUD -->
  <!-- =================================================================== -->
  <div id="toast-container" class="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-1.5 w-11/12 max-w-xs pointer-events-none"></div>


  <!-- =================================================================== -->
  <!-- MODAL 1: SMART SEARCH (YouTube / Google) -->
  <!-- =================================================================== -->
  <div id="sheet-search" class="sheet-modal fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#18181f] border-t sm:border border-[#333344] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3.5 animate-sheet-up max-h-[85dvh] overflow-y-auto">
      
      <div class="flex items-center justify-between border-b border-[#2a2a38] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="search" class="w-4 h-4 text-amber-400"></i>
          <h3 class="text-sm font-bold text-white">Putar & Cari Pintar</h3>
        </div>
        <button onclick="closeSheet('sheet-search')" class="tactile-btn w-7 h-7 rounded-full text-remote-muted">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="space-y-1.5">
        <label class="text-[11px] text-remote-muted font-medium">Kueri / Judul Lagu / Pencarian:</label>
        <div class="relative">
          <input id="smart-query-input" type="text" placeholder="Ketik apa saja..." class="w-full bg-[#121217] border border-[#333344] rounded-xl px-3 py-2.5 text-xs text-white placeholder-remote-dim outline-none focus:border-amber-400 pr-8 font-medium">
          <button onclick="document.getElementById('smart-query-input').value=''" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-remote-dim hover:text-white">
            <i data-lucide="x" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <button onclick="handleSmartPlayYouTube()" class="tactile-btn tactile-btn-accent h-10 rounded-xl text-xs font-semibold gap-1.5">
          <i data-lucide="play" class="w-4 h-4 fill-current"></i>
          <span>Play YouTube</span>
        </button>
        <button onclick="handleSmartSearchGoogle()" class="tactile-btn h-10 rounded-xl text-xs font-semibold gap-1.5 text-white">
          <i data-lucide="globe" class="w-4 h-4 text-sky-400"></i>
          <span>Google Search</span>
        </button>
      </div>

    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 2: KEYBOARD & CLIPBOARD SYNC -->
  <!-- =================================================================== -->
  <div id="sheet-keyboard" class="sheet-modal fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#18181f] border-t sm:border border-[#333344] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3.5 animate-sheet-up max-h-[85dvh] overflow-y-auto">
      
      <div class="flex items-center justify-between border-b border-[#2a2a38] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="keyboard" class="w-4 h-4 text-sky-400"></i>
          <h3 class="text-sm font-bold text-white">Remote Keyboard & Clipboard</h3>
        </div>
        <button onclick="closeSheet('sheet-keyboard')" class="tactile-btn w-7 h-7 rounded-full text-remote-muted">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="space-y-1.5">
        <label class="text-[11px] text-remote-muted font-medium">Ketik Langsung ke Laptop:</label>
        <div class="flex gap-2">
          <input id="keyboard-type-input" type="text" placeholder="Ketik kalimat di sini..." class="flex-1 bg-[#121217] border border-[#333344] rounded-xl px-3 py-2 text-xs text-white placeholder-remote-dim outline-none focus:border-sky-400 font-medium" onkeydown="if(event.key==='Enter') sendTypedText();">
          <button onclick="sendTypedText()" class="tactile-btn h-9 px-3 rounded-xl text-xs font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30">
            Kirim
          </button>
        </div>
      </div>

      <!-- Quick Virtual Keys -->
      <div class="grid grid-cols-4 gap-1.5 pt-1">
        <button onclick="pressKey('enter')" class="tactile-btn h-9 rounded-xl text-xs font-semibold text-white">
          ↵ Enter
        </button>
        <button onclick="pressKey('backspace')" class="tactile-btn h-9 rounded-xl text-xs font-semibold text-white">
          ⌫ Back
        </button>
        <button onclick="pressKey('space')" class="tactile-btn h-9 rounded-xl text-xs font-semibold text-white">
          ␣ Spasi
        </button>
        <button onclick="pressKey('tab')" class="tactile-btn h-9 rounded-xl text-xs font-semibold text-white">
          ⇥ Tab
        </button>
      </div>

      <!-- Clipboard Sync -->
      <div class="pt-2 border-t border-[#2a2a38] flex gap-2">
        <button onclick="sendClipboardToLaptop()" class="tactile-btn flex-1 h-9 rounded-xl text-xs font-medium text-white gap-1.5">
          <i data-lucide="clipboard-copy" class="w-3.5 h-3.5 text-sky-400"></i>
          <span>Kirim Clipboard</span>
        </button>
        <button onclick="getClipboardFromLaptop()" class="tactile-btn flex-1 h-9 rounded-xl text-xs font-medium text-white gap-1.5">
          <i data-lucide="clipboard-paste" class="w-3.5 h-3.5 text-emerald-400"></i>
          <span>Ambil Clipboard</span>
        </button>
      </div>

    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 3: SCREEN PEEK (Enlarged Screen Viewer) -->
  <!-- =================================================================== -->
  <div id="sheet-peek" class="sheet-modal fixed inset-0 z-50 bg-black/85 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#18181f] border-t sm:border border-[#333344] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3 animate-sheet-up max-h-[85dvh] overflow-y-auto">
      
      <div class="flex items-center justify-between border-b border-[#2a2a38] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="eye" class="w-4 h-4 text-emerald-400"></i>
          <h3 class="text-sm font-bold text-white">Intip Layar Laptop</h3>
        </div>
        <button onclick="closeSheet('sheet-peek')" class="tactile-btn w-7 h-7 rounded-full text-remote-muted">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="w-full aspect-video bg-black rounded-xl overflow-hidden border border-[#333344] flex items-center justify-center relative">
        <img id="peek-img" src="" alt="Layar Laptop" class="w-full h-full object-contain" />
        <div id="peek-loader" class="absolute inset-0 flex items-center justify-center bg-black/60 text-xs text-remote-muted">
          <i data-lucide="loader" class="w-5 h-5 animate-spin mr-2"></i> Memuat gambar...
        </div>
      </div>

      <div class="flex gap-2">
        <button onclick="refreshScreenshot()" class="tactile-btn flex-1 h-9 rounded-xl text-xs font-medium text-white gap-1.5">
          <i data-lucide="refresh-cw" class="w-3.5 h-3.5 text-emerald-400"></i>
          <span>Refresh Snapshot</span>
        </button>
      </div>

    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 4: FILE DROP -->
  <!-- =================================================================== -->
  <div id="sheet-drop" class="sheet-modal fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#18181f] border-t sm:border border-[#333344] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3.5 animate-sheet-up max-h-[85dvh] overflow-y-auto">
      
      <div class="flex items-center justify-between border-b border-[#2a2a38] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="folder-up" class="w-4 h-4 text-purple-400"></i>
          <h3 class="text-sm font-bold text-white">Kirim Berkas ke Laptop</h3>
        </div>
        <button onclick="closeSheet('sheet-drop')" class="tactile-btn w-7 h-7 rounded-full text-remote-muted">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="space-y-2">
        <input type="file" id="drop-file-input" class="w-full text-xs text-remote-muted file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-purple-500/20 file:text-purple-300 hover:file:bg-purple-500/30" />
        <button onclick="uploadDropFile()" class="tactile-btn tactile-btn-accent w-full h-10 rounded-xl text-xs font-bold gap-1.5">
          <i data-lucide="upload" class="w-4 h-4"></i>
          <span>Unggah Berkas</span>
        </button>
        <button onclick="apiPost('/api/files/open-folder')" class="tactile-btn w-full h-9 rounded-xl text-xs font-medium text-white gap-1.5">
          <i data-lucide="folder-open" class="w-3.5 h-3.5 text-amber-400"></i>
          <span>Buka Folder Drop di Laptop</span>
        </button>
      </div>

    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 5: POWER & SYSTEM CONTROLS -->
  <!-- =================================================================== -->
  <div id="modal-power" class="sheet-modal fixed inset-0 z-50 bg-black/85 backdrop-blur-sm hidden flex items-center justify-center p-4">
    <div class="w-full max-w-xs bg-[#18181f] border border-[#333344] rounded-2xl p-4 shadow-2xl space-y-3 animate-sheet-up">
      
      <div class="flex items-center justify-between border-b border-[#2a2a38] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="power" class="w-4 h-4 text-red-500"></i>
          <h3 class="text-sm font-bold text-white">Kontrol Daya Laptop</h3>
        </div>
        <button onclick="closePowerModal()" class="tactile-btn w-7 h-7 rounded-full text-remote-muted">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="grid grid-cols-1 gap-2">
        <button onclick="powerAction('lock')" class="tactile-btn h-10 rounded-xl text-xs font-semibold gap-2 text-white">
          <i data-lucide="lock" class="w-4 h-4 text-amber-400"></i>
          <span>Kunci Laptop (Lock)</span>
        </button>
        <button onclick="powerAction('sleep')" class="tactile-btn h-10 rounded-xl text-xs font-semibold gap-2 text-white">
          <i data-lucide="moon" class="w-4 h-4 text-sky-400"></i>
          <span>Tidur (Sleep)</span>
        </button>
        <button onclick="powerAction('shutdown')" class="tactile-btn tactile-btn-danger h-10 rounded-xl text-xs font-bold gap-2">
          <i data-lucide="power" class="w-4 h-4"></i>
          <span>Matikan Laptop (Shutdown 15s)</span>
        </button>
        <button onclick="powerAction('cancel-shutdown')" class="tactile-btn h-9 rounded-xl text-xs font-medium text-emerald-400 border border-emerald-500/30">
          Batalkan Shutdown
        </button>
      </div>

    </div>
  </div>


  <!-- =================================================================== -->
  <!-- CLIENT JAVASCRIPT ENGINE -->
  <!-- =================================================================== -->
  <script>
    // Audio / Haptic Helpers
    function haptic(ms = 15) {
      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate(ms);
      }
    }

    // Toast HUD
    function showToast(message, type = 'info') {
      const container = document.getElementById('toast-container');
      if (!container) return;
      const toast = document.createElement('div');

      const icons = {
        success: 'check-circle-2',
        error: 'alert-circle',
        info: 'info',
        warning: 'alert-triangle'
      };

      const colors = {
        success: 'border-emerald-500/40 text-emerald-300 bg-[#171720]',
        error: 'border-red-500/40 text-red-300 bg-[#171720]',
        info: 'border-remote-accent/40 text-white bg-[#171720]',
        warning: 'border-amber-500/40 text-amber-300 bg-[#171720]'
      };

      toast.className = `p-2.5 rounded-xl border text-xs shadow-xl flex items-center gap-2 backdrop-blur-md transition-all duration-200 pointer-events-auto transform translate-y-2 opacity-0 ${colors[type] || colors.info}`;
      toast.innerHTML = `<i data-lucide="${icons[type] || 'info'}" class="w-3.5 h-3.5 shrink-0"></i><span class="truncate">${message}</span>`;

      container.appendChild(toast);
      if (window.lucide) lucide.createIcons();

      requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
      });

      setTimeout(() => {
        toast.classList.add('opacity-0');
        setTimeout(() => toast.remove(), 250);
      }, 2400);
    }

    // Modal Sheet Helpers
    function openSheet(id) {
      haptic(20);
      document.querySelectorAll('.sheet-modal').forEach(m => {
        m.classList.add('hidden');
        m.classList.remove('flex');
      });
      const el = document.getElementById(id);
      if (el) {
        el.classList.remove('hidden');
        el.classList.add('flex');
        if (id === 'sheet-peek') refreshScreenshot();
      }
      if (window.lucide) lucide.createIcons();
    }

    function closeSheet(id) {
      haptic(15);
      const el = document.getElementById(id);
      if (el) {
        el.classList.add('hidden');
        el.classList.remove('flex');
      }
    }

    function openPowerModal() {
      haptic(30);
      const el = document.getElementById('modal-power');
      if (el) {
        el.classList.remove('hidden');
        el.classList.add('flex');
      }
      if (window.lucide) lucide.createIcons();
    }

    function closePowerModal() {
      haptic(15);
      const el = document.getElementById('modal-power');
      if (el) {
        el.classList.add('hidden');
        el.classList.remove('flex');
      }
    }

    // --- DECK SWITCHER (Zero-Modal / Native View Switch) ---
    function switchDeck(deck) {
      haptic(20);
      const remoteDeck = document.getElementById('deck-remote');
      const jarvisDeck = document.getElementById('deck-jarvis');
      const btnRemote = document.getElementById('tab-btn-remote');
      const btnJarvis = document.getElementById('tab-btn-jarvis');
      const dockRemote = document.getElementById('dock-btn-remote');
      const dockJarvis = document.getElementById('dock-btn-jarvis');

      if (deck === 'jarvis') {
        remoteDeck.classList.add('hidden');
        jarvisDeck.classList.remove('hidden');

        btnJarvis.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 shadow-sm';
        btnRemote.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white';

        if (dockJarvis) dockJarvis.classList.add('text-cyan-400');
        if (dockRemote) dockRemote.classList.remove('text-remote-accent');
        checkJarvisStatus();
      } else {
        jarvisDeck.classList.add('hidden');
        remoteDeck.classList.remove('hidden');

        btnRemote.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 bg-[#252530] text-white shadow-md border border-white/10';
        btnJarvis.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white';

        if (dockRemote) dockRemote.classList.add('text-remote-accent');
        if (dockJarvis) dockJarvis.classList.remove('text-cyan-400');
      }
      if (window.lucide) lucide.createIcons();
    }

    // REST API Helpers
    async function apiPost(endpoint, body = {}) {
      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        return await res.json();
      } catch (err) {
        showToast('Koneksi ke laptop terputus', 'error');
        return { success: false, error: err.message };
      }
    }

    async function apiGet(endpoint) {
      try {
        const res = await fetch(endpoint);
        return await res.json();
      } catch (err) {
        return { success: false, error: err.message };
      }
    }

    // Remote Actions
    async function pressKey(key) {
      haptic(20);
      await apiPost('/api/keyboard/key', { key });
    }

    async function sendShortcut(shortcut) {
      haptic(25);
      const res = await apiPost('/api/shortcut', { shortcut });
      if (res && res.success) {
        showToast(`${shortcut.replace('_', ' ').toUpperCase()}`, 'info');
      }
    }

    async function mouseClick(button) {
      haptic(15);
      await apiPost('/api/mouse/click', { button });
    }

    async function screenOff() {
      haptic(30);
      showToast('Mematikan layar laptop...', 'info');
      await apiPost('/api/screen-off');
    }

    async function volumeStep(delta) {
      haptic(15);
      const res = await apiPost('/api/volume/step', { delta });
      if (res && res.level !== undefined) {
        const text = document.getElementById('vol-level-text');
        if (text) text.innerText = `${res.level}%`;
      }
    }

    async function volumeMute() {
      haptic(20);
      const res = await apiPost('/api/volume/mute');
      if (res) {
        showToast(res.muted ? 'Audio Senyap (Muted)' : 'Audio Aktif', 'info');
      }
    }

    async function brightnessStep(delta) {
      haptic(15);
      const res = await apiPost('/api/brightness', { delta });
      if (res && res.level !== undefined) {
        const text = document.getElementById('brt-level-text');
        if (text) text.innerText = `${res.level}%`;
      }
    }

    async function mediaAction(action) {
      haptic(20);
      await apiPost(`/api/media/${action}`);
    }

    async function openBrowser(url) {
      haptic(20);
      showToast('Membuka browser di laptop...', 'info');
      await apiPost('/api/browser/open', { url });
    }

    async function powerAction(action) {
      haptic(40);
      closePowerModal();
      const res = await apiPost(`/api/power/${action}`);
      if (res && res.success) {
        showToast(`Daya: ${action.toUpperCase()}`, 'warning');
      }
    }

    // WebSocket Touchpad Stream
    let socket = null;
    function initWebSocket() {
      const loc = window.location;
      const wsProtocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${loc.host}/ws/touchpad`;

      try {
        socket = new WebSocket(wsUrl);
        socket.onopen = () => {
          const led = document.getElementById('led-indicator');
          const label = document.getElementById('led-label');
          if (led) led.className = 'w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]';
          if (label) {
            label.innerText = 'ONLINE';
            label.className = 'text-[9px] font-mono text-emerald-400 font-semibold';
          }
        };
        socket.onclose = () => {
          const led = document.getElementById('led-indicator');
          const label = document.getElementById('led-label');
          if (led) led.className = 'w-2 h-2 rounded-full bg-amber-500 animate-pulse';
          if (label) {
            label.innerText = 'RECONNECT';
            label.className = 'text-[9px] font-mono text-amber-400 font-semibold';
          }
          setTimeout(initWebSocket, 2000);
        };
      } catch (e) {
        console.warn('WS Init failed:', e);
      }
    }

    function setupTouchpad() {
      const pad = document.getElementById('touchpad-area');
      if (!pad) return;

      let lastX = 0, lastY = 0;
      let startX = 0, startY = 0;
      let startTime = 0;
      let hasMoved = false;

      pad.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
          const touch = e.touches[0];
          lastX = touch.clientX;
          lastY = touch.clientY;
          startX = touch.clientX;
          startY = touch.clientY;
          startTime = Date.now();
          hasMoved = false;
        }
      }, { passive: true });

      pad.addEventListener('touchmove', (e) => {
        if (e.touches.length === 1) {
          const touch = e.touches[0];
          const dx = (touch.clientX - lastX) * 1.6;
          const dy = (touch.clientY - lastY) * 1.6;
          lastX = touch.clientX;
          lastY = touch.clientY;

          if (Math.abs(touch.clientX - startX) > 4 || Math.abs(touch.clientY - startY) > 4) {
            hasMoved = true;
          }

          if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'move', dx: Math.round(dx), dy: Math.round(dy) }));
          }
        }
      }, { passive: true });

      pad.addEventListener('touchend', (e) => {
        const duration = Date.now() - startTime;
        if (!hasMoved && duration < 250) {
          mouseClick('left');
        }
      });
    }

    function setupScrollStrip() {
      const strip = document.getElementById('scroll-strip');
      if (!strip) return;
      let lastY = 0;

      strip.addEventListener('touchstart', (e) => {
        lastY = e.touches[0].clientY;
      }, { passive: true });

      strip.addEventListener('touchmove', (e) => {
        const currentY = e.touches[0].clientY;
        const delta = currentY - lastY;
        if (Math.abs(delta) > 8) {
          lastY = currentY;
          const scrollUnits = delta > 0 ? 80 : -80;
          if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'scroll', dy: scrollUnits }));
          } else {
            apiPost('/api/mouse/scroll', { direction: scrollUnits > 0 ? 'up' : 'down', amount: 80 });
          }
        }
      }, { passive: true });
    }

    async function loadSystemStatus() {
      try {
        const res = await apiGet('/api/status');
        if (res && res.battery !== undefined) {
          const batBox = document.getElementById('bat-box');
          const batText = document.getElementById('bat-text');
          if (batBox && batText) {
            batBox.classList.remove('hidden');
            batBox.classList.add('flex');
            batText.innerText = `${res.battery}%`;
          }
        }
        if (res && res.volume !== undefined) {
          const text = document.getElementById('vol-level-text');
          if (text) text.innerText = `${res.volume}%`;
        }
        if (res && res.brightness !== undefined) {
          const text = document.getElementById('brt-level-text');
          if (text) text.innerText = `${res.brightness}%`;
        }
      } catch (e) {}
    }

    // Modal Helpers: Peek, Drop, Search, Keyboard
    async function refreshScreenshot() {
      const img = document.getElementById('peek-img');
      const loader = document.getElementById('peek-loader');
      if (loader) loader.classList.remove('hidden');
      try {
        const res = await apiGet('/api/screen/peek');
        if (res && res.image && img) {
          img.src = `data:image/jpeg;base64,${res.image}`;
        }
      } catch (e) {
      } finally {
        if (loader) loader.classList.add('hidden');
      }
    }

    async function uploadDropFile() {
      const input = document.getElementById('drop-file-input');
      if (!input || !input.files || input.files.length === 0) {
        showToast('Pilih berkas terlebih dahulu', 'warning');
        return;
      }
      const file = input.files[0];
      const formData = new FormData();
      formData.append('file', file);
      showToast(`Mengunggah ${file.name}...`, 'info');

      try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data && data.success) {
          showToast('Berkas berhasil disimpan di folder PocketDesk Drop!', 'success');
          input.value = '';
          closeSheet('sheet-drop');
        } else {
          showToast(data.error || 'Gagal mengunggah', 'error');
        }
      } catch (err) {
        showToast('Gagal mengunggah berkas', 'error');
      }
    }

    async function sendTypedText() {
      const input = document.getElementById('keyboard-type-input');
      const text = input ? input.value : '';
      if (!text) return;
      haptic(15);
      await apiPost('/api/keyboard/type', { text });
      input.value = '';
      showToast('Teks terkirim ke laptop', 'info');
    }

    async function sendClipboardToLaptop() {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          await apiPost('/api/clipboard/send', { text });
          showToast('Clipboard HP dikirim ke laptop', 'success');
        }
      } catch (e) {
        showToast('Izin baca clipboard ditolak', 'error');
      }
    }

    async function getClipboardFromLaptop() {
      try {
        const res = await apiGet('/api/clipboard/get');
        if (res && res.text) {
          await navigator.clipboard.writeText(res.text);
          showToast('Teks disalin ke HP!', 'success');
        }
      } catch (e) {
        showToast('Gagal mengambil clipboard', 'error');
      }
    }

    async function handleSmartPlayYouTube() {
      const input = document.getElementById('smart-query-input');
      const query = input ? input.value.trim() : '';
      if (!query) return;
      haptic(20);
      closeSheet('sheet-search');
      showToast(`Memutar: ${query}...`, 'info');
      await apiPost('/api/youtube/play', { query });
    }

    async function handleSmartSearchGoogle() {
      const input = document.getElementById('smart-query-input');
      const query = input ? input.value.trim() : '';
      if (!query) return;
      haptic(20);
      closeSheet('sheet-search');
      showToast(`Mencari Google: ${query}...`, 'info');
      await apiPost('/api/browser/search', { query });
    }


    // =========================================================================
    // JARVIS AI ASSISTANT CLIENT ENGINE (Live Synced with Laptop Screen & Speaker)
    // =========================================================================
    let jarvisAudioTarget = 'laptop'; // 'laptop' | 'phone'
    let jarvisIsRecording = false;
    let jarvisAudioContext = null;
    let jarvisMediaStream = null;
    let jarvisAudioProcessor = null;
    let jarvisAudioChunks = [];

    function setJarvisAudioTarget(target) {
      haptic(15);
      jarvisAudioTarget = target;
      const btnLaptop = document.getElementById('target-btn-laptop');
      const btnPhone = document.getElementById('target-btn-phone');

      if (target === 'phone') {
        if (btnPhone) btnPhone.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1';
        if (btnLaptop) btnLaptop.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-[#121216] text-zinc-400 border border-transparent hover:text-white flex items-center gap-1';
        showToast('Suara JARVIS keluar di HP ini', 'info');
      } else {
        if (btnLaptop) btnLaptop.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1';
        if (btnPhone) btnPhone.className = 'px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all bg-[#121216] text-zinc-400 border border-transparent hover:text-white flex items-center gap-1';
        showToast('Suara JARVIS dibacakan di speaker laptop', 'info');
      }
      if (window.lucide) lucide.createIcons();
    }

    async function checkJarvisStatus() {
      try {
        const res = await apiGet('/api/jarvis/status');
        const badge = document.getElementById('jarvis-status-badge');
        const tabDot = document.getElementById('tab-jarvis-dot');
        const banner = document.getElementById('jarvis-offline-banner');
        const sub = document.getElementById('jarvis-model-sub');

        if (res && res.online) {
          if (badge) {
            badge.className = 'px-2 py-0.5 text-[9px] rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-mono';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> ONLINE';
          }
          if (tabDot) tabDot.className = 'w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]';
          if (banner) banner.classList.add('hidden');
          if (sub && res.model) sub.innerText = `Online: ${res.model} (Sync Aktif)`;
        } else {
          if (badge) {
            badge.className = 'px-2 py-0.5 text-[9px] rounded-full bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1 font-mono';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-red-400"></span> OFFLINE';
          }
          if (tabDot) tabDot.className = 'w-2 h-2 rounded-full bg-zinc-500';
          if (banner) banner.classList.remove('hidden');
          if (sub) sub.innerText = 'Offline di Laptop';
        }
      } catch (e) {}
    }

    async function startJarvisFromPhone() {
      haptic(25);
      const btn = document.getElementById('jarvis-start-btn');
      if (btn) btn.innerHTML = '<i data-lucide="loader" class="w-3 h-3 animate-spin"></i><span>Memulai...</span>';
      if (window.lucide) lucide.createIcons();
      showToast('Meluncurkan JARVIS di laptop...', 'info');

      try {
        const res = await apiPost('/api/jarvis/start');
        if (res && res.success) {
          showToast('JARVIS sedang diluncurkan di laptop!', 'success');
          setTimeout(checkJarvisStatus, 2500);
          setTimeout(checkJarvisStatus, 5000);
        } else {
          showToast(res.error || 'Gagal memulai JARVIS', 'error');
        }
      } catch (err) {
        showToast('Koneksi backend gagal', 'error');
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
          <div class="bg-cyan-600/30 border border-cyan-500/40 text-cyan-100 rounded-2xl rounded-tr-sm px-3 py-1.5 leading-relaxed max-w-[85%] shadow-sm font-medium">
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
          <div class="bg-[#181822] border border-[#2b2b3a] text-zinc-200 rounded-2xl rounded-tl-sm px-3 py-1.5 leading-relaxed max-w-[85%] shadow-sm">
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
        audio.play().catch(e => console.warn('Audio play error:', e));
      } catch (e) {
        console.error('Failed base64 audio:', e);
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
      if (statusEl) statusEl.innerHTML = '<span class="text-cyan-400 animate-pulse font-semibold">JARVIS sedang memproses di laptop...</span>';

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
          appendJarvisBubble('jarvis', `Perhatian: ${res.error}`);
        } else {
          appendJarvisBubble('jarvis', 'Perintah berhasil disinkronkan ke laptop.');
        }
      } catch (err) {
        appendJarvisBubble('jarvis', `Gagal koneksi: ${err.message}`);
      } finally {
        if (statusEl) statusEl.innerHTML = '<span>Tahan mic untuk bicara (Whisper AI)</span>';
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
      view.setUint16(22, 1, true); // Mono
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

        const glow = document.getElementById('jarvis-mic-glow');
        const micBtn = document.getElementById('jarvis-mic-btn');
        const statusEl = document.getElementById('jarvis-voice-status');

        if (glow) glow.classList.remove('opacity-0');
        if (micBtn) {
          micBtn.classList.remove('tactile-btn-cyan');
          micBtn.classList.add('bg-red-950/40', 'border-red-500', 'text-red-400');
        }
        if (statusEl) {
          statusEl.innerHTML = '<span class="text-red-400 animate-pulse font-bold flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span> Merekam suara... Lepas untuk mengirim</span>';
        }
      } catch (err) {
        console.error('Microphone error:', err);
        showToast('Izin mic diperlukan: ' + err.message, 'error');
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
        micBtn.classList.remove('bg-red-950/40', 'border-red-500', 'text-red-400');
        micBtn.classList.add('tactile-btn-cyan');
      }
      if (statusEl) {
        statusEl.innerHTML = '<span class="text-cyan-400 animate-pulse font-semibold">Mengirim ke laptop & mentranskripsi...</span>';
      }

      if (jarvisAudioProcessor) {
        try { jarvisAudioProcessor.disconnect(); } catch (e) {}
      }
      if (jarvisAudioContext) {
        try { jarvisAudioContext.close(); } catch (e) {}
      }
      if (jarvisMediaStream) {
        jarvisMediaStream.getTracks().forEach(t => t.stop());
      }

      let totalLength = 0;
      for (const chunk of jarvisAudioChunks) totalLength += chunk.length;
      if (totalLength < 1600) {
        if (statusEl) statusEl.innerHTML = '<span>Rekaman terlalu singkat</span>';
        setTimeout(() => {
          if (statusEl) statusEl.innerHTML = '<span>Tahan mic untuk bicara (Whisper AI)</span>';
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
        } else if (data.error) {
          appendJarvisBubble('jarvis', `Perhatian: ${data.error}`);
        }
        if (jarvisAudioTarget === 'phone' && data.audio_base64) {
          playBase64Wav(data.audio_base64);
        }
      } catch (err) {
        appendJarvisBubble('jarvis', `Gagal memproses: ${err.message}`);
      } finally {
        if (statusEl) statusEl.innerHTML = '<span>Tahan mic untuk bicara (Whisper AI)</span>';
      }
    }

    function setupJarvisMicListeners() {
      const btn = document.getElementById('jarvis-mic-btn');
      if (!btn) return;

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

    // Initialization
    window.addEventListener('DOMContentLoaded', () => {
      if (window.lucide) lucide.createIcons();
      initWebSocket();
      setupTouchpad();
      setupScrollStrip();
      setupJarvisMicListeners();
      checkJarvisStatus();
      setInterval(checkJarvisStatus, 5000);
      loadSystemStatus();
      setInterval(loadSystemStatus, 3500);
    });
  </script>
</body>
</html>
"""

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print(f"Successfully rebuilt {INDEX_PATH} with authentic tactile hardware remote & dual-deck architecture!")
