"""Image input — handles drag-and-drop file paths and clipboard screenshots.

Provides image bytes to pass to the Ollama multimodal API.
Never writes to or modifies any student file.
"""

import io
from pathlib import Path

# Supported image extensions
SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


def get_image_bytes_from_file(filepath: str) -> bytes | None:
    """Read an image file and return its bytes.

    Args:
        filepath: Path to the image file (typically auto-filled by terminal
                  drag-and-drop).

    Returns:
        Image file bytes, or None if the file can't be read.
    """
    path = Path(filepath.strip().strip('"').strip("'"))

    if not path.exists():
        return None

    if path.suffix.lower() not in SUPPORTED_FORMATS:
        return None

    try:
        return path.read_bytes()
    except OSError:
        return None


def get_image_bytes_from_clipboard() -> bytes | None:
    """Grab the current clipboard image and return it as PNG bytes.

    Uses PIL.ImageGrab.grabclipboard() — works on Windows.
    Returns None if there's no image on the clipboard.
    """
    try:
        from PIL import ImageGrab

        img = ImageGrab.grabclipboard()
        if img is None:
            return None

        # Convert to PNG bytes
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        # Pillow not installed
        return None
    except Exception:
        return None
