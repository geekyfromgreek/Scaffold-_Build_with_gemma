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
@click.option("--remove-hook", is_flag=True, help="Remove the auto-start hook from your shell profile.")
def setup(remove_hook):
    """Install Ollama, pull the Gemma model, and setup the offline tutor."""
    from scaffold.setup import run_setup, remove_profile_hook

    if remove_hook:
        remove_profile_hook()
    else:
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


# scaffold run <file>
@main.command()
@click.argument("file_parts", nargs=-1, required=True, metavar="FILE")
@click.option("--input", "stdin_input", default=None, help="Input to feed to the program via stdin.")
def run(file_parts, stdin_input):
    """Run your code and capture the output for the AI tutor."""
    file = resolve_file(file_parts)

    if stdin_input is not None:
        # Captured mode: pipe stdin and show output in a panel
        from scaffold.runner import run_file
        from scaffold.display import display_run_result

        stdin_input = stdin_input.replace("\\n", "\n")
        result = run_file(file, stdin_input=stdin_input)
        display_run_result(result)
    else:
        # Interactive mode: let the program use the terminal directly
        from scaffold.runner import run_file_interactive
        from scaffold.display import display_error

        result = run_file_interactive(file)
        if result.get("stderr"):
            display_error(result["stderr"])


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

    # 2. Otherwise, check recent errors
    error = get_recent_error()
    if error is None:
        display_error("No recent errors found. Write some code and I'll watch for mistakes!")
        return

    concept = error.get("concept", "")
    if concept and should_generate_practice(concept):
        past_errors = get_concept_errors(concept)
        prompt = build_practice_prompt(concept, past_errors)
        response_stream = query_gemma(prompt, stream=True)
        if response_stream:
            from rich.live import Live
            from rich.panel import Panel
            
            full_text = ""
            with Live(Panel(full_text, title="[bold]🎯 Practice Question[/]", border_style="yellow", padding=(1, 2)), console=console, refresh_per_second=10) as live:
                for chunk in response_stream:
                    full_text += chunk
                    live.update(Panel(full_text.strip(), title="[bold]🎯 Practice Question[/]", border_style="yellow", padding=(1, 2)))
            
            save_last_practice(concept, full_text.strip())
        return

    # 3. Normal hint flow
    filepath = error.get("file", "")
    code = ""
    if filepath and Path(filepath).exists():
        code = Path(filepath).read_text(encoding="utf-8", errors="replace")

    prompt = build_hint_prompt(code, error)
    response = query_gemma(prompt)
    if response:
        display_hint_response(filepath, response)


@main.command()
@click.argument("file_parts", nargs=-1, required=True, metavar="FILE")
@click.option("--expected", required=False, default=None, help="The output you expect the program to produce.")
@click.option("--input", "stdin_input", default=None, help="Input to feed to the program via stdin.")
def check(file_parts, expected, stdin_input):
    """Check if your code produces the expected output. Detects logic errors."""
    from scaffold.runner import run_file
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_check_prompt
    from scaffold.display import display_hint_response, display_error, display_check_pass, display_run_result

    file = resolve_file(file_parts)

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    if stdin_input is not None:
        stdin_input = stdin_input.replace("\\n", "\n")

    result = run_file(file, stdin_input=stdin_input)
    actual = result.get("stdout", "").strip()

    if expected is None:
        # If no expected output is given, just behave like a silent runner and display what happened
        display_run_result(result)
        return

    expected_stripped = expected.strip()

    if actual == expected_stripped:
        display_check_pass(file)
        return

    code = Path(file).read_text(encoding="utf-8", errors="replace")
    prompt = build_check_prompt(code, expected_stripped, actual)
    
    from scaffold.display import console
    console.print("[dim]Analyzing logic error...[/]", highlight=False)
    
    response = query_gemma(prompt)
    if response:
        display_hint_response(file, response)
    else:
        display_error("The AI model failed to generate a response. Please try again.")


# scaffold review <file> [--efficiency]
@main.command()
@click.argument("file_parts", nargs=-1, required=True, metavar="FILE")
@click.option("--efficiency", is_flag=True, help="Analyze time/space complexity in Big-O terms.")
def review(file_parts, efficiency):
    """On-demand code quality review."""
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_review_prompt, build_efficiency_prompt
    from scaffold.display import display_hint_response, display_efficiency_response, display_error

    file = resolve_file(file_parts)

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    code = Path(file).read_text(encoding="utf-8", errors="replace")

    if efficiency:
        prompt = build_efficiency_prompt(code)
        response = query_gemma(prompt)
        if response:
            display_efficiency_response(file, response)
    else:
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


# scaffold explain-image [image] | --snip
@main.command("explain-image")
@click.argument("image_parts", nargs=-1, required=False, metavar="IMAGE")
def explain_image(image_parts):
    """Explain the logic/concept in an image. Uses clipboard by default."""
    from scaffold.image_input import get_image_bytes_from_file, get_image_bytes_from_clipboard
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_image_prompt
    from scaffold.display import display_streamed_explanation, display_error

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    if image_parts:
        # File path provided
        image = resolve_file(image_parts)
        image_bytes = get_image_bytes_from_file(image)
        if image_bytes is None:
            display_error(f"Could not read image: {image}")
            return
        source_label = image
    else:
        # Default: grab from clipboard
        image_bytes = get_image_bytes_from_clipboard()
        if image_bytes is None:
            display_error(
                "No image found on the clipboard.\n"
                "  Copy an image or take a screenshot (Win+Shift+S), then run this command again.\n"
                "  Or provide a file: scaffold explain-image diagram.png"
            )
            return
        source_label = "clipboard screenshot"

    prompt = build_image_prompt()
    response = query_gemma(prompt, images=[image_bytes], stream=True)
    if response:
        display_streamed_explanation(source_label, response)


# scaffold ask-voice [audio] | --mic
@main.command("ask-voice")
@click.argument("audio_parts", nargs=-1, required=False, metavar="AUDIO")
@click.option("--mic", is_flag=True, help="Record from microphone instead of a file.")
@click.option("--seconds", default=10, type=int, help="Recording duration in seconds (default: 10).")
def ask_voice(audio_parts, mic, seconds):
    """Ask a question by voice - from microphone or audio file."""
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.prompts import build_voice_prompt
    from scaffold.display import display_streamed_explanation, display_error

    if not is_ollama_running():
        display_error("Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'.")
        return

    if audio_parts:
        # File mode
        from scaffold.voice_input import transcribe_audio
        audio = resolve_file(audio_parts)
        transcription = transcribe_audio(audio)
    else:
        # Microphone mode (default)
        from scaffold.voice_input import record_and_transcribe
        transcription = record_and_transcribe(duration=seconds)

    if transcription is None:
        display_error("Could not capture or transcribe audio.")
        return

    prompt = build_voice_prompt(transcription)
    response = query_gemma(prompt, stream=True)
    if response:
        display_streamed_explanation("voice", response)


# scaffold answer "<response>"
@main.command()
@click.argument("response_parts", nargs=-1, required=False, metavar="[RESPONSE]")
def answer(response_parts):
    """Ask any programming question."""
    from scaffold.ollama_client import query_gemma, is_ollama_running
    from scaffold.display import display_streamed_explanation, display_error
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

        from scaffold.prompts import build_answer_prompt
        prompt = build_answer_prompt(response)
        result = query_gemma(prompt, stream=True)
        if result:
            display_streamed_explanation("answer", result)
        
        # Clear response to prompt the user again in the next loop
        response = ""


if __name__ == "__main__":
    main()