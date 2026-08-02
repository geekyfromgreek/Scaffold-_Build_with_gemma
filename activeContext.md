# Scaffold — Active Context

## Current Prompt
Building an offline CLI tool for beginner programming students (Python and C) that watches files, catches errors, and delivers AI-powered hints/explanations using a local Gemma 4 E2B model via Ollama. The tool is strictly read-only — it never writes to student files.

## Tech Stack Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| CLI framework | Click | Cleaner multi-command routing than argparse; auto-generated help |
| File watching | watchdog | Mature, cross-platform, event-based (no polling) |
| Syntax check (Python) | py_compile | Stdlib, instant, no external deps |
| Syntax check (C) | gcc -fsyntax-only | Standard, fast, no full compilation |
| Runtime execution | subprocess | Captures stdout/stderr, supports timeouts |
| Local AI | Ollama + Gemma 4 E2B | Fully offline, multimodal (text + image), ~7.2 GB |
| Audio transcription | openai-whisper (local) | Ollama Python client lacks native audio param; Whisper base model runs locally (~140 MB) |
| Image input | PIL.ImageGrab | Clipboard capture on Windows; file bytes for drag-and-drop |
| Terminal UX | rich | Panels, syntax highlighting with line numbers, themes |
| Storage | JSON file | ~/.scaffold/mistakes.json — flat, no database needed |
| Packaging | pyproject.toml + setuptools | Modern standard, `pip install -e .` for dev |
| Auto-start | PowerShell $PROFILE hook | Start-Job for background watcher; idempotent markers |

## Folder Structure
```
scaffold/
 ├── scaffold/
 │    ├── __init__.py          # Package init
 │    ├── cli.py               # Click command group, all subcommands
 │    ├── watcher.py           # Watchdog observer, debounce, nudge throttling
 │    ├── runner.py            # Subprocess execution for .py and .c
 │    ├── prompts.py           # 11 prompt builders with NO_CODE_RULE
 │    ├── ollama_client.py     # Gemma 4 wrapper via ollama library
 │    ├── mistake_log.py       # JSON error persistence, repeat detection
 │    ├── setup.py             # Ollama install, model pull, profile hook
 │    ├── display.py           # Rich-based terminal rendering
 │    ├── image_input.py       # Drag-and-drop + clipboard image handling
 │    ├── voice_input.py       # WAV → Whisper → text pipeline
 │    └── state.py             # Practice question persistence
 │
 ├── tests/                    # Unit tests
 ├── pyproject.toml            # Build config + entry point
 ├── progress.md               # Build progress tracker
 └── activeContext.md          # This file
```

## Features

### Automatic (no manual command)
- **File watcher**: Monitors .py/.c files for changes, runs syntax checks after 2s idle
- **AI nudge**: After 8-10s idle with an unresolved error, prints ONE one-line hint (throttled, no repeats)
- **Practice trigger**: After 3+ repeated mistakes on the same concept, suggests a practice question

### Manual Commands
| Command | Purpose |
|---------|---------|
| `scaffold setup` | Install Ollama, pull model, configure auto-start |
| `scaffold watch` | Manually start the file watcher |
| `scaffold run <file>` | Run a file and capture output |
| `scaffold hint` | Get LINE/ISSUE/WHY hint for recent error |
| `scaffold check <file> --expected "<out>"` | Detect logic errors by comparing outputs |
| `scaffold review <file>` | Code quality review (1-2 suggestions) |
| `scaffold review <file> --efficiency` | Big-O complexity analysis |
| `scaffold explain <file>` | Workflow explanation (3-5 sentences) |
| `scaffold explain <file> --input "<val>"` | Step-by-step input trace |
| `scaffold explain-image <path>` | Explain image (drag-and-drop) |
| `scaffold explain-image --snip` | Explain clipboard screenshot |
| `scaffold ask-voice <audio.wav>` | Voice Q&A via Whisper transcription |
| `scaffold answer "<response>"` | Submit answer to practice question |

## Future Scope
- Live mic recording via sounddevice (currently file-path only)
- Java/other language support
- VS Code extension integration
- Web dashboard for mistake history visualization
- Ollama native audio support (when available in the Python client)
- Multi-file project analysis
- Student progress analytics over time
