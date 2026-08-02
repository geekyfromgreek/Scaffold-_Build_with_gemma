"""Setup — self-contained installer for all Scaffold dependencies.

Handles:
  1. Ollama installation check (downloads & installs if missing)
  2. Model pull (gemma4:e2b, ~7.2 GB)

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


# Main setup orchestrator

def run_setup():
    """Run the full setup flow: Ollama → model."""
    console.print(Panel(
        "[bold cyan]Scaffold: The Offline AI Tutor (Gemma for Good)[/]\n\n"
        "Scaffold is a privacy-first, fully local programming tutor for students.\n"
        "It assists you locally while you code using Google's Gemma models,\n"
        "without ever writing the code for you or needing the cloud!\n\n"
        "[bold]Installation Steps:[/]\n"
        "  1. Check/install Ollama (local AI runtime)\n"
        "  2. Pull the Gemma 4 E2B model (~7.2 GB)",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Step 1: Ollama
    console.print("\n[bold]Step 1/2 — Ollama[/]", highlight=False)
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
    console.print("\n[bold]Step 2/2 — AI Model[/]", highlight=False)
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

    # Final status
    console.print(Panel(
        "[bold green]✓ Scaffold is ready![/]\n\n"
        "Quick start:\n"
        "  • Type [bold]scaffold answer[/] to ask programming questions\n"
        "  • Type [bold]scaffold hint[/] to get structured hints for coding errors\n"
        "  • Type [bold]scaffold --help[/] to see all commands",
        border_style="green",
        padding=(1, 2),
    ))
