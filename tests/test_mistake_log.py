"""Tests for the mistake log module."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from scaffold import mistake_log


@pytest.fixture(autouse=True)
def use_temp_log(tmp_path):
    """Redirect the mistake log to a temp directory for each test."""
    temp_log_dir = tmp_path / ".scaffold"
    temp_log_file = temp_log_dir / "mistakes.json"
    with patch.object(mistake_log, "LOG_DIR", temp_log_dir), \
         patch.object(mistake_log, "LOG_FILE", temp_log_file):
        yield temp_log_file


class TestLogError:
    def test_basic_logging(self, use_temp_log):
        entry = mistake_log.log_error(
            error_type="syntax",
            file="test.py",
            line=5,
            message="invalid syntax",
        )
        assert entry["error_type"] == "syntax"
        assert entry["line"] == 5
        assert use_temp_log.exists()

        data = json.loads(use_temp_log.read_text())
        assert len(data) == 1

    def test_deduplication(self, use_temp_log):
        for _ in range(3):
            mistake_log.log_error("syntax", "test.py", 5, "invalid syntax")

        data = json.loads(use_temp_log.read_text())
        assert len(data) == 1  # Deduped back-to-back

    def test_different_errors_not_deduped(self, use_temp_log):
        mistake_log.log_error("syntax", "test.py", 5, "invalid syntax")
        mistake_log.log_error("syntax", "test.py", 10, "unexpected indent")

        data = json.loads(use_temp_log.read_text())
        assert len(data) == 2


class TestConceptInference:
    def test_indentation_concept(self):
        assert mistake_log._infer_concept("syntax", "unexpected indent") == "indentation"

    def test_undefined_variable(self):
        assert mistake_log._infer_concept("runtime", "name 'x' is not defined") == "undefined_variable"

    def test_missing_semicolon(self):
        assert mistake_log._infer_concept("syntax", "expected ';' before") == "missing_semicolon"

    def test_fallback(self):
        assert mistake_log._infer_concept("runtime", "something obscure") == "runtime"


class TestRepeatDetection:
    def test_should_generate_practice(self, use_temp_log):
        # Log 3 different errors with the same concept
        for i in range(3):
            mistake_log.log_error("syntax", "test.py", i + 1, f"indent error {i}", "indentation")

        assert mistake_log.should_generate_practice("indentation") is True

    def test_below_threshold(self, use_temp_log):
        mistake_log.log_error("syntax", "test.py", 1, "indent error", "indentation")
        mistake_log.log_error("syntax", "test.py", 2, "indent error 2", "indentation")

        assert mistake_log.should_generate_practice("indentation") is False


class TestGetRecentError:
    def test_empty_log(self, use_temp_log):
        assert mistake_log.get_recent_error() is None

    def test_returns_last(self, use_temp_log):
        mistake_log.log_error("syntax", "a.py", 1, "first")
        mistake_log.log_error("syntax", "b.py", 2, "second")

        recent = mistake_log.get_recent_error()
        assert recent["file"] == "b.py"
        assert recent["message"] == "second"
