"""Tests for the display module — response parsing and output functions."""

import pytest
from scaffold.display import parse_model_response, parse_efficiency_response


class TestParseModelResponse:
    """Test LINE/ISSUE/WHY parsing."""

    def test_single_block(self):
        raw = "LINE: 7\nISSUE: Missing colon after if\nWHY: Python needs a colon"
        blocks = parse_model_response(raw)
        assert len(blocks) == 1
        assert blocks[0]["line"] == 7
        assert "colon" in blocks[0]["issue"].lower()
        assert "Python" in blocks[0]["why"]

    def test_multiple_blocks(self):
        raw = (
            "LINE: 3\nISSUE: Unused variable\nWHY: Wastes memory\n\n"
            "LINE: 10\nISSUE: Missing return\nWHY: Function returns None"
        )
        blocks = parse_model_response(raw)
        assert len(blocks) == 2
        assert blocks[0]["line"] == 3
        assert blocks[1]["line"] == 10

    def test_empty_input(self):
        assert parse_model_response("") == []

    def test_no_format_match(self):
        raw = "This is just free text with no LINE/ISSUE/WHY format."
        assert parse_model_response(raw) == []

    def test_case_insensitive(self):
        raw = "line: 5\nissue: Something\nwhy: Because"
        blocks = parse_model_response(raw)
        assert len(blocks) == 1
        assert blocks[0]["line"] == 5


class TestParseEfficiencyResponse:
    """Test LINE/CURRENT/BETTER parsing."""

    def test_normal_suggestion(self):
        raw = "LINE: 4\nCURRENT: Bubble sort O(n²)\nBETTER: Merge sort O(n log n)"
        blocks = parse_efficiency_response(raw)
        assert len(blocks) == 1
        assert blocks[0]["line"] == 4
        assert "Bubble" in blocks[0]["current"]
        assert "Merge" in blocks[0]["better"]
        assert not blocks[0]["reasonable"]

    def test_reasonable_response(self):
        raw = "The current approach is reasonable for this input size."
        blocks = parse_efficiency_response(raw)
        assert len(blocks) == 1
        assert blocks[0]["reasonable"] is True

    def test_already_efficient(self):
        raw = "This code is already efficient. No changes needed."
        blocks = parse_efficiency_response(raw)
        assert len(blocks) == 1
        assert blocks[0]["reasonable"] is True
