"""Simple state persistence for cross-command data (e.g. last practice question).

Stores state in ~/.scaffold/state.json — small, flat, and disposable.
"""

import json
from pathlib import Path

STATE_DIR = Path.home() / ".scaffold"
STATE_FILE = STATE_DIR / "state.json"


def _ensure_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict:
    _ensure_dir()
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict):
    _ensure_dir()
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def save_last_practice(concept: str, question: str):
    """Persist the most recent practice question so `scaffold answer` can retrieve it."""
    state = _load_state()
    state["last_practice"] = {"concept": concept, "question": question}
    _save_state(state)


def load_last_practice() -> dict | None:
    """Retrieve the most recent practice question, or None."""
    state = _load_state()
    return state.get("last_practice")

def clear_last_practice():
    """Clear the active practice question so 'answer' behaves normally again."""
    state = _load_state()
    if "last_practice" in state:
        del state["last_practice"]
        _save_state(state)
