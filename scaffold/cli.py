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
        ctx.invoke(watch)


# scaffold setup
@main.command()
def setup():
    """Install Ollama, pull the Gemma model, and setup the offline tutor."""
    from scaffold.setup import run_setup
    run_setup()


# scaffold watch
@main.command()
@click.option("--daemon", is_flag=True, hidden=True, help="Run in background mode (used by auto-start hook).")
@click.option("--dir", "watch_dir", type=click.Path(exists=True, file_okay=False), default=".",
              help="Directory to watch (default: current directory).")
def watch(daemon, watch_dir):
    """Start the background file watcher to detect coding errors."""
    from scaffold.watcher import start_watcher

    start_watcher(watch_dir, daemon=daemon)


# scaffold hint
@main.command()
def hint():
    """Get an AI-generated hint from your offline tutor for your most recent error.

    If you've made the same kind of mistake 3+ times, you'll get
    a practice question instead.
    """
    from scaffold.mistake_log import get_recent_error, should_generate_practice, get_concept_errors
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_hint_prompt, build_practice_prompt
    from scaffold.display import display_hint_response, display_practice, display_error, console
    from scaffold.state import save_last_practice, load_last_practice, clear_last_practice

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    # 1. Check if there is already an active practice question in the state
    practice = load_last_practice()
    if practice is not None:
        display_practice(practice["question"])
        try:
            user_answer = console.input("\n[bold cyan]Your answer (or press Ctrl+C to exit):[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            return
            
        if user_answer:
            from scaffold.prompts import build_eval_prompt
            from scaffold.display import display_streamed_explanation
            eval_prompt = build_eval_prompt(practice["question"], user_answer)
            result = query_gemma(eval_prompt, stream=True)
            if result:
                display_streamed_explanation("answer evaluation", result)
                clear_last_practice()
        return

    # 2. Otherwise, check recent errors to see if we should generate a new practice question or standard hint
    error = get_recent_error()
    if error is None:
        display_error("No recent errors found. Write some code and I'll watch for mistakes!")
        return

    concept = error.get("concept", "")
    if concept and should_generate_practice(concept):
        past_errors = get_concept_errors(concept)
        prompt = build_practice_prompt(concept, past_errors)
        response = query_gemma(prompt, stream=True)
        if response:
            full_text = ""
            from rich.live import Live
            from rich.panel import Panel
            from rich.markdown import Markdown
            
            with Live(Panel("", title="[bold]🎯 Practice Question[/]", border_style="yellow", padding=(1, 2)), console=console, refresh_per_second=50) as live:
                for chunk in response:
                    full_text += chunk
                    live.update(Panel(
                        Markdown(full_text.strip()),
                        title="[bold]🎯 Practice Question[/]",
                        subtitle="[dim]Type your answer below or press Ctrl+C to exit[/]",
                        border_style="yellow",
                        padding=(1, 2),
                    ))
            
            save_last_practice(concept, full_text.strip())

            # Prompt the user directly in the terminal to answer it immediately
            try:
                user_answer = console.input("\n[bold cyan]Your answer (or press Ctrl+C to exit):[/] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print()
                return

            if user_answer:
                from scaffold.prompts import build_eval_prompt
                from scaffold.display import display_streamed_explanation
                eval_prompt = build_eval_prompt(full_text.strip(), user_answer)
                result = query_gemma(eval_prompt, stream=True)
                if result:
                    display_streamed_explanation("answer evaluation", result)
                    clear_last_practice()
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


# scaffold review <file>
@main.command()
@click.argument("file_parts", nargs=-1, required=True, metavar="FILE")
def review(file_parts):
    """On-demand code quality review."""
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_review_prompt
    from scaffold.display import display_hint_response, display_error

    file = resolve_file(file_parts)

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    code = Path(file).read_text(encoding="utf-8", errors="replace")

    prompt = build_review_prompt(code)
    response = query_gemma(prompt)
    if response:
        display_hint_response(file, response)


# scaffold explain <file> [--input "<value>"]
@main.command()
@click.argument("file_parts", nargs=-1, required=True, metavar="FILE")
@click.option("--input", "input_val", default=None, help="Trace execution step-by-step for this input value.")
def explain(file_parts, input_val):
    """Explain how your code works. Never rewrites code."""
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_explain_prompt, build_trace_prompt
    from scaffold.display import display_streamed_explanation, display_error

    file = resolve_file(file_parts)

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    code = Path(file).read_text(encoding="utf-8", errors="replace")

    if input_val:
        prompt = build_trace_prompt(code, input_val)
    else:
        prompt = build_explain_prompt(code)

    response = query_gemma(prompt, stream=True)
    if response:
        display_streamed_explanation(file, response)


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
