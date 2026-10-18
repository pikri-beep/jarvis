"""Script to completely refactor D:\\Project\\remote\\static\\index.html.

Implements the Ultra-Minimalist, Clean, and Proportional 5-Layer UI:
1. Layer 1: Compact Top Bar (QR, Battery, Screen Off, Power) & Segmented Mode Switcher (Remote vs JARVIS AI)
2. Layer 2: Unified Touchpad & D-Pad in ONE spacious box with corner toggle button + Left/Right click below
3. Layer 3: Single Window Quick-Keys Row (Alt+Tab, F11, Ctrl+W, Win+D)
4. Layer 4: Clean Media & Rocker Deck (Volume Rocker, Prev/Play-Pause/Next + Chrome button with globe icon, Brightness Rocker)
5. Layer 5: Minimalist Bottom Dock (Hanya 4 Ikon Utilitas: Cari, Ketik, Peek, Drop)

Also fixes:
- Battery [object Object]% bug
- Chrome button icon (data-lucide="globe") and centering (flex items-center justify-center gap-2)
- Merges Drop + Pesan/TTS into a tabbed bottom sheet
- Streamlines JARVIS AI into a clean modern ChatGPT-style view with single-line header and integrated mic input bar.
"""

import os

INDEX_HTML_PATH = r"D:\Project\remote\static\index.html"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="id" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <meta name="theme-color" content="#09090b">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>PocketDesk Remote & JARVIS AI</title>

  <!-- Google Fonts: Inter & JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">

  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'sans-serif'],
            mono: ['JetBrains Mono', 'monospace'],
          },
          colors: {
            remote: {
              bg: '#09090b',
              surface: '#121217',
              border: '#22222c',
              accent: '#f97316',
              cyan: '#06b6d4',
            }
          }
        }
      }
    }
  </script>

  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>

  <style>
    /* Mobile-first resets & tactile interaction rules */
    *, *::before, *::after {
      -webkit-tap-highlight-color: transparent;
      user-select: none;
      -webkit-user-select: none;
      box-sizing: border-box;
    }

    html, body {
      height: 100%;
      height: 100dvh;
      overflow: hidden;
      margin: 0;
      padding: 0;
      background-color: #070709;
      color: #fafafa;
    }

    input, textarea {
      user-select: text;
      -webkit-user-select: text;
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
      background: #272733;
      border-radius: 9999px;
    }

    /* Tactile button pressed state */
    .tactile-btn {
      touch-action: manipulation;
      transition: all 0.12s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .tactile-btn:active {
      transform: scale(0.96);
      filter: brightness(1.2);
    }

    /* Keyframe Animations */
    @keyframes sheetUp {
      from { transform: translateY(100%); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .animate-sheet-up {
      animation: sheetUp 0.24s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    /* Trackpad Dot Grid */
    .trackpad-surface {
      background-image: radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px);
      background-size: 16px 16px;
      touch-action: none;
    }
  </style>
</head>
<body class="flex items-center justify-center bg-[#070709]">

  <!-- =================================================================== -->
  <!-- MAIN CHASSIS (100dvh Zero-Scroll Container) -->
  <!-- =================================================================== -->
  <div class="h-[100dvh] w-full max-w-sm mx-auto flex flex-col justify-between p-2.5 sm:p-3 overflow-hidden select-none bg-[#0e0e12] border-x border-[#202028] shadow-[0_0_50px_rgba(0,0,0,0.85)] relative">

    <!-- ----------------------------------------------------------------- -->
    <!-- LAPISAN 1: COMPACT TOP BAR & SEGMENTED MODE SWITCHER -->
    <!-- ----------------------------------------------------------------- -->
    <div class="shrink-0 space-y-1.5 mb-1">
      <!-- 1.1 Top Hardware Bar (Tipis & Bersih) -->
      <header class="flex items-center justify-between h-8 px-0.5">
        <!-- Kiri: QR Icon + LED Online + Baterai -->
        <div class="flex items-center gap-1.5">
          <a href="/" onclick="haptic(15)" class="tactile-btn w-7 h-7 rounded-lg bg-[#16161d] border border-[#272733] flex items-center justify-center text-zinc-400 hover:text-white" title="Scan QR Code / Ganti Host">
            <i data-lucide="qr-code" class="w-3.5 h-3.5"></i>
          </a>

          <!-- LED Indicator -->
          <div class="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#16161d] border border-[#272733]">
            <span id="led-indicator" class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span id="led-label" class="text-[9px] font-mono text-zinc-400 font-medium">Online</span>
          </div>

          <!-- Baterai Laptop (Fix [object Object]% bug) -->
          <div id="bat-box" class="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-[#16161d] border border-[#272733] px-2 py-0.5 rounded-full">
            <i id="bat-icon" data-lucide="battery-charging" class="w-3 h-3 text-emerald-400"></i>
            <span id="bat-text">--%</span>
          </div>
        </div>

        <!-- Kanan: Screen Off + Power Button -->
        <div class="flex items-center gap-1.5">
          <!-- Screen Off Button -->
          <button onclick="screenOff()" class="tactile-btn h-7 px-2.5 rounded-full text-xs font-medium text-amber-400 gap-1 bg-[#1a1714] border border-amber-500/25 flex items-center" title="Matikan Lampu Layar Laptop">
            <i data-lucide="monitor-off" class="w-3 h-3 text-amber-400"></i>
            <span class="text-[10px] tracking-tight font-semibold">Screen</span>
          </button>

          <!-- Tombol Bulat Power Merah -->
          <button onclick="openPowerModal()" class="tactile-btn w-7 h-7 rounded-full bg-red-950/40 border border-red-500/30 text-red-400 flex items-center justify-center hover:bg-red-900/50" title="Menu Daya & Sistem">
            <i data-lucide="power" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </header>

      <!-- 1.2 Segmented Pill Mode Switcher (Remot vs JARVIS AI) -->
      <nav class="flex items-center bg-[#14141a] p-1 rounded-xl border border-[#242430] shadow-inner">
        <button id="tab-btn-remote" onclick="switchDeck('remote')" class="flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 bg-[#252532] text-white shadow-sm border border-white/10">
          <i data-lucide="gamepad-2" class="w-3.5 h-3.5 text-remote-accent"></i>
          <span>Remote</span>
        </button>
        <button id="tab-btn-jarvis" onclick="switchDeck('jarvis')" class="flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white">
          <span id="tab-jarvis-dot" class="w-2 h-2 rounded-full bg-zinc-500"></span>
          <i data-lucide="bot" class="w-3.5 h-3.5 text-cyan-400"></i>
          <span>JARVIS AI</span>
        </button>
      </nav>
    </div>

    <!-- ================================================================= -->
    <!-- MODE 1: REMOTE CONTROLLER DECK -->
    <!-- ================================================================= -->
    <main id="deck-remote" class="flex-1 min-h-0 flex flex-col justify-between overflow-hidden my-1 gap-1.5">

      <!-- --------------------------------------------------------------- -->
      <!-- LAPISAN 2: UNIFIED TOUCHPAD & D-PAD SURFACE (1 Kotak Lega) -->
      <!-- --------------------------------------------------------------- -->
      <section class="flex-1 min-h-[190px] bg-[#121217] rounded-2xl border border-[#22222d] p-2 flex flex-col justify-between relative shadow-inner overflow-hidden">
        
        <!-- Header Kotak: Label & Toggle D-Pad / Touchpad -->
        <div class="flex items-center justify-between shrink-0 mb-1 px-1 z-10">
          <span id="surface-mode-label" class="text-[10px] font-mono uppercase tracking-wider text-zinc-400 font-bold flex items-center gap-1.5">
            <i data-lucide="mouse-pointer-2" class="w-3 h-3 text-remote-accent"></i>
            <span>Touchpad</span>
          </span>
          <button onclick="toggleTouchMode()" id="surface-toggle-btn" class="tactile-btn h-6 px-2.5 rounded-lg text-[10px] font-semibold text-zinc-300 bg-[#1c1c24] border border-[#2d2d3a] hover:text-white flex items-center gap-1" title="Beralih antara Touchpad dan D-Pad">
            <i data-lucide="gamepad-2" class="w-3 h-3 text-remote-accent"></i>
            <span id="surface-toggle-text">D-Pad</span>
          </button>
        </div>

        <!-- Konten A: Touchpad Surface + Scroll Strip (Default) -->
        <div id="surface-touchpad" class="flex-1 min-h-0 w-full rounded-xl overflow-hidden bg-[#0a0a0e] border border-white/5 flex relative">
          <!-- Area Sentuh Trackpad -->
          <div id="touchpad-area" class="flex-1 h-full trackpad-surface flex items-center justify-center cursor-crosshair relative">
            <div class="pointer-events-none flex flex-col items-center gap-1 opacity-20">
              <i data-lucide="mouse-pointer-2" class="w-5 h-5 text-white"></i>
              <span class="text-[8px] tracking-widest font-mono text-white">TOUCHPAD NAVIGATION</span>
            </div>
          </div>
          <!-- Scroll Strip Tipis di Sisi Kanan -->
          <div id="scroll-strip" class="w-6 h-full bg-[#14141a] border-l border-white/5 flex flex-col items-center justify-between py-2 cursor-ns-resize touch-none z-10 hover:bg-[#1a1a24] transition-colors" title="Geser 1 Jempol Naik/Turun untuk Scroll">
            <i data-lucide="chevron-up" class="w-3 h-3 text-white/30 shrink-0"></i>
            <div class="w-1 h-5 rounded-full bg-remote-accent/60"></div>
            <i data-lucide="chevron-down" class="w-3 h-3 text-white/30 shrink-0"></i>
          </div>
        </div>

        <!-- Konten B: Circular D-Pad Ring (Saat di-toggle) -->
        <div id="surface-dpad" class="hidden flex-1 min-h-0 w-full items-center justify-center relative">
          <div class="relative w-40 h-40 flex items-center justify-center">
            <!-- Lingkaran Luar -->
            <div class="absolute inset-0 rounded-full bg-[#16161e] border-2 border-[#282836] shadow-[inset_0_2px_8px_rgba(0,0,0,0.8),0_4px_12px_rgba(0,0,0,0.6)]"></div>

            <!-- D-Pad UP -->
            <button onclick="pressKey('up')" class="tactile-btn absolute top-1 w-12 h-10 rounded-t-2xl rounded-b-md text-white hover:text-remote-accent flex items-center justify-center" title="Atas">
              <i data-lucide="chevron-up" class="w-5 h-5"></i>
            </button>
            <!-- D-Pad DOWN -->
            <button onclick="pressKey('down')" class="tactile-btn absolute bottom-1 w-12 h-10 rounded-b-2xl rounded-t-md text-white hover:text-remote-accent flex items-center justify-center" title="Bawah">
              <i data-lucide="chevron-down" class="w-5 h-5"></i>
            </button>
            <!-- D-Pad LEFT -->
            <button onclick="pressKey('left')" class="tactile-btn absolute left-1 w-10 h-12 rounded-l-2xl rounded-r-md text-white hover:text-remote-accent flex items-center justify-center" title="Kiri">
              <i data-lucide="chevron-left" class="w-5 h-5"></i>
            </button>
            <!-- D-Pad RIGHT -->
            <button onclick="pressKey('right')" class="tactile-btn absolute right-1 w-10 h-12 rounded-r-2xl rounded-l-md text-white hover:text-remote-accent flex items-center justify-center" title="Kanan">
              <i data-lucide="chevron-right" class="w-5 h-5"></i>
            </button>
            <!-- Center OK -->
            <button onclick="pressKey('enter')" class="tactile-btn tactile-btn-accent z-10 w-12 h-12 rounded-full text-xs font-extrabold uppercase shadow-xl flex items-center justify-center border-2 border-white/20 active:scale-95 bg-remote-accent text-white" title="OK / Enter">
              OK
            </button>
          </div>
        </div>

        <!-- Tombol Fisik Klik Kiri & Kanan (Tepat di bawah kotak) -->
        <div class="grid grid-cols-2 gap-2 h-9 mt-2 shrink-0">
          <button onclick="mouseClick('left')" class="tactile-btn h-full rounded-xl text-xs font-bold text-white gap-1.5 bg-[#181820] border border-[#272733] flex items-center justify-center shadow-sm">
            <i data-lucide="mouse" class="w-3.5 h-3.5 text-remote-accent"></i>
            <span>Klik Kiri</span>
          </button>
          <button onclick="mouseClick('right')" class="tactile-btn h-full rounded-xl text-xs font-bold text-zinc-400 hover:text-white gap-1.5 bg-[#181820] border border-[#272733] flex items-center justify-center shadow-sm">
            <span>Klik Kanan</span>
            <i data-lucide="corner-down-right" class="w-3.5 h-3.5 text-zinc-500"></i>
          </button>
        </div>
      </section>

      <!-- --------------------------------------------------------------- -->
      <!-- LAPISAN 3: 1 BARIS PINTASAN JENDELA SAJA (Alt+Tab, F11, Ctrl+W, Win+D) -->
      <!-- --------------------------------------------------------------- -->
      <section class="grid grid-cols-4 gap-1.5 shrink-0 h-8">
        <button onclick="sendShortcut('alt_tab')" class="tactile-btn h-full rounded-xl text-[11px] font-mono font-semibold text-amber-400 bg-[#14141a] border border-[#242430] flex items-center justify-center shadow-sm" title="Beralih Aplikasi (Alt+Tab)">
          Alt+Tab
        </button>
        <button onclick="sendShortcut('f11')" class="tactile-btn h-full rounded-xl text-[11px] font-mono font-semibold text-zinc-300 bg-[#14141a] border border-[#242430] flex items-center justify-center shadow-sm" title="Layar Penuh (F11)">
          F11
        </button>
        <button onclick="sendShortcut('ctrl_w')" class="tactile-btn h-full rounded-xl text-[11px] font-mono font-semibold text-rose-400 bg-[#14141a] border border-[#242430] flex items-center justify-center shadow-sm" title="Tutup Tab / Jendela (Ctrl+W)">
          Ctrl+W
        </button>
        <button onclick="sendShortcut('win_d')" class="tactile-btn h-full rounded-xl text-[11px] font-mono font-semibold text-sky-400 bg-[#14141a] border border-[#242430] flex items-center justify-center shadow-sm" title="Tampilkan Desktop (Win+D)">
          Win+D
        </button>
      </section>

      <!-- --------------------------------------------------------------- -->
      <!-- LAPISAN 4: CLEAN MEDIA & ROCKER DECK -->
      <!-- --------------------------------------------------------------- -->
      <section class="grid grid-cols-4 gap-1.5 shrink-0 h-24">
        
        <!-- Kiri: Rocker Vertikal Volume (Col 1) -->
        <div class="col-span-1 bg-[#14141a] p-1 rounded-xl border border-[#242430] flex flex-col justify-between items-center shadow-inner">
          <button onclick="volumeStep(5)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-remote-accent flex items-center justify-center" title="Volume Naik">
            <i data-lucide="plus" class="w-3.5 h-3.5"></i>
          </button>
          <button onclick="volumeMute()" class="w-full flex flex-col items-center py-0.5 rounded hover:bg-white/5 tactile-btn" title="Klik untuk Mute / Unmute">
            <span class="text-[8px] font-mono text-zinc-400 uppercase tracking-wider">VOL</span>
            <span id="vol-level-text" class="text-[10px] font-mono font-bold text-white">--%</span>
          </button>
          <button onclick="volumeStep(-5)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-remote-accent flex items-center justify-center" title="Volume Turun">
            <i data-lucide="minus" class="w-3.5 h-3.5"></i>
          </button>
        </div>

        <!-- Tengah: Media Controls & Tombol Lebar Buka Chrome (Col 2 & 3) -->
        <div class="col-span-2 flex flex-col justify-between gap-1.5">
          <!-- Baris 3 Tombol Media -->
          <div class="grid grid-cols-3 gap-1.5 h-11">
            <button onclick="mediaAction('prev')" class="tactile-btn h-full rounded-xl bg-[#14141a] border border-[#242430] text-zinc-300 hover:text-white flex items-center justify-center shadow-sm" title="Lagu Sebelumnya">
              <i data-lucide="skip-back" class="w-4 h-4"></i>
            </button>
            <button onclick="mediaAction('playpause')" class="tactile-btn h-full rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white flex items-center justify-center shadow-md border border-amber-400/30" title="Putar / Jeda">
              <i data-lucide="play" class="w-4 h-4 fill-current"></i>
            </button>
            <button onclick="mediaAction('next')" class="tactile-btn h-full rounded-xl bg-[#14141a] border border-[#242430] text-zinc-300 hover:text-white flex items-center justify-center shadow-sm" title="Lagu Berikutnya">
              <i data-lucide="skip-forward" class="w-4 h-4"></i>
            </button>
          </div>

          <!-- Tombol Lebar Buka Chrome (Fix Ikon globe & rata tengah) -->
          <button onclick="openBrowser('https://www.google.com')" class="tactile-btn w-full h-11 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-950/40 via-sky-950/40 to-blue-950/40 border border-sky-500/30 flex items-center justify-center gap-2 shadow-sm" title="Buka Google Chrome">
            <i data-lucide="globe" class="w-4 h-4 text-sky-400 shrink-0"></i>
            <span class="tracking-wide">Chrome</span>
          </button>
        </div>

        <!-- Kanan: Rocker Vertikal Brightness (Col 4) -->
        <div class="col-span-1 bg-[#14141a] p-1 rounded-xl border border-[#242430] flex flex-col justify-between items-center shadow-inner">
          <button onclick="brightnessStep(10)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-amber-400 flex items-center justify-center" title="Kecerahan Naik">
            <i data-lucide="sun-medium" class="w-3.5 h-3.5"></i>
          </button>
          <button onclick="toggleBrightnessPreset()" class="w-full flex flex-col items-center py-0.5 rounded hover:bg-white/5 tactile-btn" title="Toggle 20% / 80%">
            <span class="text-[8px] font-mono text-zinc-400 uppercase tracking-wider">BRT</span>
            <span id="brt-level-text" class="text-[10px] font-mono font-bold text-amber-300">--%</span>
          </button>
          <button onclick="brightnessStep(-10)" class="tactile-btn w-full h-7 rounded-lg text-xs font-bold text-white hover:text-amber-400 flex items-center justify-center" title="Kecerahan Turun">
            <i data-lucide="sun-dim" class="w-3.5 h-3.5"></i>
          </button>
        </div>

      </section>

    </main>


    <!-- ================================================================= -->
    <!-- MODE 2: SIMPLIFIED JARVIS AI ASSISTANT DECK -->
    <!-- ================================================================= -->
    <main id="deck-jarvis" class="hidden flex-1 min-h-0 flex flex-col justify-between overflow-hidden my-1 gap-1.5 animate-sheet-up">
      
      <!-- C.1 Header JARVIS Gabungan (1 Baris Tipis Saja di Atas) -->
      <section class="flex items-center justify-between bg-[#121217] px-2.5 py-1.5 rounded-xl border border-[#22222d] shrink-0">
        <!-- Kiri: Status & Model -->
        <div class="flex items-center gap-1.5">
          <span id="jarvis-status-badge" class="px-2 py-0.5 text-[9px] rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-mono font-semibold">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> ONLINE
          </span>
          <span id="jarvis-model-sub" class="text-[10px] text-zinc-400 font-mono">qwen2.5:1.5b</span>
          <!-- Tombol Nyalakan jika Offline -->
          <button onclick="startJarvisFromPhone()" id="jarvis-start-btn" class="hidden tactile-btn px-2 py-0.5 rounded-md text-[9px] font-bold bg-red-500/20 hover:bg-red-500/40 border border-red-500/40 text-red-200 flex items-center gap-1">
            <i data-lucide="zap" class="w-2.5 h-2.5 text-amber-300"></i>
            <span>Nyalakan</span>
          </button>
        </div>

        <!-- Kanan: Switcher Output Suara Tipis (Laptop vs HP) -->
        <div class="flex items-center bg-[#0a0a0e] p-0.5 rounded-lg border border-white/5">
          <button onclick="setJarvisAudioTarget('laptop')" id="target-btn-laptop" class="px-2 py-0.5 rounded-md text-[9px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="speaker" class="w-3 h-3"></i>
            <span>Laptop</span>
          </button>
          <button onclick="setJarvisAudioTarget('phone')" id="target-btn-phone" class="px-2 py-0.5 rounded-md text-[9px] font-semibold transition-all text-zinc-400 hover:text-white flex items-center gap-1">
            <i data-lucide="smartphone" class="w-3 h-3"></i>
            <span>HP</span>
          </button>
        </div>
      </section>

      <!-- C.2 Area Chat Lega (Ruang Terbesar untuk Percakapan) -->
      <section id="jarvis-chat-log" class="flex-1 min-h-0 overflow-y-auto space-y-2.5 p-3 rounded-2xl bg-[#0a0a0e] border border-[#1e1e26] text-xs">
        <!-- Default Welcome Message -->
        <div class="flex gap-2 items-start">
          <div class="w-6 h-6 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="bot" class="w-3.5 h-3.5 text-cyan-400"></i>
          </div>
          <div class="bg-[#15151c] border border-[#242430] text-zinc-200 rounded-2xl rounded-tl-sm px-3.5 py-2 leading-relaxed shadow-sm max-w-[85%] font-medium">
            Halo sir! JARVIS siap menerima instruksi suara atau teks dari HP ini.
          </div>
        </div>
      </section>

      <!-- C.3 Bagian Bawah JARVIS: Quick Chips & Unified Input Bar -->
      <div class="shrink-0 space-y-1.5">
        <!-- Quick Action Chips (Scrollable Horizontal) -->
        <div class="flex items-center gap-1 overflow-x-auto pb-0.5 shrink-0 scrollbar-none text-[10px]">
          <button onclick="sendJarvisPreset('Buka Chrome')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#14141a] border border-[#262632] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="globe" class="w-3 h-3 text-sky-400"></i>
            <span>Chrome</span>
          </button>
          <button onclick="sendJarvisPreset('Putar musik')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#14141a] border border-[#262632] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="music" class="w-3 h-3 text-amber-400"></i>
            <span>Musik</span>
          </button>
          <button onclick="sendJarvisPreset('Info sistem')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#14141a] border border-[#262632] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="cpu" class="w-3 h-3 text-emerald-400"></i>
            <span>Info Spek</span>
          </button>
          <button onclick="sendJarvisPreset('Ambil tangkapan layar')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#14141a] border border-[#262632] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="camera" class="w-3 h-3 text-purple-400"></i>
            <span>Screenshot</span>
          </button>
          <button onclick="sendJarvisPreset('Volume 50%')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#14141a] border border-[#262632] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="volume-2" class="w-3 h-3 text-rose-400"></i>
            <span>Vol 50%</span>
          </button>
          <button onclick="sendJarvisPreset('Daftar tugas')" class="tactile-btn shrink-0 px-2.5 py-1 rounded-full bg-[#14141a] border border-[#262632] text-zinc-300 hover:text-cyan-400 hover:border-cyan-500/40 flex items-center gap-1">
            <i data-lucide="check-square" class="w-3 h-3 text-indigo-400"></i>
            <span>Todo</span>
          </button>
        </div>

        <!-- 1 Modern Input Bar (Ketik + Mic Push-to-Talk + Kirim) -->
        <div class="flex items-center gap-1.5 p-1 bg-[#121217] rounded-2xl border border-[#242430] shadow-lg">
          <!-- Integrated Mic Push-to-Talk Button -->
          <button id="jarvis-mic-btn" class="tactile-btn w-10 h-10 rounded-xl bg-cyan-950/40 border border-cyan-500/40 text-cyan-400 hover:bg-cyan-900/50 active:scale-95 transition-all flex items-center justify-center shrink-0 relative" title="Tahan untuk bicara (Whisper AI)">
            <span id="jarvis-mic-glow" class="absolute inset-0 rounded-xl border-2 border-red-500 animate-ping opacity-0 pointer-events-none"></span>
            <i id="jarvis-mic-icon" data-lucide="mic" class="w-4 h-4"></i>
          </button>

          <!-- Input Kolom Teks -->
          <div class="relative flex-1">
            <input id="jarvis-text-input" type="text" placeholder="Ketik perintah ke JARVIS..." class="w-full bg-transparent px-2.5 py-2 text-xs text-white placeholder-zinc-500 outline-none font-medium" onkeydown="if(event.key==='Enter') sendJarvisText();">
          </div>

          <!-- Tombol Kirim Teks -->
          <button onclick="sendJarvisText()" id="jarvis-send-btn" class="tactile-btn w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/30 flex items-center justify-center shrink-0" title="Kirim">
            <i data-lucide="send" class="w-4 h-4"></i>
          </button>
        </div>
      </div>

    </main>

    <!-- ----------------------------------------------------------------- -->
    <!-- LAPISAN 5: MINIMALIST BOTTOM DOCK (Hanya 4 Ikon Utilitas) -->
    <!-- ----------------------------------------------------------------- -->
    <footer class="shrink-0 h-12 bg-[#121217] rounded-2xl border border-[#22222d] p-1 flex items-center justify-between shadow-2xl mt-1">
      
      <!-- 1. Cari (YouTube, Google, Wiki) -->
      <button onclick="openSheet('sheet-search')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white" title="YouTube & Web Search">
        <i data-lucide="search" class="w-4 h-4 text-remote-accent"></i>
        <span class="text-[10px] font-medium tracking-tight">Cari</span>
      </button>

      <!-- 2. Ketik (Keyboard, Esc, Enter, Clipboard) -->
      <button onclick="openSheet('sheet-keyboard')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white" title="Remote Keyboard & Clipboard">
        <i data-lucide="keyboard" class="w-4 h-4 text-sky-400"></i>
        <span class="text-[10px] font-medium tracking-tight">Ketik</span>
      </button>

      <!-- 3. Peek (Live Screenshot / Screen) -->
      <button onclick="openSheet('sheet-peek')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white" title="Intip Layar Laptop">
        <i data-lucide="eye" class="w-4 h-4 text-emerald-400"></i>
        <span class="text-[10px] font-medium tracking-tight">Peek</span>
      </button>

      <!-- 4. Drop (Upload Berkas & Kirim Pesan/TTS) -->
      <button onclick="openSheet('sheet-drop')" class="tactile-btn flex-1 h-full mx-0.5 rounded-xl flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white" title="Kirim Berkas / Pesan ke Laptop">
        <i data-lucide="folder-up" class="w-4 h-4 text-purple-400"></i>
        <span class="text-[10px] font-medium tracking-tight">Drop</span>
      </button>
    </footer>

  </div>


  <!-- =================================================================== -->
  <!-- FLOATING TOAST HUD -->
  <!-- =================================================================== -->
  <div id="toast-container" class="fixed top-3 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-1.5 w-11/12 max-w-xs pointer-events-none"></div>


  <!-- =================================================================== -->
  <!-- MODAL 1: SMART PLAY & SEARCH (YouTube / Google / Wiki) -->
  <!-- =================================================================== -->
  <div id="sheet-search" class="sheet-modal fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#14141a] border-t sm:border border-[#282834] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3 animate-sheet-up max-h-[85dvh] overflow-y-auto">
      <div class="flex items-center justify-between border-b border-[#242430] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="search" class="w-4 h-4 text-remote-accent"></i>
          <h3 class="text-sm font-bold text-white">Putar & Cari Pintar</h3>
        </div>
        <button onclick="closeSheet('sheet-search')" class="tactile-btn w-7 h-7 rounded-full text-zinc-400 hover:text-white">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="space-y-1">
        <label class="text-[11px] text-zinc-400 font-medium">Kueri / Judul Lagu / Pencarian:</label>
        <div class="relative">
          <input id="smart-query-input" type="text" placeholder="Ketik apa saja..." class="w-full bg-[#0d0d12] border border-[#272733] rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-600 outline-none focus:border-remote-accent pr-8 font-medium">
          <button onclick="document.getElementById('smart-query-input').value=''" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white">
            <i data-lucide="x" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-2 pt-1">
        <button onclick="smartAction('youtube')" class="tactile-btn h-12 rounded-xl flex flex-col items-center justify-center gap-1 bg-[#1a1a24] border border-[#2c2c3c] text-white hover:border-red-500/40">
          <i data-lucide="play-circle" class="w-4 h-4 text-red-500"></i>
          <span class="text-[10px] font-semibold">YouTube</span>
        </button>
        <button onclick="smartAction('google')" class="tactile-btn h-12 rounded-xl flex flex-col items-center justify-center gap-1 bg-[#1a1a24] border border-[#2c2c3c] text-white hover:border-sky-500/40">
          <i data-lucide="globe" class="w-4 h-4 text-sky-400"></i>
          <span class="text-[10px] font-semibold">Google</span>
        </button>
        <button onclick="smartAction('wiki')" class="tactile-btn h-12 rounded-xl flex flex-col items-center justify-center gap-1 bg-[#1a1a24] border border-[#2c2c3c] text-white hover:border-emerald-500/40">
          <i data-lucide="book-open" class="w-4 h-4 text-emerald-400"></i>
          <span class="text-[10px] font-semibold">Wiki</span>
        </button>
      </div>
    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 2: KEYBOARD & CLIPBOARD -->
  <!-- =================================================================== -->
  <div id="sheet-keyboard" class="sheet-modal fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#14141a] border-t sm:border border-[#282834] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3 animate-sheet-up max-h-[85dvh] overflow-y-auto">
      <div class="flex items-center justify-between border-b border-[#242430] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="keyboard" class="w-4 h-4 text-sky-400"></i>
          <h3 class="text-sm font-bold text-white">Keyboard Jarak Jauh</h3>
        </div>
        <button onclick="closeSheet('sheet-keyboard')" class="tactile-btn w-7 h-7 rounded-full text-zinc-400 hover:text-white">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="space-y-1">
        <label class="text-[11px] text-zinc-400 font-medium">Teks yang akan diketik:</label>
        <div class="flex gap-2">
          <input id="keyboard-input" type="text" placeholder="Ketik teks di sini..." class="flex-1 bg-[#0d0d12] border border-[#272733] rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-600 outline-none focus:border-sky-400 font-medium" onkeydown="if(event.key==='Enter') sendTypedText();">
          <button onclick="sendTypedText()" class="tactile-btn px-3 rounded-xl bg-sky-500/20 border border-sky-500/30 text-sky-300 font-semibold text-xs flex items-center gap-1">
            <i data-lucide="corner-down-left" class="w-3.5 h-3.5"></i>
            <span>Ketik</span>
          </button>
        </div>
      </div>

      <!-- Essential Keys Row -->
      <div class="grid grid-cols-4 gap-1.5 pt-1">
        <button onclick="pressKey('enter')" class="tactile-btn h-9 rounded-xl bg-[#1c1c26] border border-[#2d2d3e] text-xs font-semibold text-white">Enter</button>
        <button onclick="pressKey('backspace')" class="tactile-btn h-9 rounded-xl bg-[#1c1c26] border border-[#2d2d3e] text-xs font-semibold text-white">Backsp</button>
        <button onclick="pressKey('esc')" class="tactile-btn h-9 rounded-xl bg-[#1c1c26] border border-[#2d2d3e] text-xs font-semibold text-rose-400">ESC</button>
        <button onclick="pressKey('space')" class="tactile-btn h-9 rounded-xl bg-[#1c1c26] border border-[#2d2d3e] text-xs font-semibold text-zinc-300">Space</button>
      </div>

      <!-- Clipboard Sync -->
      <div class="pt-2 border-t border-[#242430] flex gap-2">
        <button onclick="pasteClipboardToLaptop()" class="tactile-btn flex-1 h-9 rounded-xl bg-[#1c1c26] border border-[#2d2d3e] text-[11px] font-semibold text-zinc-300 flex items-center justify-center gap-1.5">
          <i data-lucide="clipboard-paste" class="w-3.5 h-3.5 text-sky-400"></i>
          <span>Kirim Clipboard</span>
        </button>
        <button onclick="readLaptopClipboard()" class="tactile-btn flex-1 h-9 rounded-xl bg-[#1c1c26] border border-[#2d2d3e] text-[11px] font-semibold text-zinc-300 flex items-center justify-center gap-1.5">
          <i data-lucide="clipboard-copy" class="w-3.5 h-3.5 text-emerald-400"></i>
          <span>Ambil Clipboard</span>
        </button>
      </div>
    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 3: PEEK SCREEN (Layar Laptop) -->
  <!-- =================================================================== -->
  <div id="sheet-peek" class="sheet-modal fixed inset-0 z-50 bg-black/85 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#14141a] border-t sm:border border-[#282834] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3 animate-sheet-up max-h-[90dvh] overflow-y-auto">
      <div class="flex items-center justify-between border-b border-[#242430] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="eye" class="w-4 h-4 text-emerald-400"></i>
          <h3 class="text-sm font-bold text-white">Intip Layar Laptop</h3>
        </div>
        <div class="flex items-center gap-1.5">
          <button onclick="refreshScreenshot()" class="tactile-btn h-7 px-2.5 rounded-lg text-[10px] font-semibold text-zinc-300 bg-[#1c1c24] border border-[#2c2c3c] flex items-center gap-1">
            <i data-lucide="refresh-cw" class="w-3 h-3 text-emerald-400"></i>
            <span>Refresh</span>
          </button>
          <button onclick="closeSheet('sheet-peek')" class="tactile-btn w-7 h-7 rounded-full text-zinc-400 hover:text-white">
            <i data-lucide="x" class="w-4 h-4"></i>
          </button>
        </div>
      </div>

      <!-- Screenshot Display -->
      <div class="relative w-full aspect-video rounded-xl overflow-hidden bg-black border border-white/10 flex items-center justify-center">
        <img id="peek-img" src="" alt="Layar Laptop" class="w-full h-full object-contain">
        <div id="peek-loader" class="absolute inset-0 flex items-center justify-center bg-black/60 hidden">
          <i data-lucide="loader" class="w-6 h-6 text-emerald-400 animate-spin"></i>
        </div>
      </div>
      <p class="text-[10px] text-zinc-500 text-center font-mono">Tangkapan layar desktop real-time</p>
    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 4: TABBED DROP & NOTIFICATIONS (Berkas Drop + Pesan/TTS) -->
  <!-- =================================================================== -->
  <div id="sheet-drop" class="sheet-modal fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4">
    <div class="w-full max-w-sm bg-[#14141a] border-t sm:border border-[#282834] rounded-t-3xl sm:rounded-2xl p-4 shadow-2xl space-y-3 animate-sheet-up max-h-[85dvh] overflow-y-auto">
      
      <!-- Header dengan Tab Selector -->
      <div class="flex items-center justify-between border-b border-[#242430] pb-2">
        <!-- Tab Pills -->
        <div class="flex items-center bg-[#0d0d12] p-0.5 rounded-xl border border-white/5">
          <button onclick="switchDropTab('files')" id="drop-tab-btn-files" class="px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all bg-[#22222d] text-white">
            📁 Berkas Drop
          </button>
          <button onclick="switchDropTab('notify')" id="drop-tab-btn-notify" class="px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all text-zinc-400 hover:text-white">
            📢 Pesan / TTS
          </button>
        </div>

        <button onclick="closeSheet('sheet-drop')" class="tactile-btn w-7 h-7 rounded-full text-zinc-400 hover:text-white">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <!-- Tab 1: Upload Berkas Drop -->
      <div id="drop-tab-files" class="space-y-3">
        <div onclick="document.getElementById('file-drop-input').click()" class="w-full border-2 border-dashed border-[#333344] hover:border-purple-400/60 rounded-2xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer bg-[#0d0d12] transition-colors">
          <i data-lucide="upload-cloud" class="w-8 h-8 text-purple-400"></i>
          <span class="text-xs font-semibold text-zinc-200">Pilih berkas dari HP</span>
          <span class="text-[10px] text-zinc-500 font-mono">Disimpan ke Downloads/PocketDesk_Drop</span>
        </div>
        <input id="file-drop-input" type="file" multiple class="hidden" onchange="handleFileUpload(event)">
        <div id="upload-progress" class="hidden space-y-1">
          <div class="flex justify-between text-[10px] text-zinc-400 font-mono">
            <span id="upload-filename">Uploading...</span>
            <span id="upload-percent">0%</span>
          </div>
          <div class="w-full h-1.5 bg-[#22222c] rounded-full overflow-hidden">
            <div id="upload-bar" class="h-full bg-purple-500 rounded-full transition-all duration-150" style="width: 0%"></div>
          </div>
        </div>
      </div>

      <!-- Tab 2: Kirim Pesan & TTS -->
      <div id="drop-tab-notify" class="hidden space-y-3">
        <textarea id="tts-msg-input" rows="3" placeholder="Tulis pesan yang akan muncul di layar atau dibacakan speaker laptop..." class="w-full bg-[#0d0d12] border border-[#272733] rounded-xl p-2.5 text-xs text-white placeholder-zinc-600 outline-none focus:border-amber-400 resize-none font-medium"></textarea>
        <div class="grid grid-cols-2 gap-2">
          <button onclick="sendPopupMessage()" class="tactile-btn h-9 rounded-xl text-xs font-semibold gap-1.5 text-white bg-[#1a1a24] border border-[#2c2c3c] flex items-center justify-center">
            <i data-lucide="app-window" class="w-3.5 h-3.5 text-amber-400"></i>
            <span>Pop-up Layar</span>
          </button>
          <button onclick="sendTTSMessage()" class="tactile-btn h-9 rounded-xl text-xs font-semibold gap-1.5 text-white bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
            <i data-lucide="volume-2" class="w-3.5 h-3.5 text-amber-400"></i>
            <span>Suara TTS</span>
          </button>
        </div>
      </div>

    </div>
  </div>


  <!-- =================================================================== -->
  <!-- MODAL 5: POWER & SYSTEM CONTROLS -->
  <!-- =================================================================== -->
  <div id="modal-power" class="sheet-modal fixed inset-0 z-50 bg-black/85 backdrop-blur-sm hidden flex items-center justify-center p-4">
    <div class="w-full max-w-xs bg-[#14141a] border border-[#282834] rounded-2xl p-4 shadow-2xl space-y-3 animate-sheet-up">
      <div class="flex items-center justify-between border-b border-[#242430] pb-2">
        <div class="flex items-center gap-2">
          <i data-lucide="power" class="w-4 h-4 text-red-500"></i>
          <h3 class="text-sm font-bold text-white">Kontrol Daya Laptop</h3>
        </div>
        <button onclick="closePowerModal()" class="tactile-btn w-7 h-7 rounded-full text-zinc-400 hover:text-white">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="space-y-1.5">
        <button onclick="powerAction('lock')" class="tactile-btn w-full h-9 rounded-xl text-xs font-medium text-white bg-[#1a1a24] border border-[#2c2c3c] flex items-center justify-center gap-2">
          <i data-lucide="lock" class="w-3.5 h-3.5 text-amber-400"></i>
          <span>Kunci Komputer (Win+L)</span>
        </button>
        <button onclick="powerAction('sleep')" class="tactile-btn w-full h-9 rounded-xl text-xs font-medium text-white bg-[#1a1a24] border border-[#2c2c3c] flex items-center justify-center gap-2">
          <i data-lucide="moon" class="w-3.5 h-3.5 text-sky-400"></i>
          <span>Tidurkan (Sleep)</span>
        </button>
        <button onclick="powerAction('shutdown')" class="tactile-btn w-full h-9 rounded-xl text-xs font-bold text-red-400 bg-red-950/30 border border-red-500/30 flex items-center justify-center gap-2">
          <i data-lucide="power" class="w-3.5 h-3.5 text-red-500"></i>
          <span>Matikan (Shutdown 15s)</span>
        </button>
        <button onclick="powerAction('cancel-shutdown')" class="tactile-btn w-full h-9 rounded-xl text-xs font-medium text-emerald-400 bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-center gap-2">
          <i data-lucide="x-circle" class="w-3.5 h-3.5 text-emerald-400"></i>
          <span>Batalkan Shutdown</span>
        </button>
      </div>
    </div>
  </div>


  <!-- =================================================================== -->
  <!-- JAVASCRIPT CONTROLLER ENGINE -->
  <!-- =================================================================== -->
  <script>
    // Haptic feedback
    function haptic(ms = 15) {
      if (window.navigator && window.navigator.vibrate) {
        window.navigator.vibrate(ms);
      }
    }

    // Toast HUD
    function showToast(message, type = 'info') {
      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');

      const icons = {
        success: 'check-circle-2',
        error: 'alert-circle',
        info: 'info',
        warning: 'alert-triangle'
      };

      const colors = {
        success: 'border-emerald-500/40 text-emerald-400 bg-[#16161d]',
        error: 'border-red-500/40 text-red-400 bg-[#16161d]',
        info: 'border-remote-accent/40 text-white bg-[#16161d]',
        warning: 'border-amber-500/40 text-amber-400 bg-[#16161d]'
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

    // Modal Helpers
    function openSheet(id) {
      haptic(20);
      document.querySelectorAll('.sheet-modal').forEach(m => m.classList.add('hidden'));
      const el = document.getElementById(id);
      if (el) {
        el.classList.remove('hidden');
        if (id === 'sheet-peek') refreshScreenshot();
      }
      if (window.lucide) lucide.createIcons();
    }

    function closeSheet(id) {
      haptic(15);
      const el = document.getElementById(id);
      if (el) el.classList.add('hidden');
    }

    function openPowerModal() {
      haptic(25);
      document.getElementById('modal-power').classList.remove('hidden');
      if (window.lucide) lucide.createIcons();
    }

    function closePowerModal() {
      haptic(15);
      document.getElementById('modal-power').classList.add('hidden');
    }

    function switchDropTab(tab) {
      haptic(15);
      const tabFiles = document.getElementById('drop-tab-files');
      const tabNotify = document.getElementById('drop-tab-notify');
      const btnFiles = document.getElementById('drop-tab-btn-files');
      const btnNotify = document.getElementById('drop-tab-btn-notify');

      if (tab === 'files') {
        tabFiles.classList.remove('hidden');
        tabNotify.classList.add('hidden');
        btnFiles.className = 'px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all bg-[#22222d] text-white';
        btnNotify.className = 'px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all text-zinc-400 hover:text-white';
      } else {
        tabFiles.classList.add('hidden');
        tabNotify.classList.remove('hidden');
        btnNotify.className = 'px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all bg-[#22222d] text-white';
        btnFiles.className = 'px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all text-zinc-400 hover:text-white';
      }
      if (window.lucide) lucide.createIcons();
    }

    // Deck Switcher (Remote vs JARVIS AI)
    function switchDeck(deck) {
      haptic(20);
      const deckRemote = document.getElementById('deck-remote');
      const deckJarvis = document.getElementById('deck-jarvis');
      const btnRemote = document.getElementById('tab-btn-remote');
      const btnJarvis = document.getElementById('tab-btn-jarvis');

      if (deck === 'remote') {
        deckRemote.classList.remove('hidden');
        deckJarvis.classList.add('hidden');
        btnRemote.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 bg-[#252532] text-white shadow-sm border border-white/10';
        btnJarvis.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white';
      } else {
        deckRemote.classList.add('hidden');
        deckJarvis.classList.remove('hidden');
        btnJarvis.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 bg-[#252532] text-white shadow-sm border border-white/10';
        btnRemote.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 text-zinc-400 hover:text-white';
        checkJarvisStatus();
      }
      if (window.lucide) lucide.createIcons();
    }

    // Toggle Unified Surface: Touchpad vs D-Pad
    let currentSurfaceMode = 'touchpad';
    function toggleTouchMode() {
      haptic(20);
      const surfaceTouch = document.getElementById('surface-touchpad');
      const surfaceDpad = document.getElementById('surface-dpad');
      const toggleText = document.getElementById('surface-toggle-text');
      const label = document.getElementById('surface-mode-label');

      if (currentSurfaceMode === 'touchpad') {
        currentSurfaceMode = 'dpad';
        surfaceTouch.classList.add('hidden');
        surfaceDpad.classList.remove('hidden');
        surfaceDpad.classList.add('flex');
        toggleText.innerText = 'Touchpad';
        label.innerHTML = '<i data-lucide="gamepad-2" class="w-3 h-3 text-remote-accent"></i><span>D-Pad</span>';
      } else {
        currentSurfaceMode = 'touchpad';
        surfaceDpad.classList.add('hidden');
        surfaceDpad.classList.remove('flex');
        surfaceTouch.classList.remove('hidden');
        toggleText.innerText = 'D-Pad';
        label.innerHTML = '<i data-lucide="mouse-pointer-2" class="w-3 h-3 text-remote-accent"></i><span>Touchpad</span>';
      }
      if (window.lucide) lucide.createIcons();
    }

    // Network API Callers
    async function apiPost(endpoint, body = {}) {
      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        return await res.json();
      } catch (err) {
        showToast('Koneksi terputus: ' + err.message, 'error');
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

    // Hardware Actions
    function mouseClick(button = 'left') {
      haptic(25);
      apiPost('/api/mouse/click', { button });
    }

    function pressKey(key) {
      haptic(20);
      apiPost('/api/keyboard/key', { key });
    }

    function sendShortcut(shortcut) {
      haptic(25);
      apiPost('/api/shortcut', { shortcut });
    }

    function openBrowser(url) {
      haptic(20);
      apiPost('/api/browser/open', { url });
    }

    function mediaAction(action) {
      haptic(25);
      apiPost(`/api/media/${action}`);
    }

    function volumeStep(step) {
      haptic(15);
      apiPost('/api/volume/step', { step }).then(r => {
        if (r && r.volume !== undefined) {
          const el = document.getElementById('vol-level-text');
          if (el) el.innerText = `${r.volume}%`;
        }
      });
    }

    function volumeMute() {
      haptic(30);
      apiPost('/api/volume/mute').then(r => {
        if (r && r.volume !== undefined) {
          const el = document.getElementById('vol-level-text');
          if (el) el.innerText = `${r.volume}%`;
          showToast(r.muted ? 'Audio Disenyapkan (Mute)' : 'Audio Aktif', 'info');
        }
      });
    }

    function brightnessStep(step) {
      haptic(15);
      apiPost('/api/brightness', { brightness: step, is_step: true }).then(r => {
        if (r && r.brightness !== undefined) {
          const el = document.getElementById('brt-level-text');
          if (el) el.innerText = `${r.brightness}%`;
        }
      });
    }

    let currentBrtPreset = 80;
    function toggleBrightnessPreset() {
      haptic(20);
      currentBrtPreset = currentBrtPreset === 80 ? 20 : 80;
      apiPost('/api/brightness', { brightness: currentBrtPreset, is_step: false }).then(r => {
        if (r && r.brightness !== undefined) {
          const el = document.getElementById('brt-level-text');
          if (el) el.innerText = `${r.brightness}%`;
        }
      });
    }

    function screenOff() {
      haptic(35);
      apiPost('/api/screen-off').then(() => showToast('Layar laptop dimatikan', 'info'));
    }

    function powerAction(action) {
      haptic(35);
      closePowerModal();
      apiPost(`/api/power/${action}`).then(r => {
        if (r && r.countdown) {
          showToast(`Laptop shutdown dalam ${r.countdown} detik!`, 'warning');
        } else if (r && r.action === 'cancel_shutdown') {
          showToast('Shutdown dibatalkan!', 'success');
        } else {
          showToast('Perintah daya dieksekusi', 'info');
        }
      });
    }

    // Modal Action Handlers
    function smartAction(type) {
      const q = document.getElementById('smart-query-input').value.trim();
      if (!q) return;
      haptic(20);
      closeSheet('sheet-search');
      if (type === 'youtube') apiPost('/api/youtube/play', { query: q }).then(r => showToast(r.message || 'Memutar di YouTube', 'success'));
      else if (type === 'google') apiPost('/api/browser/search', { query: q }).then(() => showToast('Mencari di Google', 'info'));
      else if (type === 'wiki') apiPost('/api/wiki/summary', { query: q }).then(r => showToast(r.summary ? r.summary.slice(0, 80) + '...' : 'Wiki dicari', 'info'));
    }

    function sendTypedText() {
      const input = document.getElementById('keyboard-input');
      const text = input.value;
      if (!text) return;
      haptic(20);
      apiPost('/api/keyboard/type', { text }).then(() => {
        input.value = '';
        showToast('Teks diketik ke laptop', 'success');
      });
    }

    function pasteClipboardToLaptop() {
      haptic(20);
      if (navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then(text => {
          if (text) {
            apiPost('/api/clipboard/send', { text }).then(() => showToast('Clipboard dikirim ke laptop', 'success'));
          } else {
            showToast('Clipboard HP kosong', 'warning');
          }
        }).catch(() => showToast('Izin clipboard ditolak', 'error'));
      }
    }

    function readLaptopClipboard() {
      haptic(20);
      apiGet('/api/clipboard/get').then(r => {
        if (r && r.text) {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(r.text);
          }
          showToast(`Clipboard laptop: ${r.text.slice(0, 25)}...`, 'success');
        } else {
          showToast('Clipboard laptop kosong', 'info');
        }
      });
    }

    function refreshScreenshot() {
      const img = document.getElementById('peek-img');
      const loader = document.getElementById('peek-loader');
      if (!img) return;
      haptic(20);
      if (loader) loader.classList.remove('hidden');
      img.src = '/api/screen/peek?t=' + Date.now();
      img.onload = () => { if (loader) loader.classList.add('hidden'); };
      img.onerror = () => { if (loader) loader.classList.add('hidden'); showToast('Gagal memuat layar', 'error'); };
    }

    function handleFileUpload(e) {
      const files = e.target.files;
      if (!files || !files.length) return;
      haptic(20);

      const pBox = document.getElementById('upload-progress');
      const pBar = document.getElementById('upload-bar');
      const pName = document.getElementById('upload-filename');
      const pPct = document.getElementById('upload-percent');

      pBox.classList.remove('hidden');
      pBar.style.width = '0%';

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        pName.innerText = file.name;
        const form = new FormData();
        form.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload', true);
        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) {
            const pct = Math.round((ev.loaded / ev.total) * 100);
            pBar.style.width = pct + '%';
            pPct.innerText = pct + '%';
          }
        };
        xhr.onload = () => {
          if (xhr.status === 200) {
            showToast(`Berkas '${file.name}' berhasil dikirim!`, 'success');
            setTimeout(() => { pBox.classList.add('hidden'); closeSheet('sheet-drop'); }, 1200);
          } else {
            showToast(`Gagal mengunggah '${file.name}'`, 'error');
          }
        };
        xhr.send(form);
      }
    }

    function sendPopupMessage() {
      const text = document.getElementById('tts-msg-input').value.trim();
      if (!text) return;
      haptic(20);
      closeSheet('sheet-drop');
      apiPost('/api/notify/popup', { message: text }).then(() => showToast('Notifikasi pop-up ditampilkan di laptop', 'success'));
    }

    function sendTTSMessage() {
      const text = document.getElementById('tts-msg-input').value.trim();
      if (!text) return;
      haptic(20);
      closeSheet('sheet-drop');
      apiPost('/api/notify/tts', { message: text }).then(() => showToast('Suara dibacakan lewat speaker laptop', 'success'));
    }

    // Touchpad & Scroll Strip Handlers
    function setupTouchpad() {
      const pad = document.getElementById('touchpad-area');
      if (!pad) return;

      let lastX = 0, lastY = 0;
      let startX = 0, startY = 0;
      let startTime = 0;
      let isMoving = false;

      pad.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
          lastX = e.touches[0].clientX;
          lastY = e.touches[0].clientY;
          startX = lastX;
          startY = lastY;
          startTime = Date.now();
          isMoving = false;
        }
      }, { passive: false });

      pad.addEventListener('touchmove', (e) => {
        e.preventDefault();
        if (e.touches.length === 1) {
          const x = e.touches[0].clientX;
          const y = e.touches[0].clientY;
          const dx = (x - lastX) * 1.7;
          const dy = (y - lastY) * 1.7;
          lastX = x;
          lastY = y;
          isMoving = true;
          if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
            if (window.wsTouchpad && window.wsTouchpad.readyState === WebSocket.OPEN) {
              window.wsTouchpad.send(JSON.stringify({ type: 'move', dx, dy }));
            }
          }
        }
      }, { passive: false });

      pad.addEventListener('touchend', (e) => {
        const elapsed = Date.now() - startTime;
        const totalDist = Math.hypot(lastX - startX, lastY - startY);
        if (elapsed < 240 && totalDist < 8 && !isMoving) {
          mouseClick('left');
        }
      }, { passive: false });
    }

    function setupScrollStrip() {
      const strip = document.getElementById('scroll-strip');
      if (!strip) return;

      let startY = 0;
      let accY = 0;

      strip.addEventListener('touchstart', (e) => {
        startY = e.touches[0].clientY;
        accY = 0;
      }, { passive: false });

      strip.addEventListener('touchmove', (e) => {
        e.preventDefault();
        const currentY = e.touches[0].clientY;
        const dy = currentY - startY;
        startY = currentY;
        accY += dy;
        if (Math.abs(accY) >= 8) {
          const dir = accY > 0 ? 'down' : 'up';
          accY = 0;
          apiPost('/api/mouse/scroll', { direction: dir, amount: 80 });
        }
      }, { passive: false });
    }

    // Touchpad WebSocket
    function initWebSocket() {
      const loc = window.location;
      const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProto}//${loc.host}/ws/touchpad`;
      try {
        window.wsTouchpad = new WebSocket(wsUrl);
        window.wsTouchpad.onopen = () => console.log('Touchpad WebSocket connected');
        window.wsTouchpad.onclose = () => setTimeout(initWebSocket, 3000);
      } catch (e) {
        console.warn('WS not available, falling back to HTTP:', e);
      }
    }

    // Telemetry & Battery Fix
    async function loadSystemStatus() {
      try {
        const res = await apiGet('/api/status');
        if (res && res.volume !== undefined) {
          const el = document.getElementById('vol-level-text');
          if (el) el.innerText = `${res.volume}%`;
        }
        if (res && res.brightness !== undefined) {
          const el = document.getElementById('brt-level-text');
          if (el) el.innerText = `${res.brightness}%`;
        }

        // Fix Bug Baterai [object Object]%
        const batBox = document.getElementById('bat-box');
        const batText = document.getElementById('bat-text');
        const batIcon = document.getElementById('bat-icon');

        if (res && res.battery !== undefined && res.battery !== null) {
          let pct = null;
          let plugged = false;
          if (typeof res.battery === 'object') {
            pct = res.battery.percent;
            plugged = !!res.battery.power_plugged;
          } else if (typeof res.battery === 'number') {
            pct = res.battery;
          }

          if (pct !== null && !isNaN(pct)) {
            if (batBox) {
              batBox.classList.remove('hidden');
              batBox.classList.add('flex');
            }
            if (batText) batText.innerText = `${pct}%`;
            if (batIcon) {
              batIcon.setAttribute('data-lucide', plugged ? 'battery-charging' : (pct > 20 ? 'battery' : 'battery-low'));
            }
          }
        }
        if (window.lucide) lucide.createIcons();
      } catch (err) {
        console.warn('Telemetry load failed:', err);
      }
    }

    // =========================================================================
    // JARVIS AI ASSISTANT CLIENT ENGINE
    // =========================================================================
    let jarvisAudioTarget = 'laptop';
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
        btnPhone.className = 'px-2 py-0.5 rounded-md text-[9px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1';
        btnLaptop.className = 'px-2 py-0.5 rounded-md text-[9px] font-semibold transition-all text-zinc-400 hover:text-white flex items-center gap-1';
        showToast('Suara JARVIS diputar di speaker HP ini', 'info');
      } else {
        btnLaptop.className = 'px-2 py-0.5 rounded-md text-[9px] font-semibold transition-all bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1';
        btnPhone.className = 'px-2 py-0.5 rounded-md text-[9px] font-semibold transition-all text-zinc-400 hover:text-white flex items-center gap-1';
        showToast('Suara JARVIS diputar di speaker laptop', 'info');
      }
      if (window.lucide) lucide.createIcons();
    }

    async function checkJarvisStatus() {
      try {
        const res = await apiGet('/api/jarvis/status');
        const badge = document.getElementById('jarvis-status-badge');
        const dot = document.getElementById('tab-jarvis-dot');
        const modelSub = document.getElementById('jarvis-model-sub');
        const startBtn = document.getElementById('jarvis-start-btn');

        if (res && res.online) {
          if (badge) {
            badge.className = 'px-2 py-0.5 text-[9px] rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-mono font-semibold';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> ONLINE';
          }
          if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]';
          if (modelSub && res.model) modelSub.innerText = res.model;
          if (startBtn) startBtn.classList.add('hidden');
        } else {
          if (badge) {
            badge.className = 'px-2 py-0.5 text-[9px] rounded-full bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1 font-mono font-semibold';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-red-400"></span> OFFLINE';
          }
          if (dot) dot.className = 'w-2 h-2 rounded-full bg-zinc-500';
          if (modelSub) modelSub.innerText = 'Offline (Laptop)';
          if (startBtn) startBtn.classList.remove('hidden');
        }
        if (window.lucide) lucide.createIcons();
      } catch (e) {
        console.warn('JARVIS check failed:', e);
      }
    }

    async function startJarvisFromPhone() {
      haptic(25);
      const btn = document.getElementById('jarvis-start-btn');
      if (btn) btn.innerHTML = '<i data-lucide="loader" class="w-2.5 h-2.5 animate-spin"></i><span>Memulai...</span>';
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
        showToast('Gagal menghubungi server', 'error');
      } finally {
        if (btn) btn.innerHTML = '<i data-lucide="zap" class="w-2.5 h-2.5 text-amber-300"></i><span>Nyalakan</span>';
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
          <div class="bg-cyan-600/25 border border-cyan-500/35 text-cyan-100 rounded-2xl rounded-tr-sm px-3.5 py-2 leading-relaxed max-w-[85%] shadow-sm font-medium">
            ${escapeHtml(text)}
          </div>
          <div class="w-6 h-6 rounded-lg bg-cyan-500/30 border border-cyan-500/50 flex items-center justify-center shrink-0 mt-0.5 text-cyan-200">
            <i data-lucide="user" class="w-3.5 h-3.5"></i>
          </div>
        `;
      } else {
        bubbleWrap.innerHTML = `
          <div class="w-6 h-6 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="bot" class="w-3.5 h-3.5 text-cyan-400"></i>
          </div>
          <div class="bg-[#15151c] border border-[#242430] text-zinc-200 rounded-2xl rounded-tl-sm px-3.5 py-2 leading-relaxed max-w-[85%] shadow-sm font-medium">
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

      const placeholderOld = input.placeholder;
      input.placeholder = 'JARVIS sedang memproses...';

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
          appendJarvisBubble('jarvis', 'Perintah diterima, sir.');
        }
      } catch (err) {
        appendJarvisBubble('jarvis', `Koneksi gagal: ${err.message}`);
      } finally {
        input.placeholder = placeholderOld;
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
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
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
          audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true }
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

        // Visual feedback
        const glow = document.getElementById('jarvis-mic-glow');
        const micBtn = document.getElementById('jarvis-mic-btn');
        const input = document.getElementById('jarvis-text-input');

        if (glow) glow.classList.remove('opacity-0');
        if (micBtn) {
          micBtn.classList.remove('border-cyan-500/40', 'text-cyan-400', 'bg-cyan-950/40');
          micBtn.classList.add('border-red-500', 'text-red-400', 'bg-red-950/40');
        }
        if (input) input.placeholder = 'Merekam suara... Lepas tombol untuk mengirim';
      } catch (err) {
        console.error('Microphone error:', err);
        showToast('Izin mikrofon diperlukan: ' + err.message, 'error');
      }
    }

    async function stopJarvisRecording() {
      if (!jarvisIsRecording) return;
      jarvisIsRecording = false;
      haptic(20);

      const glow = document.getElementById('jarvis-mic-glow');
      const micBtn = document.getElementById('jarvis-mic-btn');
      const input = document.getElementById('jarvis-text-input');

      if (glow) glow.classList.add('opacity-0');
      if (micBtn) {
        micBtn.classList.add('border-cyan-500/40', 'text-cyan-400', 'bg-cyan-950/40');
        micBtn.classList.remove('border-red-500', 'text-red-400', 'bg-red-950/40');
      }
      if (input) input.placeholder = 'Mentranskripsi suara...';

      if (jarvisAudioProcessor) try { jarvisAudioProcessor.disconnect(); } catch (e) {}
      if (jarvisAudioContext) try { jarvisAudioContext.close(); } catch (e) {}
      if (jarvisMediaStream) jarvisMediaStream.getTracks().forEach(t => t.stop());

      let totalLength = 0;
      for (const chunk of jarvisAudioChunks) totalLength += chunk.length;
      if (totalLength < 1600) {
        if (input) input.placeholder = 'Ketik perintah ke JARVIS...';
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
        const res = await fetch('/api/jarvis/voice', { method: 'POST', body: formData });
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
        appendJarvisBubble('jarvis', `Gagal memproses suara: ${err.message}`);
      } finally {
        if (input) input.placeholder = 'Ketik perintah ke JARVIS...';
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

    // App Initialization
    window.addEventListener('DOMContentLoaded', () => {
      if (window.lucide) lucide.createIcons();
      initWebSocket();
      setupTouchpad();
      setupScrollStrip();
      setupJarvisMicListeners();
      loadSystemStatus();
      checkJarvisStatus();

      // Periodic Status Polling
      setInterval(loadSystemStatus, 3500);
      setInterval(checkJarvisStatus, 5000);
    });
  </script>
</body>
</html>
"""

with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print(f"Successfully wrote refactored UI to {INDEX_HTML_PATH}")
