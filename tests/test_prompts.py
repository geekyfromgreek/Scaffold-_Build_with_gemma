"""Tests for prompt builders — verify structure and safety rules."""

import pytest
from scaffold.prompts import (
    build_nudge_prompt,
    build_hint_prompt,
    build_check_prompt,
    build_practice_prompt,
    build_eval_prompt,
    build_review_prompt,
    build_efficiency_prompt,
    build_explain_prompt,
    build_trace_prompt,
    build_image_prompt,
    build_voice_prompt,
)

# Every prompt MUST contain the no-code rule
NO_CODE_PHRASES = [
    "Do NOT provide corrected",
    "Do NOT output code snippets",
]

SAMPLE_CODE = "x = 10\nprint(x + y)\n"
SAMPLE_ERROR = {
    "error_type": "syntax",
    "file": "test.py",
    "line": 2,
    "message": "name 'y' is not defined",
    "concept": "undefined_variable",
}


class TestNoCodeRule:
    """Every prompt builder must include the no-code safety instruction."""

    @pytest.mark.parametrize("builder,args", [
        (build_nudge_prompt, (SAMPLE_CODE, SAMPLE_ERROR)),
        (build_hint_prompt, (SAMPLE_CODE, SAMPLE_ERROR)),
        (build_check_prompt, (SAMPLE_CODE, "20", "10")),
        (build_practice_prompt, ("undefined_variable", [SAMPLE_ERROR])),
        (build_eval_prompt, ("What is a variable?", "It stores data")),
        (build_review_prompt, (SAMPLE_CODE,)),
        (build_efficiency_prompt, (SAMPLE_CODE,)),
        (build_explain_prompt, (SAMPLE_CODE,)),
        (build_trace_prompt, (SAMPLE_CODE, "5")),
        (build_image_prompt, ()),
        (build_voice_prompt, ("How do I fix a syntax error?",)),
    ])
    def test_no_code_rule_present(self, builder, args):
        prompt = builder(*args)
        for phrase in NO_CODE_PHRASES:
            assert phrase in prompt, f"{builder.__name__} missing: {phrase}"


class TestPromptFormats:
    """Verify prompts request the correct output format."""

    def test_nudge_requests_one_sentence(self):
        prompt = build_nudge_prompt(SAMPLE_CODE, SAMPLE_ERROR)
        assert "ONE" in prompt or "one" in prompt.lower()

    def test_hint_requests_line_issue_why(self):
        prompt = build_hint_prompt(SAMPLE_CODE, SAMPLE_ERROR)
        assert "LINE:" in prompt
        assert "ISSUE:" in prompt
        assert "WHY:" in prompt

    def test_check_requests_line_issue_why(self):
        prompt = build_check_prompt(SAMPLE_CODE, "20", "10")
        assert "LINE:" in prompt
        assert "ISSUE:" in prompt
        assert "WHY:" in prompt

    def test_efficiency_requests_current_better(self):
        prompt = build_efficiency_prompt(SAMPLE_CODE)
        assert "CURRENT:" in prompt
        assert "BETTER:" in prompt
        assert "reasonable" in prompt.lower()

    def test_explain_no_rewrite(self):
        prompt = build_explain_prompt(SAMPLE_CODE)
        assert "3-5" in prompt or "3 to 5" in prompt.lower()

    def test_trace_includes_input(self):
        prompt = build_trace_prompt(SAMPLE_CODE, "42")
        assert "42" in prompt

    def test_line_numbers_added(self):
        prompt = build_hint_prompt(SAMPLE_CODE, SAMPLE_ERROR)
        assert "1 |" in prompt or "1|" in prompt
        assert "2 |" in prompt or "2|" in prompt
