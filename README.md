# Scaffold: The Offline AI Tutor 🚀

**Built for the Gemma for Good Hackathon**

Scaffold is a privacy-first, fully local programming tutor for students. Traditional AI coding assistants and chatbots write code *for* students, robbing them of the learning process. Scaffold takes a different approach: it acts exactly like a human Teaching Assistant. It watches your code, catches errors instantly, and guides you to the right answer without ever writing the code for you.

Because Scaffold runs **100% locally**, it is perfect for college computer labs, areas with poor internet, and students who want to learn without uploading their code to the cloud.

---

## 🛠️ The Student Workflow

Scaffold integrates seamlessly into a student's natural coding environment—the terminal and the browser.

### 1. Code & Save (`scaffold watch`)
Run the background watcher in your project directory. Every time you save your `.py` or `.c` file, Scaffold runs it. If it crashes, Scaffold securely logs the error without interrupting your flow.

### 2. Get Unstuck (`scaffold hint`)
When you hit a wall, you don't need to copy-paste your code into a browser. Just type `scaffold hint`. Scaffold analyzes your last error and your code context, and provides a **Socratic nudge** to help you figure it out yourself.

### 3. Adaptive Practice
If Scaffold notices you making the same type of mistake 3 times in a row (e.g., forgetting to indent), it intervenes! It automatically generates a custom, tailored practice question to test your fundamental understanding of the concept before letting you move on. Run `scaffold hint` again to answer the question and get feedback.

### 4. Interactive Learning
- **Chat (`scaffold answer`)**: Drop into a zero-latency interactive chat loop to ask questions about programming concepts.
- **Voice (`scaffold ask-voice`)**: Explain your confusion out loud to the tutor using your microphone.
- **Vision (`scaffold explain-image`)**: Take a screenshot of a confusing diagram or weird IDE behavior, and Scaffold will analyze it visually.

### 5. Web Dashboard (`python -m scaffold.app`)
Open **http://localhost:5000** for a browser-based dashboard with:
- Real-time mistake feed via SSE (auto-refreshes as errors are detected)
- File picker for your workspace
- All commands accessible via buttons and a text input bar
- Dark theme with JetBrains Mono typography

---

## 🏗️ Stack Architecture

Scaffold is designed to run efficiently on standard college hardware (e.g., 8GB RAM, i5 CPUs) without requiring dedicated GPUs.

- **Language & Reasoning Engine**: `gemma4:e2b` for rapid text generation and problem solving on low-end hardware.
- **Vision Engine**: `llava` for fast image analysis and visual debugging.
- **Speech-to-Text**: Local OpenAI Whisper (`base` model).
- **Backend**: Ollama (Localhost 11434).
- **CLI & UI**: Built with Python using **`click`** for command routing and **`rich`** for beautiful, syntax-highlighted, markdown-rendered terminal interfaces.
- **Web Dashboard**: Flask-based localhost server with Server-Sent Events for real-time updates.
- **State Management**: A lightweight, file-based locking system (`mistake_log.py`) safely tracks student errors in the background without needing a database.

---

## 🚀 Installation

### Windows Setup (Primary)
1. Clone this repository:
   ```cmd
   git clone https://github.com/geekyfromgreek/Scaffold.git
   cd Scaffold
   ```
2. Install the CLI:
   ```cmd
   pip install -e .
   ```
3. Run the automated setup (installs Ollama, downloads models, checks voice dependencies):
   ```cmd
   scaffold setup
   ```

### Ubuntu Setup
If you are running on an Ubuntu PC, you must first install the voice dependency before running the steps above:
```bash
sudo apt update
sudo apt install ffmpeg
```

---

## 📖 Command Reference

| Command | Description |
|---|---|
| `scaffold setup` | Install Ollama, pull AI models, and configure auto-start. |
| `scaffold watch` | Start the background watcher to catch errors automatically. |
| `scaffold hint` | Get a Socratic nudge for your most recent error. Triggers practice questions on repeated mistakes. |
| `scaffold answer` | Start an interactive Q&A loop with the tutor. |
| `scaffold ask-voice` | Ask a question using your microphone (10s recording). |
| `scaffold ask-voice <file>` | Transcribe and answer a question from an audio file. |
| `scaffold check <file> --expected "<output>"` | Automatically test your logic against expected output. |
| `scaffold run <file>` | Run your code and capture output. |
| `scaffold explain <file>` | Get a concise explanation of what a file does. |
| `scaffold explain <file> --input "<value>"` | Trace execution step-by-step with a given input. |
| `scaffold explain-image <path>` | Ask the tutor to explain an image file. |
| `scaffold explain-image --snip` | Explain the image currently in your clipboard. |
| `scaffold review <file>` | Get a quick code-quality review with hints. |
| `scaffold review <file> --efficiency` | Get a Big-O complexity analysis. |

### Web Dashboard
```cmd
python -m scaffold.app
```
Open **http://localhost:5000** in your browser. All commands are available via the UI.
