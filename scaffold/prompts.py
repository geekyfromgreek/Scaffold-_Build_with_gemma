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


# 3. Logical error detection — scaffold check

def build_check_prompt(code: str, expected: str, actual: str) -> str:
    """Build a prompt for `scaffold check --expected`.

    Compares expected vs actual output and asks the model where the logic diverges.
    """
    numbered = _add_line_numbers(code)

    return (
        f"You are a patient coding tutor for beginners. "
        f"A student's code runs without crashing, but produces the wrong output.\n\n"
        f"Expected output:\n{expected}\n\n"
        f"Actual output:\n{actual}\n\n"
        f"Here is their code with line numbers:\n"
        f"```\n{numbered}\n```\n\n"
        f"Identify where the logic likely diverges from the student's intent. "
        f"Respond in EXACTLY this format:\n"
        f"LINE: <the line number where the logic issue is>\n"
        f"ISSUE: <one sentence describing the logical mistake>\n"
        f"WHY: <one sentence explaining why this produces the wrong output>\n"
        f"{_NO_CODE_RULE}"
    )


# 4. Practice question — triggered on 3+ repeated mistakes

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


# 5. General Q&A — scaffold answer

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


# 6. Code review — scaffold review (1-2 suggestions max)

def build_review_prompt(code: str) -> str:
    """Build a prompt for on-demand code quality review.

    Provides concise suggestions. Never outputs rewritten code.
    """
    numbered = _add_line_numbers(code)

    return (
        f"You are a coding tutor reviewing a beginner's code for quality. "
        f"Provide 1 to 3 concise suggestions for improving the code.\n\n"
        f"Here is their code with line numbers:\n"
        f"```\n{numbered}\n```\n\n"
        f"For each suggestion, respond in this format:\n"
        f"LINE: <line number>\n"
        f"ISSUE: <one sentence describing the quality issue>\n"
        f"HINT: <one sentence explaining how to improve it>\n\n"
        f"If the code is clean and well-written, say so briefly."
        f"{_NO_CODE_RULE}"
    )


# 7. Efficiency analysis — scaffold review --efficiency

def build_efficiency_prompt(code: str) -> str:
    """Build a prompt for Big-O complexity analysis.

    Uses LINE/CURRENT/BETTER format. Explicitly allows 'current approach is reasonable'.
    """
    numbered = _add_line_numbers(code)

    return (
        f"You are a coding tutor analyzing a beginner's code for efficiency. "
        f"Analyze the time and space complexity.\n\n"
        f"Here is their code with line numbers:\n"
        f"```\n{numbered}\n```\n\n"
        f"If there is a meaningful efficiency improvement, respond in this format:\n"
        f"LINE: <line number of the relevant section>\n"
        f"CURRENT: <current approach and its Big-O complexity>\n"
        f"BETTER: <name of a better approach type and its Big-O, with one sentence on why>\n\n"
        f"If the current approach is already reasonably efficient for a beginner's code, "
        f"explicitly say 'current approach is reasonable' and briefly explain the current "
        f"complexity. Do NOT force a suggestion when none is warranted."
        f"{_NO_CODE_RULE}"
    )


# 8. Code explanation — scaffold explain

def build_explain_prompt(code: str) -> str:
    """Build a prompt for overall code workflow explanation."""
    numbered = _add_line_numbers(code)

    return (
        f"You are a patient coding tutor explaining code to a beginner. "
        f"Provide a concise explanation of what this code does (3-5 sentences).\n\n"
        f"Here is the code with line numbers:\n"
        f"```\n{numbered}\n```\n\n"
        f"Explain the overall flow and purpose. Use plain language. "
        f"Mention what the key variables do and how the logic flows from start to finish."
        f"{_NO_CODE_RULE}"
    )


# 9. Input trace — scaffold explain --input

def build_trace_prompt(code: str, input_value: str) -> str:
    """Build a prompt for step-by-step execution tracing with a given input."""
    numbered = _add_line_numbers(code)

    return (
        f"You are a patient coding tutor. Trace through this code step by step "
        f"as if the input is: {input_value}\n\n"
        f"Here is the code with line numbers:\n"
        f"```\n{numbered}\n```\n\n"
        f"Walk through the execution line by line. For each important step, show:\n"
        f"- Which line is executing\n"
        f"- What variables change and to what values\n"
        f"- What decisions (if/else, loops) are made and why\n\n"
        f"Keep it beginner-friendly and concise (under 10 steps if possible)."
        f"{_NO_CODE_RULE}"
    )


# 10. Image explanation — scaffold explain-image

def build_image_prompt() -> str:
    """Build a prompt for explaining an image (code screenshot, diagram, etc).

    The image bytes are passed separately via the Ollama images field.
    """
    return (
        f"You are a patient coding tutor. A beginner student is showing you an image. "
        f"It might be a screenshot of code, a flowchart, a diagram, or a concept illustration.\n\n"
        f"Explain the logic or concept shown in this image in 3-5 simple sentences. "
        f"Focus on WHAT it represents and HOW it works conceptually.\n\n"
        f"If it's a code screenshot, describe what the code is trying to do, "
        f"but do NOT rewrite, correct, or reproduce the code."
        f"{_NO_CODE_RULE}"
    )


# 11. Voice Q&A — scaffold ask-voice

def build_voice_prompt(transcription: str) -> str:
    """Build a prompt for answering a voice-transcribed question.

    The audio has already been transcribed to text by Whisper.
    """
    return (
        f"You are a patient coding tutor for beginners. A student asked you a question "
        f"verbally (transcribed below). Give a helpful hint or explanation — "
        f"never a full answer, solution, or working code.\n\n"
        f"Student's question: \"{transcription}\"\n\n"
        f"Respond in 2-4 sentences. Focus on explaining the concept, "
        f"pointing them in the right direction, or asking a clarifying question."
        f"{_NO_CODE_RULE}"
    )
