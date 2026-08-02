"""Scaffold Web Dashboard — Flask localhost server.

Serves a browser-based dashboard at http://localhost:5000 that
directly imports scaffold functions (no subprocess shelling).
All CLI commands are wired up to work from the browser.
"""

import json
import os
import glob
import base64
import threading
from pathlib import Path

from flask import Flask, render_template_string, jsonify, request

from scaffold.ollama_client import query_gemma, is_ollama_running
from scaffold.mistake_log import get_recent_error, _load_log, should_generate_practice, get_concept_errors
from scaffold.prompts import (
    build_hint_prompt, build_check_prompt, build_practice_prompt,
    build_review_prompt, build_explain_prompt, build_trace_prompt,
    build_answer_prompt, build_eval_prompt, build_image_prompt,
    build_voice_prompt
)
from scaffold.display import parse_model_response

app = Flask(__name__)

MISTAKES_FILE = Path.home() / ".scaffold" / "mistakes.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Scaffold Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Geist:wght@400;600&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --bg: #050505; --surface: #0A0A0A; --elevated: #131313;
    --border: #262626; --text: #EDEDED; --dim: #888;
    --accent: #F59E0B; --cyan: #8fd5ff; --red: #ffb4ab;
    --green: #22c55e;
  }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'JetBrains Mono', monospace; font-size: 13px;
    line-height: 20px; height: 100vh; display: flex; flex-direction: column;
    overflow: hidden;
  }
  header {
    background: #0e0e0e; border-bottom: 1px solid #534434;
    height: 36px; display: flex; align-items: center;
    justify-content: space-between; padding: 0 16px; flex-shrink: 0;
  }
  header .title {
    font-family: 'Geist', sans-serif; font-weight: 700; font-size: 12px;
    letter-spacing: 0.02em; color: var(--accent);
  }
  header .status { display: flex; align-items: center; gap: 6px; font-size: 11px; }
  .status-dot { width: 6px; height: 6px; border-radius: 50%; }
  .status-dot.active { background: var(--accent); }
  .status-dot.idle { background: var(--border); }
  .utility-bar {
    height: 32px; border-bottom: 1px solid var(--border);
    background: var(--surface); display: flex; align-items: center;
    justify-content: space-between; padding: 0 12px; flex-shrink: 0;
    font-size: 11px; color: var(--text);
  }
  .main-layout { display: flex; flex: 1; overflow: hidden; }
  .sidebar {
    width: 260px; border-right: 1px solid var(--border);
    background: var(--surface); display: flex; flex-direction: column;
    flex-shrink: 0; overflow: hidden;
  }
  .sidebar-header {
    padding: 12px; border-bottom: 1px solid var(--border);
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em;
    font-weight: 700; color: var(--dim);
  }
  .sidebar-list { flex: 1; overflow-y: auto; padding: 8px; }
  .mistake-card {
    border: 1px solid var(--border); background: #1a1a1a;
    padding: 10px; margin-bottom: 8px; cursor: pointer;
    transition: border-color 0.15s;
  }
  .mistake-card:hover { border-color: #404040; }
  .mistake-card .concept { font-weight: 700; font-size: 11px; margin-bottom: 4px; }
  .mistake-card .msg { font-size: 11px; color: var(--dim); line-height: 16px; }
  .output-area { flex: 1; position: relative; overflow: hidden; }
  #output-scroll {
    position: absolute; top: 0; bottom: 82px; left: 0; right: 0;
    overflow-y: auto; padding: 16px;
  }
  .output-block {
    border: 1px solid var(--border); background: var(--elevated);
    padding: 16px; margin-bottom: 12px;
  }
  .output-block .label {
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--dim); margin-bottom: 8px; font-weight: 700;
  }
  .output-block .line-num { color: var(--cyan); font-weight: 700; }
  .output-block .issue { color: var(--accent); }
  .output-block .why { color: var(--text); }
  .output-block .hint { color: var(--green); }
  .output-block .raw { white-space: pre-wrap; color: var(--text); }
  .welcome-msg { color: var(--dim); font-style: italic; padding: 24px; }
  .input-section {
    position: absolute; bottom: 0; left: 0; right: 0; height: 82px;
    border-top: 1px solid var(--border); background: var(--surface);
    padding: 10px 16px;
  }
  .input-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
  .input-row:last-child { margin-bottom: 0; }
  .input-row input, .input-row select {
    background: var(--bg); border: 1px solid var(--border);
    color: var(--text); font-family: 'JetBrains Mono', monospace;
    font-size: 12px; padding: 7px 10px; outline: none;
    transition: border-color 0.15s;
  }
  .input-row input:focus, .input-row select:focus { border-color: var(--accent); }
  .input-row input::placeholder { color: #555; }
  .input-row select { cursor: pointer; }
  .input-row select option { background: var(--bg); color: var(--text); }
  .cmd-btn {
    background: var(--bg); border: 1px solid var(--border);
    color: var(--text); font-family: 'JetBrains Mono', monospace;
    font-size: 11px; padding: 7px 12px; cursor: pointer;
    transition: all 0.15s; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; white-space: nowrap;
  }
  .cmd-btn:hover { border-color: var(--accent); color: var(--accent); }
  .cmd-btn:active { transform: scale(0.97); }
  .cmd-btn.loading { opacity: 0.5; pointer-events: none; }
  .cmd-btn.accent { border-color: var(--accent); color: var(--accent); }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); }
  ::-webkit-scrollbar-thumb:hover { background: #404040; }
  footer {
    background: #0e0e0e; border-top: 1px solid #534434;
    height: 24px; display: flex; align-items: center;
    justify-content: space-between; padding: 0 16px; flex-shrink: 0;
    font-size: 11px; color: #888;
  }
  .file-upload-zone {
    border: 1px dashed var(--border); padding: 6px 10px;
    font-size: 11px; color: var(--dim); cursor: pointer;
    transition: border-color 0.15s; display: inline-block;
  }
  .file-upload-zone:hover { border-color: var(--accent); }
</style>
</head>
<body>
<header>
  <div class="title">SCAFFOLD</div>
  <div class="status">
    <span class="material-symbols-outlined" style="font-size:14px">terminal</span>
    <span id="ollama-status">Checking...</span>
  </div>
</header>
<div class="utility-bar">
  <div style="display:flex;align-items:center;gap:6px">
    <span class="material-symbols-outlined" style="font-size:14px">visibility</span>
    <span>Dashboard — Offline AI Tutor</span>
  </div>
  <div style="display:flex;align-items:center;gap:4px">
    <span class="status-dot idle" id="status-dot"></span>
    <span id="status-text" style="font-weight:700;color:#888">IDLE</span>
  </div>
</div>
<div class="main-layout">
  <div class="sidebar">
    <div class="sidebar-header">Logged Mistakes</div>
    <div class="sidebar-list" id="mistake-list">
      <div class="welcome-msg">No mistakes logged yet.</div>
    </div>
    <div style="padding:8px;border-top:1px solid var(--border)">
      <div class="sidebar-header" style="padding:4px 0;border:none">Workspace Files</div>
      <select id="file-select" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);font-family:'JetBrains Mono',monospace;font-size:11px;padding:6px;">
        <option value="">Loading files...</option>
      </select>
    </div>
  </div>
  <div class="output-area">
    <div id="output-scroll">
        Welcome to Scaffold Dashboard.<br><br>
        All commands work here:<br>
        <span style="color:var(--accent)">hint</span> — get a hint for your most recent error<br>
        <span style="color:var(--accent)">review</span> — code quality review<br>
        <span style="color:var(--accent)">explain</span> — explain how your code works<br>
        <span style="color:var(--accent)">answer</span> — ask any programming question<br>
        <span style="color:var(--accent)">explain-image</span> — explain an uploaded image<br>
        <span style="color:var(--accent)">watch</span> — start the background file watcher<br>
    </div>
    <div class="input-section">
      <div class="input-row">
        <input type="text" id="cmd-input" placeholder="Type a question or command (e.g. explain main.py)..."
               autocomplete="off" autofocus style="flex:1"/>
        <label class="file-upload-zone" id="image-upload-zone" style="display:none">
          Upload Image
          <input type="file" id="image-file" accept="image/*" style="display:none"/>
        </label>
      </div>
      <div class="input-row">
        <button class="cmd-btn accent" onclick="runCommand('hint')">Hint</button>
        <button class="cmd-btn" onclick="runCommand('review')">Review</button>
        <button class="cmd-btn" onclick="runCommand('explain')">Explain</button>
        <button class="cmd-btn" onclick="runCommand('answer')">Answer</button>
        <button class="cmd-btn" onclick="runCommand('explain-image')">Image</button>
        <button class="cmd-btn" onclick="runCommand('ask-voice')">Voice</button>
        <button class="cmd-btn" onclick="runCommand('watch')">Watch</button>
      </div>
    </div>
  </div>
</div>
<footer>
  <div>~/Desktop/Scaffold</div>
  <div style="display:flex;gap:16px">
    <span>Python 3.13</span>
    <span>Gemma 4</span>
    <span id="footer-watch">Watch: Inactive</span>
  </div>
</footer>

<script>
const outputScroll = document.getElementById('output-scroll');
const cmdInput = document.getElementById('cmd-input');
const fileSelect = document.getElementById('file-select');
const imageUploadZone = document.getElementById('image-upload-zone');
const imageFile = document.getElementById('image-file');
let uploadedImageB64 = null;

cmdInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    let val = cmdInput.value.trim();
    let valLower = val.toLowerCase();
    // Strip "scaffold" prefix if present
    if (valLower.startsWith('scaffold ')) { valLower = valLower.substring(9).trim(); val = val.substring(9).trim(); }
    const cmds = ['hint','review','explain','answer','explain-image','ask-voice','watch'];
    let firstWord = valLower.split(' ')[0];
    if (firstWord === 'voice') firstWord = 'ask-voice';
    if (cmds.includes(firstWord)) {
      runCommand(firstWord, val.substring(firstWord.length).trim());
      cmdInput.value = '';
    } else if (val) {
      runCommand('answer', val);
      cmdInput.value = '';
    }
  }
});

// Show/hide contextual inputs based on focused button
document.querySelectorAll('.cmd-btn').forEach(btn => {
  btn.addEventListener('mouseenter', () => {
    const cmd = btn.textContent.trim().toLowerCase();
    imageUploadZone.style.display = (cmd === 'image') ? 'inline-block' : 'none';
  });
});

imageFile.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    uploadedImageB64 = reader.result.split(',')[1];
    imageUploadZone.textContent = file.name;
  };
  reader.readAsDataURL(file);
});

function setStatus(text, active) {
  document.getElementById('status-dot').className = 'status-dot ' + (active ? 'active' : 'idle');
  const el = document.getElementById('status-text');
  el.textContent = text;
  el.style.color = active ? '#F59E0B' : '#888';
}

function appendOutput(html) {
  const existing = outputScroll.querySelector('.welcome-msg');
  if (existing) existing.remove();
  outputScroll.insertAdjacentHTML('beforeend', html);
  outputScroll.scrollTop = outputScroll.scrollHeight;
}

function escHtml(s) {
  const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
}

async function runCommand(cmd, customInput = null) {
  document.querySelectorAll('.cmd-btn').forEach(b => b.classList.add('loading'));
  setStatus('WORKING', true);

  const selectedFile = fileSelect.value;
  const userInput = customInput !== null ? customInput : cmdInput.value.trim();

  const labelText = cmd === 'answer' ? `ask: ${userInput}` : `scaffold ${cmd}` + (userInput ? ` ${userInput}` : (selectedFile ? ` ${selectedFile.split(/[/\\\\]/).pop()}` : ''));
  appendOutput(`<div class="output-block" id="loading-block"><div class="label">$ ${escHtml(labelText)}</div><div class="raw" style="color:var(--dim)">Running...</div></div>`);

  const body = { command: cmd, file: selectedFile, input: userInput };
  if (uploadedImageB64) { body.image_b64 = uploadedImageB64; }

  try {
    const res = await fetch('/api/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await res.json();
    const lb = document.getElementById('loading-block');
    if (lb) lb.remove();

    if (data.error) {
      appendOutput(`<div class="output-block"><div class="label">Error</div><div class="raw" style="color:var(--red)">${escHtml(data.error)}</div></div>`);
    } else if (data.parsed && data.parsed.length > 0) {
      data.parsed.forEach(p => {
        let content = '';
        if (p.line) content += `<div><span class="line-num">LINE: ${p.line}</span></div>`;
        if (p.issue) content += `<div><span class="issue">ISSUE: ${escHtml(p.issue)}</span></div>`;
        if (p.why) content += `<div><span class="why">WHY: ${escHtml(p.why)}</span></div>`;
        if (p.hint) content += `<div><span class="hint">HINT: ${escHtml(p.hint)}</span></div>`;
        if (p.current) content += `<div><span class="issue">CURRENT: ${escHtml(p.current)}</span></div>`;
        if (p.better) content += `<div><span class="hint">BETTER: ${escHtml(p.better)}</span></div>`;
        appendOutput(`<div class="output-block"><div class="label">$ ${escHtml(labelText)}</div>${content}</div>`);
      });
    } else if (data.raw) {
      appendOutput(`<div class="output-block"><div class="label">$ ${escHtml(labelText)}</div><div class="raw">${escHtml(data.raw)}</div></div>`);
    }
  } catch (err) {
    const lb = document.getElementById('loading-block');
    if (lb) lb.remove();
    appendOutput(`<div class="output-block"><div class="label">Error</div><div class="raw" style="color:var(--red)">${escHtml(err.message)}</div></div>`);
  }

  setStatus('IDLE', false);
  document.querySelectorAll('.cmd-btn').forEach(b => b.classList.remove('loading'));
  uploadedImageB64 = null;
  cmdInput.value = '';
}

async function refreshMistakes() {
  try {
    const res = await fetch('/api/mistakes');
    const data = await res.json();
    const list = document.getElementById('mistake-list');
    if (!data.mistakes || data.mistakes.length === 0) {
      list.innerHTML = '<div class="welcome-msg">No mistakes logged yet.</div>';
      return;
    }
    list.innerHTML = data.mistakes.map(m => {
      const concept = (m.concept || 'error').replace(/_/g, ' ').toUpperCase();
      const file = m.file ? m.file.split(/[/\\]/).pop() : '?';
      const colors = {syntax: 'var(--accent)', logic: 'var(--red)', runtime: 'var(--cyan)'};
      const c = colors[m.error_type] || 'var(--accent)';
      return `<div class="mistake-card">
        <div class="concept" style="color:${c}">${concept}</div>
        <div class="msg">${escHtml(m.message || '')} — ${file}:${m.line || '?'}</div>
      </div>`;
    }).join('');
  } catch(e) {}
}

async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('ollama-status').textContent = data.ollama ? 'Ollama Connected' : 'Ollama Offline';
    document.getElementById('ollama-status').style.color = data.ollama ? '#22c55e' : '#ffb4ab';
  } catch(e) {}
}

async function refreshFiles() {
  try {
    const res = await fetch('/api/files');
    const data = await res.json();
    const sel = document.getElementById('file-select');
    sel.innerHTML = '<option value="">(select a file)</option>';
    (data.files || []).forEach(f => {
      const opt = document.createElement('option');
      opt.value = f; opt.textContent = f.split(/[/\\]/).pop();
      sel.appendChild(opt);
    });
  } catch(e) {}
}

refreshMistakes(); refreshStatus(); refreshFiles();
setInterval(refreshStatus, 10000);

// Real-time EventSource connection for mistakes streaming
const evtSource = new EventSource("/api/mistakes/stream");
evtSource.onmessage = (event) => {
  try {
    const mistakes = JSON.parse(event.data);
    const list = document.getElementById('mistake-list');
    if (!mistakes || mistakes.length === 0) {
      list.innerHTML = '<div class="welcome-msg">No mistakes logged yet.</div>';
      return;
    }
    list.innerHTML = mistakes.map(m => {
      const concept = (m.concept || 'error').replace(/_/g, ' ').toUpperCase();
      const file = m.file ? m.file.split(/[/\\]/).pop() : '?';
      const colors = {syntax: 'var(--accent)', logic: 'var(--red)', runtime: 'var(--cyan)'};
      const c = colors[m.error_type] || 'var(--accent)';
      return `<div class="mistake-card">
        <div class="concept" style="color:${c}">${concept}</div>
        <div class="msg">${escHtml(m.message || '')} — ${file}:${m.line || '?'}</div>
      </div>`;
    }).join('');
  } catch(e) {}
};
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/status")
def api_status():
    return jsonify({"ollama": is_ollama_running()})


@app.route("/api/mistakes/stream")
def api_mistakes_stream():
    def event_stream():
        import time
        last_mtime = 0
        while True:
            if MISTAKES_FILE.exists():
                try:
                    mtime = MISTAKES_FILE.stat().st_mtime
                    if mtime > last_mtime:
                        last_mtime = mtime
                        data = json.loads(MISTAKES_FILE.read_text(encoding="utf-8"))
                        if isinstance(data, list):
                            yield f"data: {json.dumps(list(reversed(data))[:20])}\n\n"
                except Exception:
                    pass
            else:
                yield "data: []\n\n"
            time.sleep(0.5)
    from flask import Response
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/mistakes")
def api_mistakes():
    if not MISTAKES_FILE.exists():
        return jsonify({"mistakes": []})
    try:
        data = json.loads(MISTAKES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return jsonify({"mistakes": list(reversed(data))[:20]})
    except Exception:
        pass
    return jsonify({"mistakes": []})


@app.route("/api/files")
def api_files():
    exts = ('.py', '.js', '.ts', '.c', '.cpp', '.java', '.go', '.rs', '.rb', '.txt', '.html', '.css')
    files = []
    for ext in exts:
        for f in PROJECT_ROOT.rglob(f"*{ext}"):
            rel = str(f.relative_to(PROJECT_ROOT))
            if '.git' not in rel and 'node_modules' not in rel and '__pycache__' not in rel and '.egg' not in rel:
                files.append(str(f))
    files.sort()
    return jsonify({"files": files[:100]})


@app.route("/api/command", methods=["POST"])
def api_command():
    body = request.get_json(silent=True) or {}
    cmd = body.get("command", "").strip().lower()
    file_path = body.get("file", "").strip()
    user_input = body.get("input", "").strip()
    image_b64 = body.get("image_b64", "")

    # Strip "scaffold" prefix from input if present
    if user_input.lower().startswith("scaffold "):
        user_input = user_input[9:].strip()

    # If user typed a full command string like "review calculator.py" into the input,
    # parse the command and file argument out of user_input
    known_cmds = ["hint", "review", "explain", "answer", "explain-image", "ask-voice", "watch"]
    if user_input:
        parts = user_input.split(None, 1)
        first_word = parts[0].lower() if parts else ""
        if first_word == 'voice':
            first_word = 'ask-voice'
        if first_word in known_cmds:
            cmd = first_word
            user_input = parts[1] if len(parts) > 1 else ""

    # For commands that need a file, try to resolve from user_input if no file selected
    if cmd in ["review", "explain"] and not file_path and user_input:
        # user_input might be a filename like "calculator.py"
        resolved = _find_file(user_input)
        if resolved:
            file_path = resolved
            user_input = ""
        else:
            return jsonify({"error": f"File '{user_input}' not found in the workspace."})

    if cmd == "hint":
        return _run_hint(user_input)
    elif cmd == "review":
        return _run_review(file_path)
    elif cmd == "explain":
        return _run_explain(file_path, user_input)
    elif cmd == "answer":
        return _run_answer(user_input)
    elif cmd == "explain-image":
        return _run_explain_image(image_b64)
    elif cmd == "ask-voice":
        return _run_ask_voice()
    elif cmd == "watch":
        return _run_watch()
    else:
        return jsonify({"error": f"Unknown command: '{cmd}'. Try: hint, review, explain, answer, ask-voice, watch"})


def _find_file(name):
    """Search the workspace for a file by name."""
    name_lower = name.lower().strip()
    for root, _, files in os.walk(PROJECT_ROOT):
        rel = os.path.relpath(root, PROJECT_ROOT)
        if '.git' in rel or '__pycache__' in rel or '.egg' in rel:
            continue
        for f in files:
            if f.lower() == name_lower:
                return os.path.join(root, f)
    return None


def _check_ollama():
    if not is_ollama_running():
        return {"error": "Ollama is not running. Start it with 'ollama serve' or run 'scaffold setup'."}
    return None


def _read_file(file_path):
    if not file_path:
        return None, "No file selected. Pick a file from the sidebar dropdown first."
    p = Path(file_path)
    if not p.exists():
        return None, f"File not found: {file_path}"
    try:
        return p.read_text(encoding="utf-8", errors="replace"), None
    except Exception as e:
        return None, f"Could not read file: {e}"


def _run_hint(user_input=""):
    from scaffold.state import load_last_practice, save_last_practice, clear_last_practice
    from scaffold.mistake_log import get_recent_error, should_generate_practice, get_concept_errors
    from scaffold.prompts import build_hint_prompt, build_practice_prompt, build_eval_prompt

    err = _check_ollama()
    if err: return jsonify(err)

    practice = load_last_practice()
    if practice is not None:
        if not user_input:
            return jsonify({"raw": f"**Practice Question:**\n\n{practice['question']}\n\n*Type your answer in the input box and click Hint again.*"})
        else:
            eval_prompt = build_eval_prompt(practice['question'], user_input)
            response = query_gemma(eval_prompt, stream=False)
            clear_last_practice()
            return jsonify({"raw": f"**Evaluating your answer:**\n\n{response}"})

    error = get_recent_error()
    if error is None:
        return jsonify({"error": "No recent errors found. Write some code and the watcher will catch mistakes!"})

    concept = error.get("concept", "")
    if concept and should_generate_practice(concept):
        past_errors = get_concept_errors(concept)
        prompt = build_practice_prompt(concept, past_errors)
        response = query_gemma(prompt, stream=False)
        if response:
            save_last_practice(concept, response)
            return jsonify({"raw": f"**Practice Question:**\n\n{response}\n\n*Type your answer in the input box and click Hint again.*"})

    source_code = ""
    fp = error.get("file", "")
    if fp and Path(fp).exists():
        try: source_code = Path(fp).read_text(encoding="utf-8", errors="replace")
        except Exception: pass

    prompt = build_hint_prompt(source_code, error)
    response = query_gemma(prompt, stream=False)
    if response is None:
        return jsonify({"error": "Model failed to respond. Is the Gemma model loaded?"})
    parsed = parse_model_response(response)
    return jsonify({"parsed": parsed, "raw": response})


def _run_check(file_path, expected):
    err = _check_ollama()
    if err: return jsonify(err)

    code, file_err = _read_file(file_path)
    if file_err: return jsonify({"error": file_err})

    if not expected:
        return jsonify({"error": "Please provide the expected output in the 'Expected output' field, then click Check."})

    import subprocess, sys
    try:
        result = subprocess.run(
            [sys.executable, file_path],
            capture_output=True, text=True, timeout=10, cwd=str(PROJECT_ROOT)
        )
        actual = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        actual = "(program timed out after 10 seconds)"
    except Exception as e:
        actual = f"(could not run file: {e})"

    prompt = build_check_prompt(code, expected, actual)
    response = query_gemma(prompt, stream=False)
    if response is None:
        return jsonify({"error": "Model failed to respond."})
    parsed = parse_model_response(response)
    return jsonify({"parsed": parsed, "raw": response})


def _run_review(file_path):
    err = _check_ollama()
    if err: return jsonify(err)

    code, file_err = _read_file(file_path)
    if file_err: return jsonify({"error": file_err})

    prompt = build_review_prompt(code)
    response = query_gemma(prompt, stream=False)
    if response is None:
        return jsonify({"error": "Model failed to respond."})
    parsed = parse_model_response(response)
    return jsonify({"parsed": parsed, "raw": response})


def _run_explain(file_path, input_val):
    err = _check_ollama()
    if err: return jsonify(err)

    code, file_err = _read_file(file_path)
    if file_err: return jsonify({"error": file_err})

    if input_val:
        prompt = build_trace_prompt(code, input_val)
    else:
        prompt = build_explain_prompt(code)

    response = query_gemma(prompt, stream=False)
    if response is None:
        return jsonify({"error": "Model failed to respond."})
    return jsonify({"raw": response})


def _run_answer(question):
    err = _check_ollama()
    if err: return jsonify(err)

    if not question:
        return jsonify({"error": "Type your question in the input field, then click Answer."})

    prompt = build_answer_prompt(question)
    response = query_gemma(prompt, stream=False)
    if response is None:
        return jsonify({"error": "Model failed to respond."})
    return jsonify({"raw": response})


def _run_explain_image(image_b64):
    err = _check_ollama()
    if err: return jsonify(err)

    if not image_b64:
        return jsonify({"error": "Upload an image first by hovering over the Image button and clicking the upload zone."})

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        return jsonify({"error": "Invalid image data."})

    prompt = build_image_prompt()
    response = query_gemma(prompt, images=[image_bytes], stream=False)
    if response is None:
        return jsonify({"error": "Model failed to respond. Is the LLaVA model pulled?"})
    return jsonify({"raw": response})


def _run_watch():
    def _start_watcher():
        try:
            from scaffold.watcher import start_watcher
            start_watcher(str(PROJECT_ROOT), daemon=False)
        except Exception:
            pass

    t = threading.Thread(target=_start_watcher, daemon=True)
    t.start()
    return jsonify({"raw": "Watcher started in background. It will monitor your project files for errors and log them to the sidebar."})


def _run_ask_voice():
    err = _check_ollama()
    if err: return jsonify(err)

    try:
        from scaffold.voice_input import record_and_transcribe
        # Record and transcribe for 10 seconds from default microphone
        transcription = record_and_transcribe(duration=10)
    except Exception as e:
        return jsonify({"error": f"Voice recording failed: {e}"})

    if not transcription:
        return jsonify({"error": "Could not capture or transcribe audio. Please make sure your mic is connected and unmuted."})

    from scaffold.prompts import build_voice_prompt
    prompt = build_voice_prompt(transcription)
    response = query_gemma(prompt, stream=False)
    if response is None:
        return jsonify({"error": "Model failed to respond."})

    return jsonify({"raw": f"[Heard: \"{transcription}\"]\n\n{response}"})


def main():
    print("\n  Scaffold Dashboard starting...")
    print("  Open your browser to: http://localhost:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
