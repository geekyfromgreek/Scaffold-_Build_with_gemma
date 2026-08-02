"""Mistake log — persistent JSON storage for tracking student errors.

Stores errors in ~/.scaffold/mistakes.json as a flat JSON array.
Supports repeat-pattern detection for triggering practice questions.
Thread-safe via simple file locking.
"""

import json
import time
from pathlib import Path
from threading import Lock

LOG_DIR = Path.home() / ".scaffold"
LOG_FILE = LOG_DIR / "mistakes.json"

_file_lock = Lock()


def _ensure_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _load_log() -> list[dict]:
    """Load the full mistake log from disk."""
    _ensure_dir()
    if LOG_FILE.exists():
        try:
            data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_log(entries: list[dict]):
    """Write the full mistake log to disk."""
    _ensure_dir()
    LOG_FILE.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")


def log_error(
    error_type: str,
    file: str,
    line: int,
    message: str,
    concept: str = "",
) -> dict:
    """Append an error to the mistake log.

    Args:
        error_type: "syntax", "runtime", or "logic"
        file: Absolute path to the source file
        line: Line number (0 if unknown)
        message: Error message text
        concept: Category/concept tag (e.g., "indentation", "missing_semicolon")

    Returns:
        The logged entry dict.
    """
    entry = {
        "error_type": error_type,
        "file": file,
        "line": line,
        "message": message,
        "concept": concept or _infer_concept(error_type, message),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    with _file_lock:
        entries = _load_log()

        # Deduplicate: don't log the exact same error back-to-back
        if entries:
            last = entries[-1]
            if (
                last.get("file") == entry["file"]
                and last.get("line") == entry["line"]
                and last.get("message") == entry["message"]
            ):
                return entry  # Skip duplicate

        entries.append(entry)

        # Keep log manageable — retain last 500 entries
        if len(entries) > 500:
            entries = entries[-500:]

        _save_log(entries)

    return entry


def get_recent_error() -> dict | None:
    """Return the most recent logged error, or None if the log is empty."""
    with _file_lock:
        entries = _load_log()
    return entries[-1] if entries else None


def get_repeat_count(concept: str) -> int:
    """Count how many times a concept has appeared in the log."""
    with _file_lock:
        entries = _load_log()
    return sum(1 for e in entries if e.get("concept") == concept)


def should_generate_practice(concept: str) -> bool:
    """Returns True if the concept has been logged 3+ times — time for practice."""
    return get_repeat_count(concept) >= 3


def get_concept_errors(concept: str, limit: int = 5) -> list[dict]:
    """Return the most recent errors for a given concept."""
    with _file_lock:
        entries = _load_log()
    matching = [e for e in entries if e.get("concept") == concept]
    return matching[-limit:]


def _infer_concept(error_type: str, message: str) -> str:
    """Attempt to tag an error with a concept based on keywords in the message.

    This is a best-effort heuristic — the AI model may provide better tags.
    """
    msg_lower = message.lower()

    # Python syntax patterns
    if "indentation" in msg_lower or "indent" in msg_lower:
        return "indentation"
    if "unexpected eof" in msg_lower or "unterminated" in msg_lower:
        return "unclosed_block"
    if "invalid syntax" in msg_lower:
        return "syntax_error"
    if "name" in msg_lower and "not defined" in msg_lower:
        return "undefined_variable"
    if "typeerror" in msg_lower:
        return "type_error"
    if "indexerror" in msg_lower or "out of range" in msg_lower:
        return "index_error"
    if "keyerror" in msg_lower:
        return "key_error"
    if "attributeerror" in msg_lower:
        return "attribute_error"
    if "importerror" in msg_lower or "modulenotfounderror" in msg_lower:
        return "import_error"

    # C syntax patterns
    if "expected" in msg_lower and ";" in msg_lower:
        return "missing_semicolon"
    if "undeclared" in msg_lower or "undeclared identifier" in msg_lower:
        return "undeclared_variable"
    if "implicit declaration" in msg_lower:
        return "missing_include"

    return error_type
