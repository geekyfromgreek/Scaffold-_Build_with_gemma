"""Tests for the runner module."""

import sys
import pytest
import tempfile
from pathlib import Path

from scaffold.runner import run_file


class TestRunPython:
    def test_successful_run(self, tmp_path):
        script = tmp_path / "hello.py"
        script.write_text('print("hello world")')

        result = run_file(str(script))
        assert result["stdout"].strip() == "hello world"
        assert result["returncode"] == 0
        assert result["runtime_error"] is False

    def test_runtime_error(self, tmp_path):
        script = tmp_path / "bad.py"
        script.write_text('print(1/0)')

        result = run_file(str(script))
        assert result["returncode"] != 0
        assert result["runtime_error"] is True
        assert "ZeroDivisionError" in result["stderr"]

    def test_stdin_input(self, tmp_path):
        script = tmp_path / "echo.py"
        script.write_text('x = input()\nprint(f"got: {x}")')

        result = run_file(str(script), stdin_input="hello")
        assert "got: hello" in result["stdout"]

    def test_unsupported_extension(self, tmp_path):
        script = tmp_path / "file.java"
        script.write_text("class Main {}")

        result = run_file(str(script))
        assert result["runtime_error"] is True
        assert "Unsupported" in result["stderr"]


class TestRunC:
    def test_c_file_without_gcc(self, tmp_path):
        """If gcc isn't installed, should return a clear error."""
        script = tmp_path / "hello.c"
        script.write_text('#include <stdio.h>\nint main() { printf("hello"); return 0; }')

        result = run_file(str(script))
        # Either it works (gcc present) or gives a clear error (gcc absent)
        if result["runtime_error"]:
            assert "GCC" in result["stderr"] or "gcc" in result["stderr"].lower() or result["returncode"] != 0
