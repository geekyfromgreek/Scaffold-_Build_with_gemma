"""Voice input — transcribes audio files or microphone recordings to text via Whisper.

The transcribed text is then sent to Gemma 4 through the normal prompt flow.
This module handles ONLY the audio → text step.

Whisper runs fully locally (no cloud calls). The 'base' model (~140 MB)
is auto-downloaded on first use.
"""

import tempfile
from pathlib import Path


def record_and_transcribe(duration: int = 10) -> str | None:
    """Record audio from the microphone and transcribe it.

    Args:
        duration: Recording duration in seconds.

    Returns:
        Transcribed text string, or None on failure.
    """
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wav
    except ImportError:
        _print_error(
            "sounddevice or scipy is not installed. Run: pip install sounddevice scipy"
        )
        return None

    try:
        from rich.console import Console
        console = Console()

        console.print(
            f"[bold cyan]🎙 Recording for {duration} seconds... speak now![/]",
            highlight=False,
        )

        sample_rate = 16000  # Whisper expects 16kHz
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()  # Block until recording is done

        # Check if the audio is completely silent
        import numpy as np
        if np.max(np.abs(audio_data)) < 100:
            console.print(
                "[bold yellow]⚠ No audio detected (pure silence).[/]\n"
                "  Make sure your microphone is unmuted and set as the 'Default Recording Device' in Windows Sound Settings.",
                highlight=False
            )
            return None

        console.print("[dim]✓ Recording finished. Transcribing...[/]", highlight=False)

        # Save to temp .wav file for Whisper
        # We don't use 'with' here because on Windows, keeping the NamedTemporaryFile open
        # prevents other functions from reading/writing to it by path.
        tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()
        
        wav.write(tmp_path, sample_rate, audio_data)

        return _transcribe_file(tmp_path)

    except Exception as e:
        _print_error(f"Recording failed: {e}")
        return None


def transcribe_audio(filepath: str) -> str | None:
    """Transcribe an audio file to text using OpenAI Whisper (local).

    Args:
        filepath: Path to an audio file (.wav, .mp3, etc.).

    Returns:
        Transcribed text string, or None on failure.
    """
    path = Path(filepath.strip().strip('"').strip("'"))

    if not path.exists():
        _print_error(f"Audio file not found: {path}")
        return None

    return _transcribe_file(str(path))


def _transcribe_file(filepath: str) -> str | None:
    """Internal: run Whisper on a file path."""
    try:
        import whisper
    except ImportError:
        _print_error(
            "Whisper is not installed. Run: pip install openai-whisper\n"
            "  (This is installed automatically by 'scaffold setup')"
        )
        return None

    try:
        from rich.console import Console
        console = Console()
        console.print("[dim]🎙 Transcribing audio...[/]", highlight=False)

        model = whisper.load_model("base")
        result = model.transcribe(filepath)
        text = result.get("text", "").strip()

        if not text:
            _print_error("Transcription returned empty text. The audio may be too short or unclear.")
            return None

        console.print(f'[dim]📝 Heard: "{text}"[/]', highlight=False)
        return text

    except Exception as e:
        error_msg = str(e)
        if "urlopen error" in error_msg or "WinError 10054" in error_msg:
            _print_error(
                "Failed to download the Whisper AI model (network error).\n"
                "  This only happens on the first run because it needs to download ~140MB of model weights.\n"
                "  Please check your internet connection, disable VPNs if needed, and try again."
            )
        elif "WinError 2" in error_msg:
            _print_error(
                "Transcription failed because FFmpeg is not installed on your system.\n"
                "  Whisper requires FFmpeg to process audio files.\n"
                "  To install it on Windows, open a new terminal and run:\n\n"
                "  winget install ffmpeg\n\n"
                "  After installing, restart your terminal and try again."
            )
        else:
            _print_error(f"Transcription failed: {error_msg}")
        return None


def _print_error(message: str):
    """Print an error message using rich if available, plain print otherwise."""
    try:
        from rich.console import Console
        Console().print(f"[bold red]✗ {message}[/]", highlight=False)
    except ImportError:
        print(f"ERROR: {message}")

