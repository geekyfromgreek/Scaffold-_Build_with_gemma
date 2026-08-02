"""Display — all terminal output rendering via the rich library.

This module is the ONLY place that prints to the terminal.
It reads student files for context display but NEVER writes to them.

Provides:
  • parse_model_response() — regex extraction of LINE/ISSUE/WHY format
  • display_syntax_error() — compact syntax error print with code segment
  • display_nudge() — simple dim nudge text print
  • display_hint_response() — code context panel + explanation panel
  • display_streamed_explanation() — live-streamed prose explanation
  • display_practice() — practice question panel
  • display_error() — generic error message
"""

import os
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme
from rich.markdown import Markdown
from rich.live import Live
from typing import Generator

# Force UTF-8 output on Windows to avoid cp1252 emoji encoding errors
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Consistent theme across all output
SCAFFOLD_THEME = Theme({
    "scaffold.hint": "bold cyan",
    "scaffold.error": "bold red",
    "scaffold.success": "bold green",
    "scaffold.nudge": "dim italic",
    "scaffold.label": "bold magenta",
})

console = Console(theme=SCAFFOLD_THEME, force_terminal=True)


# Response parsing

def parse_model_response(raw: str) -> list[dict]:
    """Parse LINE/ISSUE/WHY/HINT blocks from model output.

    Handles responses like:
        LINE: 7
        ISSUE: Missing colon after if statement
        WHY: Python requires a colon to start a block
        HINT: Add a colon at the end of the line

    Returns a list of dicts, each with keys: line, issue, why, hint.
    Multiple blocks are separated by blank lines or repeated LINE: headers.
    """
    blocks = []
    current: dict = {}

    for text_line in raw.strip().splitlines():
        text_line = text_line.strip()

        m_line = re.match(r"^LINE:\s*(\d+)", text_line, re.IGNORECASE)
        m_issue = re.match(r"^ISSUE:\s*(.*)", text_line, re.IGNORECASE)
        m_why = re.match(r"^WHY:\s*(.*)", text_line, re.IGNORECASE)
        m_hint = re.match(r"^HINT:\s*(.*)", text_line, re.IGNORECASE)

        if m_line:
            # Start a new block (save previous if it exists)
            if current:
                blocks.append(current)
            current = {"line": int(m_line.group(1)), "issue": "", "why": "", "hint": ""}
        elif m_issue and current:
            current["issue"] = m_issue.group(1).strip()
        elif m_why and current:
            current["why"] = m_why.group(1).strip()
        elif m_hint and current:
            current["hint"] = m_hint.group(1).strip()

    if current:
        blocks.append(current)

    return blocks


# Code context extraction

def _extract_code_context(filepath: str, target_line: int, context: int = 3) -> tuple[str, int, int]:
    """Read a file and extract lines around a target line.

    Returns (code_snippet, start_line, end_line) — all 1-indexed.
    """
    try:
        lines = Path(filepath).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ("", 1, 1)

    total = len(lines)
    start = max(1, target_line - context)
    end = min(total, target_line + context)

    snippet = "\n".join(lines[start - 1 : end])
    return (snippet, start, end)


def _get_lexer(filepath: str) -> str:
    """Return the rich Syntax lexer name for a file."""
    ext = Path(filepath).suffix.lower()
    return {"py": "python", ".py": "python", ".c": "c"}.get(ext, "text")


# Display functions

def display_syntax_error(error: dict):
    """Show a compact syntax error with the offending code line from the watcher."""
    filepath = error["file"]
    filename = Path(filepath).name
    line_num = error.get("line", 0)
    msg = error.get("message", "Syntax error")
    if len(msg) > 120:
        msg = msg[:117] + "..."

    console.print(
        f"[scaffold.error]✗ Syntax error[/] in [bold]{filename}[/] "
        f"line [yellow]{line_num}[/]: {msg}"
    )

    # Show the offending line and surrounding context
    if line_num and line_num > 0:
        try:
            lines = Path(filepath).read_text(encoding="utf-8", errors="replace").splitlines()
            start = max(0, line_num - 2)
            end = min(len(lines), line_num + 1)
            code_lines = []
            for i in range(start, end):
                marker = "→" if i == line_num - 1 else " "
                style = "bold red" if i == line_num - 1 else "dim"
                code_lines.append(f"  [{style}]{marker} {i + 1:>3} │ {lines[i]}[/]")
            if code_lines:
                console.print("\n".join(code_lines))
        except Exception:
            pass


def display_nudge(message: str):
    """Print a subtle one-line automatic nudge — no panel, no box."""
    console.print(f"[scaffold.nudge]{message}[/]")


def display_error(message: str):
    """Display a generic error message."""
    console.print(f"[scaffold.error]✗ {message}[/]")


def display_hint_response(filepath: str, raw_response: str):
    """Parse and display a LINE/ISSUE/WHY hint response with code context."""
    blocks = parse_model_response(raw_response)

    if not blocks:
        # Model didn't follow the format — display as plain text
        console.print(Panel(
            Markdown(raw_response.strip()),
            title="[bold]💡 Hint[/]",
            border_style="cyan",
            padding=(1, 2),
        ))
        return

    for block in blocks:
        line_num = block.get("line", 0)
        issue = block.get("issue", "")
        why = block.get("why", "")
        hint = block.get("hint", "")

        # Code context panel
        if line_num > 0 and filepath and Path(filepath).exists():
            snippet, start, end = _extract_code_context(filepath, line_num)
            lexer = _get_lexer(filepath)
            syntax = Syntax(
                snippet,
                lexer,
                line_numbers=True,
                start_line=start,
                highlight_lines={line_num},
                theme="monokai",
                padding=1,
            )
            console.print(Panel(
                syntax,
                title=f"[bold]📍 {Path(filepath).name} — Line {line_num}[/]",
                border_style="cyan",
                padding=(0, 0),
            ))

        # Explanation panel
        explanation_parts = []
        if issue:
            explanation_parts.append(f"**ISSUE:** {issue}")
        if why:
            explanation_parts.append(f"**WHY:** {why}")
        if hint:
            explanation_parts.append(f"**HINT:** {hint}")

        if explanation_parts:
            console.print(Panel(
                Markdown("\n\n".join(explanation_parts)),
                border_style="blue",
                padding=(1, 2),
            ))


def display_streamed_explanation(source: str, stream: Generator[str, None, None]):
    """Stream a prose explanation dynamically."""
    source_name = Path(source).name if Path(source).exists() else source
    content = ""
    
    with Live(Panel(Markdown(content), title=f"[bold]📖 Explanation — {source_name}[/]", border_style="magenta", padding=(1, 2)), console=console, refresh_per_second=50) as live:
        for chunk in stream:
            content += chunk
            live.update(Panel(Markdown(content.strip()), title=f"[bold]📖 Explanation — {source_name}[/]", border_style="magenta", padding=(1, 2)))


def display_practice(question: str):
    """Display a practice question in a distinct panel."""
    console.print(Panel(
        Markdown(question.strip()),
        title="[bold]🎯 Practice Question[/]",
        subtitle="[dim]Type your answer below or press Ctrl+C to exit[/]",
        border_style="yellow",
        padding=(1, 2),
    ))
