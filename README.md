# JARVIS — Local AI Personal Assistant

JARVIS is a local, private, voice-enabled AI personal assistant for Windows 11 built to run primarily offline and without paid APIs, following the principles and roadmap detailed in [AGENTS.md](AGENTS.md).

> 💡 **Panduan Pemula (How-To-Use)**: Baca panduan lengkap penggunaan, tutorial langkah demi langkah, dan katalog kemampuan JARVIS untuk pemula di [how-to-use.md](how-to-use.md).

---

## Current Status: Phase 4 (Always-Listening Local Wake Word) Complete

- **Phase 0 (Environment)**: Verified Python 3.11 virtual environment, local Ollama server connectivity, and local `qwen3:8b` model availability.
- **Phase 1 (Text JARVIS)**:
  - Terminal-based conversation interface (interactive REPL and one-shot CLI query).
  - Command Router separating fast local actions, web-dependent requests, and complex AI reasoning.
  - Local LLM client integrating with Ollama with streaming response support and latency optimization.
- **Phase 2 (Push-to-Talk STT & Fast Commands)**:
  - Local, offline speech-to-text powered by `faster-whisper` (`base` model on CPU with `int8` quantization).
  - Instant deterministic fast commands (time, date, battery, system specs, apps) bypassing the LLM in < 1ms.
- **Phase 3 (Local Text-to-Speech)**:
  - Offline neural speech synthesis powered by `piper-tts` (`en_GB-alan-low` and `id_ID-news_tts-medium`).
  - Sentence-buffered streaming playback and non-blocking background audio playback queue.
- **Phase 3.7 & 3.8 (App Registry & Conversation Experience)**:
  - Configurable application & website registries (Chrome, Edge, WhatsApp, YouTube, etc.).
  - Conversational router guardrails and multi-turn session history.
- **Phase 4 (Always-Listening Local Wake Word)**:
  - 100% local, offline wake-word detection powered by `openWakeWord` with ONNX Runtime (`hey_jarvis_v0.1.onnx`).
  - Explicit 6-state lifecycle state machine preventing self-activation during TTS playback.
  - Two-tone harmonic acknowledgment chime (880 Hz / 1318.5 Hz) synthesized locally without external files.
- **Phase 4.1 (Command Routing & Audio Stability Fixes)**:
  - Deterministic router normalization for colloquial Indonesian and English command variations.
  - Strict execution contract: actions execute exactly once, zero hallucinated tool executions.
  - Single-owner microphone lifecycle eliminating PortAudio device conflicts (`-9996`) and PTT signal starvation.
  - Pre-STT energy gate rejecting silence and background noise without non-VAD hallucinations.
  - Added Instagram support (`WebsiteRegistry`) and Whisper domain vocabulary priming.

---

## Architecture Overview

```text
User Text
    │
    ▼
Terminal Interface (app/main.py)
    │
    ▼
Command Router (app/core/router.py)
    │
    ├──────────────┬────────────────────────┬──────────────────────┐
    ▼              ▼                        ▼                      ▼
Terminal Cmd   Fast Command (Phase 2)   Web Dependent (Phase 6)  AI Request (Phase 1)
(/help, /exit) (open app, lock, etc.)   (weather, news, etc.)          │
    │              │                        │                          ▼
 Immediate      Simulated                Acknowledge             OllamaClient
 Response       Confirmation             Data Need              (app/ai/llm.py)
                                                                       │
                                                                       ▼
                                                                  qwen3:8b
                                                                       │
                                                                       ▼
                                                             Streaming Output
```

### Directory Structure

```text
JARVIS/
├── AGENTS.md                  # Project specification & guidelines
├── README.md                  # Setup and usage documentation
├── requirements.txt           # Project dependencies
├── .env.example               # Example configuration template
├── .env                       # Local active environment configuration
│
├── app/
│   ├── main.py                # Terminal application entry point
│   ├── core/
│   │   ├── config.py          # Centralized settings & environment loader
│   │   ├── router.py          # Intent classification & command routing
│   │   ├── orchestrator.py    # Coordination between Router, LLM, and State
│   │   ├── state.py           # In-memory session and conversation history
│   │   └── logger.py          # Structured logging and credential redaction
│   │
│   ├── ai/
│   │   ├── llm.py             # Ollama local LLM client
│   │   ├── prompts.py         # JARVIS personality and system prompts
│   │   └── streaming.py       # Streaming processor & tag filtering
│   │
│   ├── voice/                 # (Phases 3-4: STT, TTS, Wake Word)
│   ├── tools/                 # (Phase 2: Windows, Apps, Filesystem)
│   ├── memory/                # (Phase 5: SQLite persistent memory)
│   └── ui/                    # (Phase 7: Optional GUI)
│
├── data/                      # Persistent storage directory
├── logs/                      # Log files (jarvis.log)
├── tests/                     # Unit and integration test suite
└── scripts/                   # Setup and utility scripts
```

---

## Prerequisites

1. **Operating System**: Windows 11 (64-bit).
2. **Python**: Python 3.11+ (in `.venv`).
3. **Ollama**:
   - Installed and running locally (`http://localhost:11434`).
   - Download the target model:
     ```powershell
     ollama pull qwen3:8b
     ```

---

## Installation & Setup

1. **Activate Virtual Environment**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Copy `.env.example` to `.env` if not already present:
   ```powershell
   Copy-Item .env.example .env
   ```

   Key configuration variables in `.env`:
   - `JARVIS_NAME`: Assistant name (default: `Jarvis`).
   - `JARVIS_MODEL`: Ollama model tag (default: `qwen3:8b`).
   - `JARVIS_OLLAMA_URL`: Ollama endpoint (default: `http://localhost:11434`).
   - `JARVIS_KEEP_ALIVE`: Model retention period in memory (default: `15m`).
   - `JARVIS_TEMPERATURE`: Sampling temperature (default: `0.7`).
   - `JARVIS_LOG_LEVEL`: Logging verbosity (default: `INFO`).

---

## Usage

### 1. Interactive Terminal REPL

Launch JARVIS in interactive mode:

```powershell
python app/main.py
```

Example interaction:

```text
================================================================
       JARVIS - Local AI Personal Assistant
================================================================
 Model:         qwen3:8b [Available]
 Ollama:        http://localhost:11434 [Connected]
 Architecture:  Phase 1 (Terminal Interface & Local LLM)
 Commands:      Type '/help' for commands, '/exit' to quit
----------------------------------------------------------------

You > Who are you?

Jarvis > I am JARVIS, your AI personal assistant, seamlessly integrated into Windows 11. I am designed to assist with tasks, answer questions, and provide support while maintaining a calm, professional demeanor. How can I assist you today, sir?

You > /status

Jarvis > JARVIS Status:
  Identity:        Jarvis
  Ollama Server:   http://localhost:11434 [ONLINE]
  Active Model:    qwen3:8b [READY]
  History Length:  2 messages

You > /exit

Jarvis > Shutting down. Good day, sir.
```

### 2. Always-Listening Wake Word Mode (Phase 4)

Launch JARVIS in hands-free always-listening mode:

```powershell
python app/main.py --wake
```

Or toggle always-listening mode inside the REPL by typing `/wake`.

**Interaction Flow:**
1. State: `LISTENING_FOR_WAKE_WORD` (runs lightweight ONNX inference at ~3.1ms per 80ms chunk; no Whisper or Qwen3 idle load).
2. Say: **"Hey Jarvis"**
3. JARVIS immediately acknowledges with a digital chime and visually transitions:
   `🔔 [WAKE WORD DETECTED: 'Hey Jarvis'] Listening for command...`
4. State: `CAPTURING_COMMAND` records subsequent speech until silence is detected.
5. Audio is transcribed via faster-whisper, routed to fast command or LLM, and spoken aloud via Piper TTS.
6. The detector remains paused during speech output to prevent self-retriggering, flushes historical buffers, and resumes listening after playback completes.

### 3. Push-to-Talk Voice Mode

Launch JARVIS in push-to-talk voice input mode:

```powershell
python app/main.py --ptt
```

Or toggle push-to-talk mode anytime inside the interactive REPL by typing `/ptt`.

**Interaction Flow:**
1. When prompted: `You [🎙️ Press ENTER to speak, or type command] > `
2. Press **ENTER** on the empty line.
3. JARVIS indicates: `● [RECORDING...] Speak now. (Press ENTER when done)`
4. Speak your request (e.g., *"Open Chrome"*).
5. Press **ENTER** to stop recording.
6. The audio is transcribed offline by `faster-whisper`, routed automatically, and spoken aloud through your speakers via Piper TTS.

### 4. Text-to-Speech (TTS) Voice Controls

- **Runtime Toggle**: Inside the terminal REPL, type `/tts` to toggle voice responses on or off.
- **Launch Without Audio**: Use `--no-tts` to run in silent terminal-only mode:
  ```powershell
  python app/main.py --no-tts
  ```
- **Language Support**: English (`en_GB-alan-low`) and Indonesian (`id_ID-news_tts-medium`) models are cached locally in `data/models/piper/`.

### 5. Single-Query Non-Interactive Mode

Run a single prompt and receive the streamed response directly:

```powershell
python app/main.py --query "Explain the difference between RAM and storage in 2 sentences."
```

---

## Running Tests

Execute the automated test suite with `pytest`:

```powershell
.\.venv\Scripts\pytest.exe
```

Test coverage includes 71 automated tests across:
- `tests/test_config.py`: Settings loading and environment overrides.
- `tests/test_router.py`: Classification of terminal, fast, web, and AI commands.
- `tests/test_apps.py`: Application registry, path discovery, protocol handlers, WhatsApp safety, and process management.
- `tests/test_browser.py`: Deterministic website launching, Chrome prioritization, and URL mapping.
- `tests/test_conversation_context.py`: Multi-turn session context, sliding window history, pronoun resolution, and router guardrails.
- `tests/test_llm.py`: Ollama client health checks, streaming, and error handling.
- `tests/test_orchestrator.py`: Multi-component end-to-end integration flow.
- `tests/test_voice.py`: Faster-Whisper transcription, silence thresholds, audio resampling, and recorder lifecycle.
- `tests/test_tts.py`: Piper speech synthesis, markdown text cleaning, sentence buffering, phonetic normalization, and playback queue lifecycle.
- `tests/test_wake_word.py`: openWakeWord detector lifecycle, state machine transitions, acknowledgment chime synthesis, and self-activation prevention during TTS.
- `tests/test_user_simulator.py`: In-memory audio injection, Groq cognitive persona planner, Edge-TTS voice generation, and multi-modal Windows OS state verification.

---

## Simulated User Agent (Voice E2E Human Tester)

JARVIS features a dedicated autonomous **Simulated User Agent** that tests JARVIS by actually using it like a real human being:
- **Speaks with realistic human voice** (via Microsoft Edge-TTS neural voices).
- **Injects 16kHz PCM audio** into JARVIS's STT / wake-word pipeline in real-time.
- **Inspects Windows OS state** (verifying processes like `notepad.exe` or `chrome.exe` via `psutil`).
- **Live Terminal Dashboard** displaying two-way dialogue, latency meters (TTFT, STT, TTS), and a scorecard.
- **Powered by Groq Cloud API** (free, ultra-fast LLM persona) with smart deterministic fallback if no API key is set.

### Usage

```powershell
# List all available testing scenarios
python scripts/run_user_simulator.py --list

# Run Scenario SC-01 (Desktop & App Automation)
python scripts/run_user_simulator.py --scenario SC-01

# Run fast validation mode (skips human conversational pauses)
python scripts/run_user_simulator.py --scenario SC-01 --fast

# Run all scenarios sequentially
python scripts/run_user_simulator.py --scenario all --fast
```

---

## Roadmap

- [x] **Phase 0**: Local Environment verification (Python 3.11, Ollama, Qwen3:8b).
- [x] **Phase 1**: Text JARVIS (Terminal REPL, Ollama client, Command Router, Logging, Tests).
- [x] **Phase 2 (STT & Fast Commands)**: Local offline microphone input (`sounddevice` + `faster-whisper`), instant system command bypass.
- [x] **Phase 3 (Text-to-Speech)**: Offline neural speech synthesis (Piper TTS with sentence-buffered streaming and non-blocking playback).
- [x] **Phase 4 (Wake Word)**: Always-listening offline activation keyword ("Hey Jarvis" via openWakeWord + ONNX Runtime).
- [ ] **Phase 5 (Memory)**: Persistent Memory (SQLite short/long term facts).
- [ ] **Phase 6 (Web Intelligence)**: Web search abstraction.
- [ ] **Phase 7 (Desktop UI)**: Lightweight Windows desktop interface.
