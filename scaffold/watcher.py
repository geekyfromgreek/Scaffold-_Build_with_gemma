"""File watcher — monitors .py and .c files for changes and runs syntax checks.

Uses watchdog with a two-tier debounce:
  • 2s idle → instant syntax check (py_compile / gcc), no AI call
  • 8-10s idle → ONE throttled AI nudge if there's an unresolved error

The watcher is designed to run in the background (via shell profile hook)
or manually via `scaffold watch`.
"""

import hashlib
import os
import sys
import time
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from scaffold.display import display_nudge, display_syntax_error, display_error

# How long after last file-change before running a syntax check
SYNTAX_DEBOUNCE_SECONDS = 2.0

# How long after last file-change before generating an AI nudge
NUDGE_DEBOUNCE_SECONDS = 9.0

# Supported file extensions
SUPPORTED_EXTENSIONS = {".py", ".c"}


def _compute_content_hash(filepath: str) -> str | None:
    """Hash the file contents — used to detect if code actually changed."""
    try:
        data = Path(filepath).read_bytes()
        return hashlib.md5(data).hexdigest()
    except OSError:
        return None


def _check_syntax_python(filepath: str) -> dict | None:
    """Check Python syntax by compiling in memory (no .pyc written).

    Uses the builtin compile() instead of py_compile to avoid writing
    bytecode files, which can fail with PermissionError on locked dirs.
    """
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
        compile(source, filepath, "exec")
        return None
    except SyntaxError as e:
        return {
            "error_type": "syntax",
            "file": filepath,
            "line": e.lineno or 0,
            "message": e.msg or str(e),
            "concept": "syntax_error",
        }
    except Exception:
        # File unreadable or other issue — skip silently
        return None


def _check_syntax_c(filepath: str) -> dict | None:
    """Run gcc -fsyntax-only on a C file. Returns error dict or None if clean."""
    import subprocess
    import re

    try:
        result = subprocess.run(
            ["gcc", "-fsyntax-only", filepath],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        # gcc not installed — skip silently (warn once handled by caller)
        return None
    except subprocess.TimeoutExpired:
        return None

    if result.returncode == 0:
        return None

    stderr = result.stderr.strip()
    # Parse first error line:  file.c:10:5: error: ...
    line = 0
    msg = stderr
    m = re.search(r":(\d+):\d+:\s*error:\s*(.*)", stderr)
    if m:
        line = int(m.group(1))
        msg = m.group(2).strip()

    return {
        "error_type": "syntax",
        "file": filepath,
        "line": line,
        "message": msg,
        "concept": "syntax_error",
    }


def check_syntax(filepath: str) -> dict | None:
    """Dispatch syntax check based on file extension."""
    ext = Path(filepath).suffix.lower()
    if ext == ".py":
        return _check_syntax_python(filepath)
    elif ext == ".c":
        return _check_syntax_c(filepath)
    return None


class NudgeThrottler:
    """Ensures each unique error is nudged at most once until the code changes."""

    def __init__(self):
        # {filepath: {"content_hash": str, "error_hash": str, "nudged": bool}}
        self._state: dict[str, dict] = {}
        self._lock = threading.Lock()

    def should_nudge(self, filepath: str, error: dict | None, content_hash: str) -> bool:
        """Returns True if we should fire an AI nudge for this file+error combo."""
        with self._lock:
            prev = self._state.get(filepath, {})

            # Code changed — reset tracking
            if prev.get("content_hash") != content_hash:
                if error is None:
                    # No error and code changed — clear state
                    self._state[filepath] = {
                        "content_hash": content_hash,
                        "error_hash": None,
                        "nudged": False,
                    }
                    return False
                else:
                    err_hash = self._error_hash(error)
                    self._state[filepath] = {
                        "content_hash": content_hash,
                        "error_hash": err_hash,
                        "nudged": False,
                    }
                    return True  # New code + new error → nudge

            # Code unchanged
            if error is None:
                return False  # No error → nothing to nudge

            err_hash = self._error_hash(error)
            if prev.get("error_hash") == err_hash and prev.get("nudged"):
                return False  # Already nudged this exact error — stay silent

            # Same code, but new/different error OR not yet nudged
            self._state[filepath] = {
                "content_hash": content_hash,
                "error_hash": err_hash,
                "nudged": False,
            }
            return True

    def mark_nudged(self, filepath: str):
        """Mark that we've delivered a nudge for the current file state."""
        with self._lock:
            if filepath in self._state:
                self._state[filepath]["nudged"] = True

    @staticmethod
    def _error_hash(error: dict) -> str:
        key = f"{error.get('file', '')}:{error.get('line', '')}:{error.get('message', '')}"
        return hashlib.md5(key.encode()).hexdigest()


class ScaffoldEventHandler(FileSystemEventHandler):
    """Handles file modification events with two-tier debounce."""

    def __init__(self):
        super().__init__()
        self._syntax_timers: dict[str, threading.Timer] = {}
        self._nudge_timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._throttler = NudgeThrottler()
        self._last_errors: dict[str, dict] = {}  # filepath → last syntax error
        self._gcc_warned = False

    def on_modified(self, event):
        if event.is_directory:
            return

        filepath = os.path.abspath(event.src_path)
        ext = Path(filepath).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            return

        # Cancel any pending timers for this file (debounce reset)
        with self._lock:
            if filepath in self._syntax_timers:
                self._syntax_timers[filepath].cancel()
            if filepath in self._nudge_timers:
                self._nudge_timers[filepath].cancel()

            # Schedule syntax check after 2s
            syn_timer = threading.Timer(
                SYNTAX_DEBOUNCE_SECONDS,
                self._run_syntax_check,
                args=(filepath,),
            )
            syn_timer.daemon = True
            syn_timer.start()
            self._syntax_timers[filepath] = syn_timer

            # Schedule AI nudge after 9s
            nudge_timer = threading.Timer(
                NUDGE_DEBOUNCE_SECONDS,
                self._run_nudge_check,
                args=(filepath,),
            )
            nudge_timer.daemon = True
            nudge_timer.start()
            self._nudge_timers[filepath] = nudge_timer

    def _run_syntax_check(self, filepath: str):
        """Tier 1: Fast syntax-only check, no AI call."""
        try:
            if not Path(filepath).exists():
                return

            error = check_syntax(filepath)
            if error is not None:
                # Log to mistake log
                try:
                    from scaffold.mistake_log import log_error
                    log_error(**error)
                except Exception:
                    pass

                self._last_errors[filepath] = error
                display_syntax_error(error)
            else:
                # Error resolved — clear it
                self._last_errors.pop(filepath, None)
        except Exception:
            # Never let internal errors surface as tracebacks to the user
            pass

    def _run_nudge_check(self, filepath: str):
        """Tier 2: Throttled AI nudge for persistent unresolved errors."""
        if not Path(filepath).exists():
            return

        error = self._last_errors.get(filepath)
        content_hash = _compute_content_hash(filepath)
        if content_hash is None:
            return

        if error is None:
            return  # No pending error

        if not self._throttler.should_nudge(filepath, error, content_hash):
            return  # Already nudged or code hasn't changed

        # Check if we should suggest a practice question instead
        try:
            from scaffold.mistake_log import should_generate_practice
            concept = error.get("concept", "")
            if concept and should_generate_practice(concept):
                display_nudge(
                    f"🔄 You've repeated this mistake 3+ times — "
                    f"type `scaffold hint` for a practice question"
                )
                self._throttler.mark_nudged(filepath)
                return
        except Exception:
            pass

        # Generate an AI nudge (1 sentence)
        try:
            from scaffold.ollama_client import query_gemma, is_ollama_running
            from scaffold.prompts import build_nudge_prompt

            if not is_ollama_running():
                return  # Silently skip if Ollama isn't available

            code = Path(filepath).read_text(encoding="utf-8", errors="replace")
            prompt = build_nudge_prompt(code, error)
            response = query_gemma(prompt)
            if response:
                # Trim to one line
                nudge_text = response.strip().split("\n")[0]
                display_nudge(f"💡 {nudge_text} — type `scaffold hint` for more")
        except Exception:
            pass  # Never crash the watcher due to an AI call failure

        self._throttler.mark_nudged(filepath)


def start_watcher(directory: str = ".", daemon: bool = False):
    """Start the file watcher on the given directory.

    Args:
        directory: Directory to watch recursively.
        daemon: If True, runs silently (no startup banner). Used by the profile hook.
    """
    from rich.console import Console

    console = Console()
    watch_path = os.path.abspath(directory)

    if not daemon:
        console.print(
            f"[bold green]👁 Scaffold watcher started[/] — watching [cyan]{watch_path}[/] "
            f"for .py and .c files",
            highlight=False,
        )
        console.print(
            "[dim]Syntax checks every ~2s of idle · AI nudges after ~9s · Ctrl+C to stop[/]",
            highlight=False,
        )

    handler = ScaffoldEventHandler()
    observer = Observer()
    observer.schedule(handler, watch_path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if not daemon:
            console.print("\n[dim]Watcher stopped.[/]")
    finally:
        observer.stop()
        observer.join()
