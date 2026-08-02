"""Scaffold CLI — command routing via Click.

Every subcommand delegates to the appropriate module for logic,
then uses display.py for terminal output. This file is purely
the command-line interface layer.
"""

import os
import click
from pathlib import Path


def resolve_file(file_parts: tuple[str, ...], must_exist: bool = True) -> str:
    """Join variadic filename parts and resolve to an existing file.

    Handles two user-experience issues:
    1. Filenames with spaces — the shell splits them into multiple args,
       so we accept *parts and join them back.
    2. Bare filenames — the user can type just 'hello.py' and we search
       the current directory (then one level of subdirectories) for it.

    Returns the resolved absolute path as a string, or calls click.fail().
    """
    if not file_parts:
        raise click.UsageError("Missing required argument 'FILE'.")

    filename = " ".join(file_parts)

    # 1. If the path exists as given (absolute or relative), use it directly.
    candidate = Path(filename)
    if candidate.exists() and candidate.is_file():
        return str(candidate.resolve())

    # 2. Search CWD and one level of subdirectories for a matching basename.
    cwd = Path.cwd()
    basename = Path(filename).name  # strip any bogus directory component
    for root, _dirs, files in os.walk(cwd):
        if basename in files:
            return str((Path(root) / basename).resolve())
        # Limit depth: only search CWD and its immediate children
        depth = len(Path(root).relative_to(cwd).parts)
        if depth >= 2:
            _dirs.clear()

    if must_exist:
        raise click.BadParameter(
            f"File '{filename}' not found in the current directory tree.",
            param_hint="'FILE'",
            param_type="argument",
        )
    return str(candidate.resolve())


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(package_name="scaffold")
def main(ctx):
    """Scaffold: The Offline AI Tutor (Gemma for Good).

    A privacy-first programming tutor that watches your code and helps you learn.
    Scaffold NEVER writes to your files and NEVER gives you the exact answer.
    It provides hints, explanations, and practice using a local Gemma model.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# scaffold setup
@main.command()
def setup():
    """Install Ollama, pull the Gemma model, and setup the offline tutor."""
    from scaffold.setup import run_setup
    run_setup()


# scaffold hint
@main.command()
def hint():
    """Get an AI-generated hint from your offline tutor for your most recent error.

    If you've made the same kind of mistake 3+ times, you'll get
    a practice question instead.
    """
    from scaffold.mistake_log import get_recent_error, should_generate_practice, get_concept_errors
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_hint_prompt
    from scaffold.display import display_hint_response, display_practice, display_error
    from scaffold.state import save_last_practice

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    error = get_recent_error()
    if error is None:
        display_error("No recent errors found. Write some code and I'll watch for mistakes!")
        return

    # Check if we should generate a practice question instead
    concept = error.get("concept", "")
    if concept and should_generate_practice(concept):
        from scaffold.prompts import build_practice_prompt
        past_errors = get_concept_errors(concept)
        prompt = build_practice_prompt(concept, past_errors)
        response = query_gemma(prompt, stream=True)
        if response:
            save_last_practice(concept, response)
            display_practice(response)
        return

    # Normal hint flow
    filepath = error.get("file", "")
    code = ""
    if filepath and Path(filepath).exists():
        code = Path(filepath).read_text(encoding="utf-8", errors="replace")

    prompt = build_hint_prompt(code, error)
    response = query_gemma(prompt)
    if response:
        display_hint_response(filepath, response)


# scaffold answer "<response>"
@main.command()
@click.argument("response_parts", nargs=-1, required=False, metavar="[RESPONSE]")
def answer(response_parts):
    """Answer a practice question, or ask any programming question."""
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.display import display_streamed_explanation, display_error
    from scaffold.state import load_last_practice
    from scaffold.display import console

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    response = " ".join(response_parts).strip()

    while True:
        if not response:
            try:
                response = console.input("\n[bold cyan]Ask a question (or press Ctrl+C to exit):[/] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print()
                break
            
            if not response:
                continue

        # If there's an active practice question, evaluate the answer against it
        practice = load_last_practice()
        if practice is not None:
            from scaffold.prompts import build_eval_prompt
            from scaffold.state import clear_last_practice
            
            prompt = build_eval_prompt(practice["question"], response)
            result = query_gemma(prompt, stream=True)
            if result:
                display_streamed_explanation("answer evaluation", result)
                # Clear the practice question so the user isn't stuck answering it forever
                clear_last_practice()
        else:
            # No active practice question — treat as a general Q&A
            from scaffold.prompts import build_answer_prompt
            prompt = build_answer_prompt(response)
            result = query_gemma(prompt, stream=True)
            if result:
                display_streamed_explanation("answer", result)
        
        # Clear response to prompt the user again in the next loop
        response = ""


if __name__ == "__main__":
    main()
