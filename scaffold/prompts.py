"""Prompt builders — every prompt sent to Gemma 4 lives here.

CORE RULE enforced in every prompt:
  "Do NOT provide corrected, complete, rewritten, or optimized code
   under any circumstance."

Each builder returns a plain string ready to send to ollama_client.query_gemma().
"""


def _add_line_numbers(code: str) -> str:
    """Prefix each line of code with its line number for model reference."""
    lines = code.splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{i+1:>{width}} | {line}" for i, line in enumerate(lines))


# The universal safety instruction appended to EVERY prompt
_NO_CODE_RULE = (
    "\n\nCRITICAL RULES:\n"
    "- Do NOT provide corrected, complete, rewritten, or optimized code under any circumstance.\n"
    "- Do NOT output code snippets, code blocks, or fixed versions of any line.\n"
    "- Only provide explanations, hints, questions, or named suggestions with reasoning.\n"
    "- Keep your response concise, beginner-friendly, and to the point.\n"
)


# 1. Auto-nudge — 1 sentence max, triggered by watcher

def build_nudge_prompt(code: str, error: dict) -> str:
    """Build a prompt for an automatic one-sentence nudge.

    This is the tightest prompt — model must respond in ONE short sentence only.
    """
    filename = error.get("file", "file")
    line = error.get("line", "unknown")
    message = error.get("message", "")

    return (
        f"You are a helpful coding tutor for beginners. "
        f"A student has a syntax error in their code.\n\n"
        f"File: {filename}\n"
        f"Error on line {line}: {message}\n\n"
        f"Respond with EXACTLY ONE short sentence (under 15 words) giving a gentle hint "
        f"about what the student should look at. Do not name the fix, just point them "
        f"in the right direction."
        f"{_NO_CODE_RULE}"
    )


# 2. On-demand hint — LINE/ISSUE/WHY format

def build_hint_prompt(code: str, error: dict) -> str:
    """Build a prompt for the `scaffold hint` command.

    Requests the structured LINE/ISSUE/WHY format for reliable parsing.
    """
    numbered = _add_line_numbers(code) if code else "(no code available)"
    line = error.get("line", "unknown")
    message = error.get("message", "")
    error_type = error.get("error_type", "error")

    return (
        f"You are a patient coding tutor for beginners. "
        f"A student has a {error_type} in their code.\n\n"
        f"Error on line {line}: {message}\n\n"
        f"Here is their code with line numbers:\n"
        f"```\n{numbered}\n```\n\n"
        f"Respond in EXACTLY this format (no other text before or after):\n"
        f"LINE: <the line number where the issue is>\n"
        f"ISSUE: <one sentence describing what is wrong>\n"
        f"WHY: <one sentence explaining why this causes a problem>\n"
        f"{_NO_CODE_RULE}"
    )


# 3. Practice question — triggered on 3+ repeated mistakes

def build_practice_prompt(concept: str, past_errors: list[dict]) -> str:
    """Build a prompt to generate a practice question for a repeated concept.

    The model should generate a short, focused question testing understanding.
    """
    error_summaries = "\n".join(
        f"- Line {e.get('line', '?')}: {e.get('message', '')}" for e in past_errors[:3]
    )

    return (
        f"You are a coding tutor for beginners. A student keeps making mistakes "
        f"related to the concept: '{concept}'.\n\n"
        f"Recent examples of their mistakes:\n{error_summaries}\n\n"
        f"Generate ONE short practice question (2-3 sentences) that tests their "
        f"understanding of this concept. The question should:\n"
        f"- Be conceptual (not asking them to write code)\n"
        f"- Test whether they understand WHY the concept matters\n"
        f"- Be answerable in 1-2 sentences\n"
        f"{_NO_CODE_RULE}"
    )


# 4. General Q&A — scaffold answer

def build_answer_prompt(question: str) -> str:
    """Build a prompt to answer any programming question from a student."""
    return (
        f"You are a patient coding tutor for beginners. "
        f"A student has asked you the following question:\n\n"
        f"\"{question}\"\n\n"
        f"Answer clearly and concisely, aimed at someone just learning to code. Keep it to 2-3 short paragraphs max.\n"
        f"- If answering multiple distinct questions, format your numbered list EXACTLY like this:\n"
        f"1. **[Question text here]**\n"
        f"\n"
        f"   [Answer text here]\n"
        f"- Use simple, everyday analogies when helpful\n"
        f"- Focus on the concept and the 'why', not just the definition\n"
        f"- If the question is about a specific language feature, explain when and why it's used\n"
        f"{_NO_CODE_RULE}"
    )


# 5. Practice question evaluation — scaffold answer (when practice is active)

def build_eval_prompt(question: str, student_answer: str) -> str:
    """Build a prompt to evaluate a student's answer to a practice question."""
    return (
        f"You are a patient coding tutor for beginners. You asked this practice question:\n\n"
        f"Question: {question}\n\n"
        f"The student answered: \"{student_answer}\"\n\n"
        f"Evaluate their answer in 2-3 sentences:\n"
        f"- Say whether the reasoning is correct or not\n"
        f"- Explain WHY it's right or wrong conceptually\n"
        f"- If wrong, give a gentle nudge toward the right thinking (no code)\n"
        f"{_NO_CODE_RULE}"
    )
