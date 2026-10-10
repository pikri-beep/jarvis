# JARVIS — Local AI Personal Assistant

## 1. Project Overview

Build a personal AI assistant named **JARVIS** for Windows 11.

The goal is to create a practical, voice-enabled personal assistant that runs primarily **locally and for free**, using open-source/local AI technologies wherever possible.

JARVIS should feel like a real computer assistant rather than a simple chatbot.

Example interaction:

> User: "Jarvis, open Chrome."

> JARVIS: "Opening Chrome, sir."

The application must actually open Chrome.

Another example:

> User: "Jarvis, what is the weather tomorrow?"

JARVIS should recognize that this requires current information and use an appropriate web/search capability before answering.

---

# 2. Target Hardware

The primary development machine is:

- Laptop: Acer Aspire A514-56P
- CPU: 13th Gen Intel Core i5-1335U
- CPU: 10 cores / 12 threads
- Max clock: up to 4.60 GHz
- GPU: Intel Iris Xe Graphics
- RAM: 16 GB
- Storage: 512 GB NVMe SSD
- OS: Windows 11 Pro 64-bit

### Hardware constraints

The machine does NOT have a large dedicated NVIDIA GPU.

Therefore:

- Do not assume CUDA is available.
- Do not require a dedicated GPU.
- Prefer CPU-friendly / quantized models.
- Keep RAM usage reasonable.
- Avoid unnecessarily large local models.
- The system must remain usable while JARVIS is running.

Target local model size:

- Preferred: approximately 7B–8B class models.
- Smaller models are acceptable if they significantly improve latency.
- Larger models may be optional, not required.

---

# 3. Core Principles

## 3.1 Local First

Prefer local/open-source components.

Priority:

1. Local
2. Free/open-source
3. Lightweight
4. Reliable
5. Cloud/API only when necessary

Do NOT introduce paid APIs as mandatory dependencies.

If an external API is optional, clearly document it.

---

## 3.2 Modular Architecture

JARVIS must be modular.

Avoid putting all functionality into one giant Python file.

Recommended architecture:

```text
jarvis/
│
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
│
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── router.py
│   │   ├── orchestrator.py
│   │   └── state.py
│   │
│   ├── ai/
│   │   ├── llm.py
│   │   ├── prompts.py
│   │   └── streaming.py
│   │
│   ├── voice/
│   │   ├── wake_word.py
│   │   ├── speech_to_text.py
│   │   └── text_to_speech.py
│   │
│   ├── tools/
│   │   ├── apps.py
│   │   ├── browser.py
│   │   ├── filesystem.py
│   │   ├── windows.py
│   │   └── system.py
│   │
│   ├── memory/
│   │   ├── database.py
│   │   ├── memory.py
│   │   └── schemas.py
│   │
│   └── ui/
│       └── ...
│
├── data/
│   └── .gitkeep
│
├── tests/
│   └── ...
│
└── scripts/
    └── ...
```

The exact structure can be adjusted when implementation reveals a better architecture, but separation of concerns must be maintained.

---

# 4. Technology Direction

Recommended technologies:

### Programming language

**Python 3.11+**

Use Python unless there is a strong technical reason not to.

### Local LLM

Use **Ollama** as the initial local model runtime.

The implementation should make the model configurable.

Example configuration:

```env
JARVIS_MODEL=qwen3:8b
```

Do not hard-code a specific model throughout the application.

### Speech-to-Text

Use a local Whisper-compatible implementation.

Possible choices:

- faster-whisper
- whisper.cpp
- another lightweight local Whisper implementation

Prefer the implementation that provides the best latency/reliability on the target hardware.

### Text-to-Speech

Prefer a local TTS engine.

Possible choices:

- Piper
- another lightweight offline TTS engine

The architecture must allow changing the TTS engine later.

### Memory

Use SQLite initially.

No external database server should be required.

---

# 5. JARVIS Architecture

The system should follow this conceptual architecture:

```text
                 USER
                   │
                   ▼
              🎙️ MICROPHONE
                   │
                   ▼
             SPEECH-TO-TEXT
                   │
                   ▼
              COMMAND ROUTER
                   │
          ┌────────┴─────────┐
          │                  │
          ▼                  ▼
     FAST COMMAND         AI REQUEST
          │                  │
          ▼                  ▼
    LOCAL TOOLS             LLM
          │                  │
          │           ┌──────┴──────┐
          │           │             │
          │           ▼             ▼
          │         MEMORY         TOOLS
          │           │             │
          └───────────┴─────────────┘
                      │
                      ▼
                  RESPONSE
                      │
                      ▼
                    TTS
                      │
                      ▼
                  🔊 SPEAKER
```

---

# 6. Command Router

The router is extremely important.

Do NOT send every command to the LLM.

The router should distinguish between:

### Fast commands

Examples:

- Open Chrome
- Open Spotify
- Open Notepad
- Close Chrome
- Take screenshot
- Increase volume
- Decrease volume
- Create folder
- Open a specific folder
- Lock computer

These should preferably bypass the LLM.

Target:

**~1–2 seconds or less where practical.**

---

### AI requests

Examples:

- Explain quantum computing.
- Summarize this document.
- Help me write an email.
- Analyze this information.
- Remember this information.
- Reason about a complex task.

These can be routed to the local LLM.

---

### Web-dependent requests

Examples:

- What is the latest news?
- What is the weather tomorrow?
- What is the current price?
- Who won today's match?
- What happened today?

These require current external information.

The architecture should support a web/search tool.

Do not pretend that the local model has real-time knowledge.

---

# 7. Voice Interaction

The target interaction is:

```text
User:
"Jarvis, open Chrome."

↓
Wake word detection

↓
Speech-to-text

↓
Command router

↓
open_chrome()

↓
TTS

JARVIS:
"Opening Chrome, sir."
```

The wake word should eventually be configurable.

Default:

```text
Jarvis
```

Do not require the user to manually press a button for every command in the final version.

However, push-to-talk may be implemented first for development/debugging.

---

# 8. Latency Goals

The system should be optimized for responsiveness.

Target latency:

### Fast commands

Target:

**~1–2 seconds**

Example:

```text
"Jarvis, open Chrome."
```

The system should not unnecessarily invoke the LLM.

### AI response

Target:

**~2–5 seconds until first spoken response**, depending on model and hardware.

The exact latency is hardware-dependent.

Streaming should be implemented where practical.

Do not wait for the entire LLM response before beginning TTS if doing so creates unnecessary latency.

---

# 9. Streaming

The LLM should support streaming responses.

Concept:

```text
LLM:

"It..."
     ↓
TTS begins

"is..."
     ↓
TTS continues

"8 PM."
```

The goal is to reduce perceived latency.

However, prioritize natural speech over extremely aggressive streaming.

Do not split speech into awkward fragments.

Implement sentence/chunk buffering where appropriate.

---

# 10. Tools

JARVIS should use explicit tools/functions.

Examples:

```python
open_application()
close_application()
open_url()
search_web()
create_folder()
read_file()
write_file()
take_screenshot()
get_system_info()
set_volume()
lock_windows()
```

The LLM should NOT directly execute arbitrary shell commands.

Instead:

```text
LLM
 ↓
Tool request
 ↓
Tool validation
 ↓
Tool execution
```

This provides safety and predictability.

---

# 11. Security

This is a local computer-control application.

Security is therefore critical.

### Never allow unrestricted arbitrary commands by default.

Avoid designs such as:

```python
os.system(llm_generated_text)
```

or:

```python
subprocess.run(llm_output, shell=True)
```

without strict validation.

Instead, expose explicit functions/tools.

For example:

```python
open_chrome()
```

rather than:

```python
run_any_command("...")
```

---

# 12. Confirmation System

Dangerous actions must require confirmation.

Examples:

- Delete files
- Empty recycle bin
- Shutdown
- Restart
- Format storage
- Modify system configuration
- Send messages/emails
- Execute unknown programs

Example:

> User: "Jarvis, delete the project folder."

JARVIS:

> "That will permanently delete the project folder. Do you want me to continue?"

Only execute after confirmation.

---

# 13. Memory

Use SQLite.

Memory should support:

### Short-term conversation context

Recent conversation messages.

### Long-term memory

Explicit user facts/preferences.

Example:

> "Remember that my preferred browser is Chrome."

Store:

```text
key: preferred_browser
value: Chrome
```

Do not automatically store every conversation.

Memory should be intentional and controllable.

Provide commands such as:

```text
"Jarvis, remember ..."
"Jarvis, forget ..."
"What do you remember about me?"
```

---

# 14. Personality

JARVIS should have a professional, concise assistant personality.

Default characteristics:

- Calm
- Intelligent
- Helpful
- Slightly futuristic
- Professional
- Concise
- Occasionally use "sir" when natural

Avoid excessive roleplay.

Bad:

> "As you command, magnificent master!"

Good:

> "Certainly, sir."

The user should be able to change the personality later.

---

# 15. Error Handling

JARVIS must fail gracefully.

If a command fails:

Bad:

```text
Traceback...
```

Good:

> "I couldn't open Chrome. It looks like Chrome isn't installed at the expected location."

For developers, log the technical error separately.

Use structured logging.

---

# 16. Logging

Maintain useful logs for debugging.

Example:

```text
logs/
    jarvis.log
```

Log:

- Timestamp
- Input type
- Recognized command
- Tool invoked
- Tool result
- Error
- Latency

Do NOT log sensitive information unnecessarily.

Passwords, API keys, tokens and private data must never be logged.

---

# 17. Configuration

Configuration must be centralized.

Example:

```env
JARVIS_NAME=Jarvis
JARVIS_MODEL=qwen3:8b
JARVIS_WAKE_WORD=jarvis
JARVIS_TTS_ENABLED=true
JARVIS_WEB_SEARCH_ENABLED=true
JARVIS_MEMORY_ENABLED=true
```

Use `.env.example`.

Never commit secrets.

---

# 18. Development Roadmap

Build incrementally.

## Phase 0 — Environment

Install and verify:

- Python
- Ollama
- Local LLM
- Required Python packages

Acceptance test:

```text
python app/main.py
```

starts successfully.

---

## Phase 1 — Text JARVIS

Implement:

```text
User text
 ↓
Router
 ↓
LLM
 ↓
Text response
```

Acceptance:

User can have a basic conversation with JARVIS from the terminal.

---

## Phase 2 — Tool System

Implement:

- Open application
- Open website
- File operations
- System commands
- Screenshot

Acceptance:

```text
"open Chrome"
```

actually opens Chrome.

---

## Phase 3 — Voice

Implement:

- Microphone input
- Speech-to-text
- Text-to-speech

Acceptance:

User can speak to JARVIS and hear a spoken response.

---

## Phase 4 — Wake Word

Implement:

```text
"Jarvis"
```

as wake word.

Acceptance:

JARVIS remains idle until activated.

---

## Phase 5 — Memory

Implement SQLite memory.

Acceptance:

```text
"Remember my name is Alex."

...

"What is my name?"

"My name is Alex."
```

---

## Phase 6 — Web Intelligence

Implement a web search abstraction.

Acceptance:

JARVIS can identify when current information is required.

---

## Phase 7 — Desktop UI

Build an optional UI.

Potential interface:

```text
┌─────────────────────────────────┐
│              JARVIS             │
│                                 │
│          ● LISTENING            │
│                                 │
│ User: Open Chrome               │
│                                 │
│ Jarvis: Opening Chrome.         │
│                                 │
│       [ 🎙️ Talk to Jarvis ]     │
└─────────────────────────────────┘
```

UI technology can be selected based on simplicity and performance.

---

# 19. Testing

Every major feature should have tests.

At minimum:

```text
tests/
├── test_router.py
├── test_tools.py
├── test_memory.py
├── test_config.py
└── test_security.py
```

Test tools without actually performing destructive operations.

Mock dangerous operations.

---

# 20. Performance Requirements

JARVIS must remain lightweight.

Avoid:

- Huge background processes
- Unnecessary browser instances
- Large models by default
- Continuous CPU-intensive loops
- Memory leaks
- Repeated model initialization

The LLM runtime should remain loaded when practical rather than reloading the model for every request.

---

# 21. Free / Open-Source Requirement

The core JARVIS functionality must work without paid subscriptions.

Do not make these mandatory:

- OpenAI API
- Anthropic API
- Google paid API
- Paid TTS
- Paid speech recognition
- Paid automation services

Optional integrations may exist behind configuration flags.

---

# 22. Developer Experience

The project must be easy to install.

Provide:

```text
README.md
requirements.txt
.env.example
setup scripts
```

Prefer a setup process such as:

```powershell
git clone <repository>
cd jarvis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app/main.py
```

If additional software such as Ollama is required, clearly document installation.

---

# 23. Agent Instructions

When modifying the project:

1. Read `AGENTS.md` first.
2. Understand the existing architecture before creating new files.
3. Reuse existing abstractions.
4. Do not duplicate functionality.
5. Keep modules small and focused.
6. Do not introduce paid services without explicit approval.
7. Do not introduce unnecessary dependencies.
8. Do not break existing functionality.
9. Add tests for important new behavior.
10. Run relevant tests after changes.
11. Document significant architectural decisions.
12. Prioritize reliability over flashy features.
13. Optimize for the target hardware.
14. Never execute destructive actions without confirmation.
15. Never expose secrets in logs or source code.

---

# 24. Definition of Done — MVP

The MVP is considered successful when all of the following work:

### Voice

```text
User:
"Jarvis"
```

JARVIS activates.

### Conversation

```text
User:
"What can you do?"

JARVIS:
"I can control applications, work with files,
answer questions, search the web, and more."
```

### Application control

```text
"Jarvis, open Chrome."
```

Chrome opens.

### Website

```text
"Jarvis, open YouTube."
```

YouTube opens.

### File

```text
"Jarvis, create a folder called Test
on my Desktop."
```

Folder is created.

### System

```text
"Jarvis, take a screenshot."
```

Screenshot is created.

### AI

```text
"Jarvis, explain relativity in simple terms."
```

Local LLM generates the answer.

### Memory

```text
"Remember that my favorite programming language is Python."

...

"What is my favorite programming language?"
```

JARVIS retrieves the memory.

### Safety

```text
"Delete my Documents folder."
```

JARVIS asks for confirmation instead of executing immediately.

---

# 25. Final Product Vision

The final goal is not to create another chatbot.

The goal is:

> **A local, private, free, voice-controlled AI computer assistant capable of reasoning, remembering, searching, and performing actions on Windows.**

JARVIS should behave as:

```text
             🧠 THINK
                │
                ▼
             🎯 PLAN
                │
                ▼
             🛠️ ACT
                │
                ▼
             🔍 VERIFY
                │
                ▼
             🗣️ RESPOND
```

The assistant should understand the user's intent, select the appropriate tool, perform the action safely, verify the result where possible, and communicate the outcome naturally.

Build incrementally.

Do not attempt to implement every feature simultaneously.

**Start with Phase 0 and Phase 1.**
Do not proceed to advanced voice, memory, vision, or autonomous capabilities until the core architecture is stable.