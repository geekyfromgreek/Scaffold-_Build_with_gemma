"""Setup — self-contained installer for all Scaffold dependencies.

Handles:
  1. Ollama installation check (downloads & installs if missing)
  2. Model pull (gemma4:e2b, ~7.2 GB)
  3. PowerShell $PROFILE hook for auto-starting the watcher
  4. Readiness verification

Safe to re-run — every step is idempotent.
"""

import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
MODEL_TAG = "gemma4:e2b"
PROFILE_MARKER_START = "# --- Scaffold Auto-Start ---"
PROFILE_MARKER_END = "# --- End Scaffold Auto-Start ---"

PROFILE_HOOK_BLOCK = f"""{PROFILE_MARKER_START}
if (Get-Command scaffold -ErrorAction SilentlyContinue) {{
    Start-Job -ScriptBlock {{ scaffold watch --daemon }} | Out-Null
}}
{PROFILE_MARKER_END}"""


# Ollama installation

def _is_ollama_installed() -> bool:
    """Check if Ollama CLI is available on PATH."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _install_ollama():
    """Download and silently install Ollama on Windows."""
    console.print("\n[bold yellow]⬇ Downloading Ollama installer...[/]", highlight=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        installer_path = os.path.join(tmpdir, "OllamaSetup.exe")

        try:
            urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, installer_path)
        except Exception as e:
            console.print(f"[bold red]✗ Download failed:[/] {e}", highlight=False)
            console.print(
                "[dim]Download Ollama manually from https://ollama.com/download[/]",
                highlight=False,
            )
            return False

        console.print("[bold yellow]📦 Installing Ollama (this may take a moment)...[/]", highlight=False)

        try:
            result = subprocess.run(
                [installer_path, "/S"],  # /S = silent install
                timeout=120,
            )
            if result.returncode != 0:
                console.print(
                    f"[bold red]✗ Installer exited with code {result.returncode}.[/]",
                    highlight=False,
                )
                return False
        except subprocess.TimeoutExpired:
            console.print("[bold red]✗ Installer timed out.[/]", highlight=False)
            return False
        except Exception as e:
            console.print(f"[bold red]✗ Installation failed:[/] {e}", highlight=False)
            return False

    # Verify after install (might need PATH refresh)
    if _is_ollama_installed():
        console.print("[bold green]✓ Ollama installed successfully.[/]", highlight=False)
        return True
    else:
        console.print(
            "[bold yellow]⚠ Ollama was installed but isn't on PATH yet.[/]\n"
            "  Close and re-open your terminal, then run [bold]scaffold setup[/] again.",
            highlight=False,
        )
        return False


# Model pull

def _is_model_pulled() -> bool:
    """Check if the required model is already available."""
    try:
        from scaffold.ollama_client import is_model_available
        return is_model_available()
    except Exception:
        return False


def _pull_model():
    """Pull the Gemma 4 model via Ollama CLI with live progress output."""
    console.print(
        f"\n[bold yellow]⬇ Pulling model '{MODEL_TAG}' (~7.2 GB)...[/]\n"
        f"[dim]This may take a while on the first run. Go grab a coffee ☕[/]",
        highlight=False,
    )

    try:
        # Use subprocess for live output streaming
        process = subprocess.Popen(
            ["ollama", "pull", MODEL_TAG],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )

        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if line:
                console.print(f"  [dim]{line}[/]", highlight=False)

        process.wait()

        if process.returncode == 0:
            console.print(f"[bold green]✓ Model '{MODEL_TAG}' is ready.[/]", highlight=False)
            return True
        else:
            console.print(f"[bold red]✗ Model pull failed (exit code {process.returncode}).[/]", highlight=False)
            return False

    except FileNotFoundError:
        console.print("[bold red]✗ Ollama CLI not found. Install Ollama first.[/]", highlight=False)
        return False
    except Exception as e:
        console.print(f"[bold red]✗ Model pull failed:[/] {e}", highlight=False)
        return False


# PowerShell profile hook

def _get_profile_path() -> str | None:
    """Get the PowerShell $PROFILE path."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "echo $PROFILE"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        path = result.stdout.strip()
        return path if path else None
    except Exception:
        return None


def _is_hook_installed(profile_path: str) -> bool:
    """Check if the Scaffold auto-start hook is already in the profile."""
    try:
        content = Path(profile_path).read_text(encoding="utf-8")
        return PROFILE_MARKER_START in content
    except (OSError, FileNotFoundError):
        return False


def _install_hook(profile_path: str) -> bool:
    """Add the Scaffold auto-start block to the PowerShell profile."""
    profile = Path(profile_path)

    try:
        # Create parent directories and file if they don't exist
        profile.parent.mkdir(parents=True, exist_ok=True)

        existing = ""
        if profile.exists():
            existing = profile.read_text(encoding="utf-8")

        # Don't add twice
        if PROFILE_MARKER_START in existing:
            console.print("[dim]Profile hook already installed.[/]", highlight=False)
            return True

        # Append the hook
        with open(profile, "a", encoding="utf-8") as f:
            f.write(f"\n{PROFILE_HOOK_BLOCK}\n")

        console.print("[bold green]✓ Auto-start hook added to PowerShell profile.[/]", highlight=False)
        console.print(f"  [dim]{profile_path}[/]", highlight=False)
        return True

    except Exception as e:
        console.print(f"[bold red]✗ Could not update profile:[/] {e}", highlight=False)
        return False


def remove_profile_hook():
    """Remove the Scaffold auto-start hook from the PowerShell profile."""
    profile_path = _get_profile_path()
    if not profile_path:
        console.print("[bold red]✗ Could not locate PowerShell profile.[/]", highlight=False)
        return

    profile = Path(profile_path)
    if not profile.exists():
        console.print("[dim]No profile file found — nothing to remove.[/]", highlight=False)
        return

    content = profile.read_text(encoding="utf-8")
    if PROFILE_MARKER_START not in content:
        console.print("[dim]No Scaffold hook found in profile — nothing to remove.[/]", highlight=False)
        return

    # Remove the block between markers (inclusive)
    import re
    pattern = re.compile(
        rf"\n?{re.escape(PROFILE_MARKER_START)}.*?{re.escape(PROFILE_MARKER_END)}\n?",
        re.DOTALL,
    )
    cleaned = pattern.sub("\n", content).strip() + "\n"

    profile.write_text(cleaned, encoding="utf-8")
    console.print("[bold green]✓ Auto-start hook removed from PowerShell profile.[/]", highlight=False)


# Main setup orchestrator

def run_setup():
    """Run the full setup flow: Ollama → model → profile hook."""
    console.print(Panel(
        "[bold cyan]Scaffold: The Offline AI Tutor (Gemma for Good)[/]\n\n"
        "Scaffold is a privacy-first, fully local programming tutor for students.\n"
        "It watches your code, catches errors instantly, and guides you to the right answer\n"
        "using Google's Gemma models—without ever writing the code for you or needing the cloud!\n\n"
        "[bold]Installation Steps:[/]\n"
        "  1. Check/install Ollama (local AI runtime)\n"
        "  2. Pull the Gemma 4 E2B model (~7.2 GB)\n"
        "  3. Check voice dependencies (FFmpeg & Whisper)\n"
        "  4. Configure your terminal to auto-start the code watcher",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Step 1: Ollama
    console.print("\n[bold]Step 1/4 — Ollama[/]", highlight=False)
    if _is_ollama_installed():
        console.print("[bold green]✓ Ollama is already installed.[/]", highlight=False)
    else:
        console.print("[dim]Ollama not found. Installing...[/]", highlight=False)
        if not _install_ollama():
            console.print(
                "\n[bold red]Setup paused.[/] Install Ollama manually, then re-run [bold]scaffold setup[/].",
                highlight=False,
            )
            return

    # Step 2: Model
    console.print("\n[bold]Step 2/4 — AI Model[/]", highlight=False)
    if _is_model_pulled():
        console.print(f"[bold green]✓ Model '{MODEL_TAG}' is already available.[/]", highlight=False)
    else:
        if not _pull_model():
            console.print(
                f"\n[bold red]Setup paused.[/] Pull the model manually with: "
                f"[bold]ollama pull {MODEL_TAG}[/]",
                highlight=False,
            )
            return

    # Step 3: Voice Dependencies (FFmpeg & Whisper Model)
    console.print("\n[bold]Step 3/4 — Voice Dependencies[/]", highlight=False)
    
    # Check FFmpeg
    import shutil
    if shutil.which("ffmpeg"):
        console.print("[bold green]✓ FFmpeg is installed.[/]", highlight=False)
    else:
        console.print(
            "[bold yellow]⚠ FFmpeg not found.[/]\n"
            "  Voice commands require FFmpeg. Open a new terminal and run:\n"
            "  [bold]winget install ffmpeg[/]",
            highlight=False,
        )

    # Download Whisper Model
    console.print("[dim]Checking Whisper AI model...[/]", highlight=False)
    try:
        import whisper
        # This will download the model to cache if it doesn't exist
        whisper.load_model("base")
        console.print("[bold green]✓ Whisper 'base' model is ready.[/]", highlight=False)
    except Exception as e:
        console.print(
            f"[bold yellow]⚠ Could not download Whisper model:[/] {e}\n"
            "  It will try again the first time you use a voice command.",
            highlight=False,
        )

    # Step 4: Profile hook
    console.print("\n[bold]Step 4/4 — Auto-Start Hook[/]", highlight=False)
    profile_path = _get_profile_path()
    if profile_path:
        if _is_hook_installed(profile_path):
            console.print("[bold green]✓ Auto-start hook already installed.[/]", highlight=False)
        else:
            console.print(
                "[dim]This will add a small block to your PowerShell profile so "
                "the watcher starts automatically in new terminals.[/]",
                highlight=False,
            )
            # Ask for confirmation
            try:
                answer = input("  Add auto-start hook? [Y/n]: ").strip().lower()
                if answer in ("", "y", "yes"):
                    _install_hook(profile_path)
                else:
                    console.print("[dim]Skipped. You can start the watcher manually with: scaffold watch[/]",
                                  highlight=False)
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Skipped.[/]", highlight=False)
    else:
        console.print(
            "[bold yellow]⚠ Could not locate PowerShell profile.[/] "
            "You can start the watcher manually with: [bold]scaffold watch[/]",
            highlight=False,
        )

    # Final status
    console.print(Panel(
        "[bold green]✓ Scaffold is ready![/]\n\n"
        "Quick start:\n"
        "  • The watcher starts automatically in new terminals\n"
        "  • Write some code and save — errors are detected in ~2 seconds\n"
        "  • Type [bold]scaffold hint[/] for help with errors\n"
        "  • Type [bold]scaffold --help[/] to see all commands",
        border_style="green",
        padding=(1, 2),
    ))

    # Start the watcher immediately so the user doesn't have to open a new terminal
    console.print("\n[bold]Starting watcher...[/]", highlight=False)
    from scaffold.watcher import start_watcher
    start_watcher(".", daemon=False)
