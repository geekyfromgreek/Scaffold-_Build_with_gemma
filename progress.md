# Scaffold — Progress Tracker

## ✅ Completed

### Phase 1: Project Skeleton
- `pyproject.toml` — build config, dependencies, `scaffold` entry point
- `scaffold/__init__.py` — package init
- `scaffold/cli.py` — Click-based CLI with all 11 subcommands wired up

### Phase 2: Core Watcher + Runner + Display
- `scaffold/watcher.py` — watchdog observer with 2s/9s two-tier debounce, NudgeThrottler for dedup
- `scaffold/runner.py` — subprocess execution for Python (.py) and C (.c) files, timeout handling
- `scaffold/display.py` — rich-based rendering: Syntax panels with line highlighting, nudges, errors, practice questions, efficiency analysis

### Phase 3: Mistake Log
- `scaffold/mistake_log.py` — JSON file storage (~/.scaffold/mistakes.json), deduplication, concept inference heuristics, repeat-pattern detection (3+ triggers practice)

### Phase 4: Ollama Client + Prompts
- `scaffold/ollama_client.py` — Gemma 4 E2B wrapper via ollama Python library, connection/model checks
- `scaffold/prompts.py` — 11 prompt builders with universal NO_CODE_RULE, structured output formats (LINE/ISSUE/WHY, LINE/CURRENT/BETTER)

### Phase 5: AI-Powered CLI Commands
- `scaffold hint` — recent error → AI → LINE/ISSUE/WHY → code context + explanation panels
- `scaffold check <file> --expected` — run → compare → AI logic error detection
- `scaffold review <file>` / `--efficiency` — code quality and Big-O analysis
- `scaffold explain <file>` / `--input` — workflow description and input tracing
- `scaffold answer "<response>"` — practice question evaluation

### Phase 6: Automatic AI Nudges
- NudgeThrottler in watcher — hash-based dedup, one-line nudge after 9s idle, practice suggestion on 3+ repeats

### Phase 7: Image Input
- `scaffold/image_input.py` — drag-and-drop path + clipboard via PIL.ImageGrab
- `scaffold explain-image` CLI command with `--snip` flag

### Phase 8: Voice Input
- `scaffold/voice_input.py` — .wav → Whisper (local base model) → text
- `scaffold ask-voice` CLI command

### Phase 9: Setup & Auto-Start
- `scaffold/setup.py` — Ollama install check/download, model pull with progress, PowerShell $PROFILE hook (idempotent, with confirmation, --remove-hook)

### Phase 10: Documentation
- `progress.md` — this file
- `activeContext.md` — decisions and context
- `scaffold/state.py` — practice question persistence across CLI invocations

## 🔄 In Progress
- Testing and validation on target hardware

## 📋 Pending
- `tests/` — unit tests for prompt builders, display parser, mistake log, runner
- Live mic recording (stretch goal beyond MVP)
- Edge case hardening (large files, binary files, encoding issues)

## ➡️ Next Steps
1. Run `pip install -e .` to install in dev mode
2. Run `scaffold setup` to install Ollama + pull model
3. Test the watcher: `scaffold watch` then edit a .py file with a syntax error
4. Test hint flow: `scaffold hint` after an error is logged
5. Write unit tests for core modules
