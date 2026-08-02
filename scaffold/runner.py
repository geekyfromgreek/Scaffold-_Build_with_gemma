"""Runner — executes Python and C files, captures stdout/stderr.

Strictly read-only: compiles C files to a temp location, never modifies the source.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path


def run_file_interactive(filepath: str) -> dict:
    """Run a Python or C file interactively — stdin/stdout go directly to the terminal.

    This is the default for `scaffold run`. Programs can use input(), print(),
    and interact with the user normally.

    Returns:
        Dict with keys: file, returncode, runtime_error (bool)
    """
    filepath = os.path.abspath(filepath)
    ext = Path(filepath).suffix.lower()

    if ext == ".py":
        cmd = [sys.executable, filepath]
    elif ext == ".c":
        return _run_c_interactive(filepath)
    else:
        return {
            "file": filepath,
            "returncode": 1,
            "runtime_error": True,
            "stderr": f"Unsupported file type: {ext}. Scaffold supports .py and .c files.",
        }

    try:
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(filepath),
        )
        return {
            "file": filepath,
            "returncode": result.returncode,
            "runtime_error": result.returncode != 0,
        }
    except Exception as e:
        return {
            "file": filepath,
            "returncode": -1,
            "runtime_error": True,
            "stderr": str(e),
        }


def _run_c_interactive(filepath: str) -> dict:
    """Compile and run a C file interactively."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_name = "scaffold_temp_prog.exe" if sys.platform == "win32" else "scaffold_temp_prog"
            exe_path = os.path.join(tmpdir, exe_name)

            compile_result = subprocess.run(
                ["gcc", filepath, "-o", exe_path],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if compile_result.returncode != 0:
                return {
                    "file": filepath,
                    "returncode": compile_result.returncode,
                    "runtime_error": True,
                    "stderr": compile_result.stderr,
                }

            result = subprocess.run(
                [exe_path],
                cwd=os.path.dirname(filepath),
            )
            return {
                "file": filepath,
                "returncode": result.returncode,
                "runtime_error": result.returncode != 0,
            }

    except FileNotFoundError:
        return {
            "file": filepath,
            "returncode": -1,
            "runtime_error": True,
            "stderr": "GCC not found. Install GCC (MinGW on Windows) to compile C files.",
        }
    except Exception as e:
        return {
            "file": filepath,
            "returncode": -1,
            "runtime_error": True,
            "stderr": str(e),
        }


def run_file(filepath: str, stdin_input: str | None = None) -> dict:
    """Run a Python or C file and capture its output.

    Args:
        filepath: Path to the .py or .c file.
        stdin_input: Optional string to pipe into the program's stdin.

    Returns:
        Dict with keys: file, stdout, stderr, returncode, runtime_error (bool)
    """
    filepath = os.path.abspath(filepath)
    ext = Path(filepath).suffix.lower()

    if ext == ".py":
        return _run_python(filepath, stdin_input)
    elif ext == ".c":
        return _run_c(filepath, stdin_input)
    else:
        return {
            "file": filepath,
            "stdout": "",
            "stderr": f"Unsupported file type: {ext}. Scaffold supports .py and .c files.",
            "returncode": 1,
            "runtime_error": True,
        }


def _run_python(filepath: str, stdin_input: str | None = None) -> dict:
    """Run a Python file via the current interpreter."""
    try:
        result = subprocess.run(
            [sys.executable, filepath],
            capture_output=True,
            text=True,
            input=stdin_input,
            timeout=30,
            cwd=os.path.dirname(filepath),
        )
        return {
            "file": filepath,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "runtime_error": result.returncode != 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "file": filepath,
            "stdout": "",
            "stderr": "Program timed out after 30 seconds. Check for infinite loops.",
            "returncode": -1,
            "runtime_error": True,
        }
    except Exception as e:
        return {
            "file": filepath,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "runtime_error": True,
        }


def _run_c(filepath: str, stdin_input: str | None = None) -> dict:
    """Compile and run a C file. Uses a temp directory for the executable."""
    # First, compile
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_name = "scaffold_temp_prog.exe" if sys.platform == "win32" else "scaffold_temp_prog"
            exe_path = os.path.join(tmpdir, exe_name)

            compile_result = subprocess.run(
                ["gcc", filepath, "-o", exe_path],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if compile_result.returncode != 0:
                return {
                    "file": filepath,
                    "stdout": "",
                    "stderr": compile_result.stderr,
                    "returncode": compile_result.returncode,
                    "runtime_error": True,
                }

            # Run the compiled executable
            run_result = subprocess.run(
                [exe_path],
                capture_output=True,
                text=True,
                input=stdin_input,
                timeout=30,
                cwd=os.path.dirname(filepath),
            )
            return {
                "file": filepath,
                "stdout": run_result.stdout,
                "stderr": run_result.stderr,
                "returncode": run_result.returncode,
                "runtime_error": run_result.returncode != 0,
            }

    except FileNotFoundError:
        return {
            "file": filepath,
            "stdout": "",
            "stderr": "GCC not found. Install GCC (MinGW on Windows) to compile C files.",
            "returncode": -1,
            "runtime_error": True,
        }
    except subprocess.TimeoutExpired:
        return {
            "file": filepath,
            "stdout": "",
            "stderr": "Program timed out after 30 seconds. Check for infinite loops.",
            "returncode": -1,
            "runtime_error": True,
        }
    except Exception as e:
        return {
            "file": filepath,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "runtime_error": True,
        }
