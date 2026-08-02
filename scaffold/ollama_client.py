"""Ollama client — thin wrapper around the Ollama Python library.

All AI calls go through query_gemma(). This is the ONLY module that
talks to the model. No cloud calls — everything stays on localhost:11434.
"""

import ollama
from typing import Generator
from rich.console import Console

MODEL = "gemma4:e2b"
VISION_MODEL = "llava"
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 60  # seconds — generous for modest hardware

console = Console()


def is_ollama_running() -> bool:
    """Check if Ollama is reachable on localhost."""
    try:
        ollama.list()
        return True
    except Exception:
        return False


def is_model_available() -> bool:
    """Check if the required model is pulled and ready."""
    try:
        models = ollama.list()
        model_names = []
        # Handle both dict-style and object-style responses
        if hasattr(models, "models"):
            model_list = models.models
        elif isinstance(models, dict):
            model_list = models.get("models", [])
        else:
            model_list = []

        for m in model_list:
            name = m.model if hasattr(m, "model") else m.get("model", "")
            model_names.append(name)

        # Check for exact match or prefix match (e.g., "gemma4:e2b" matches "gemma4:e2b")
        return any(MODEL in name for name in model_names)
    except Exception:
        return False


def query_gemma(
    prompt: str,
    images: list[bytes] | None = None,
    temperature: float = 0.3,
    stream: bool = False,
) -> str | Generator[str, None, None] | None:
    """Send a prompt to the local model and return the response.

    Args:
        prompt: The text prompt to send.
        images: Optional list of image byte arrays for multimodal input.
        temperature: Sampling temperature (lower = more focused).
        stream: If True, returns a generator of string chunks.

    Returns:
        The response text (if stream=False), a Generator of strings (if stream=True), or None on failure.
    """
    message = {
        "role": "user",
        "content": prompt,
    }

    if images:
        message["images"] = images

    target_model = VISION_MODEL if images else MODEL

    try:
        response = ollama.chat(
            model=target_model,
            messages=[message],
            options={"temperature": temperature},
            stream=stream,
        )

        if stream:
            def chunk_generator():
                for chunk in response:
                    if hasattr(chunk, "message"):
                        yield chunk.message.content
                    elif isinstance(chunk, dict):
                        yield chunk.get("message", {}).get("content", "")
            return chunk_generator()
        else:
            if hasattr(response, "message"):
                return response.message.content
            elif isinstance(response, dict):
                return response.get("message", {}).get("content", "")
            return None

    except ollama.ResponseError as e:
        if "not found" in str(e).lower():
            console.print(
                f"[bold red]✗ Model '{target_model}' not found.[/]\n"
                f"Please run: [bold cyan]ollama pull {target_model}[/]",
                highlight=False,
            )
        else:
            console.print(f"[bold red]✗ Ollama error:[/] {e}", highlight=False)
        return None

    except Exception as e:
        console.print(
            f"[bold red]✗ Could not reach Ollama.[/] "
            f"Make sure it's running (try 'ollama serve').\n  Error: {e}",
            highlight=False,
        )
        return None
