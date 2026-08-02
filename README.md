# Scaffold 🚀

An offline, privacy-first AI programming companion and tutor powered by Google's **Gemma 4** model via Ollama. Scaffold acts as a Socratic coding assistant for beginner engineers, guiding them through errors and programming concepts rather than just writing the code for them.

---

## 💡 Core Philosophy
- **Privacy & Offline First**: Everything runs entirely on your local machine using Ollama. No source code or learning history ever leaves your device.
- **Socratic Guidance**: Scaffold **never** writes or corrects code for you. Instead, it provides structured breakdowns, hints, and concept-reinforcing practice questions to help you learn and fix the bugs yourself.

---

## 🛠️ Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/geekyfromgreek/Scaffold-_Build_with_gemma.git
   cd Scaffold-_Build_with_gemma
   ```

2. **Install Scaffold in Editable/Development Mode**:
   ```bash
   pip install -e .
   ```

3. **Run the Setup Wizard**:
   The installer automatically checks your local environment and configures the Gemma model:
   ```bash
   scaffold setup
   ```
   *What this does:*
   - Checks if **Ollama** is installed and running (guides you through installation if missing).
   - Pulls the local Gemma 4 model (`gemma4:e2b`, ~7.2 GB).

---

## 💻 Commands

### 1. `scaffold setup`
Runs the wizard to verify your local Ollama environment and pull the required Gemma 4 model.

### 2. `scaffold answer "[query]"`
Ask any general programming or conceptual question. Gemma 4 will stream the explanation in real-time inside a formatted panel.

- **Ask directly**:
  ```bash
  scaffold answer "What is the difference between a list and a tuple in Python?"
  ```
- **Interactive Mode**: Run without any arguments to open an interactive tutor shell loop:
  ```bash
  scaffold answer
  ```

### 3. `scaffold hint`
Queries the AI tutor for a Socratic hint regarding your most recent error.

- Explains the issue using a structured **LINE / ISSUE / WHY** format with code syntax-highlighting.
- **Adaptive Practice**: If you make the same category of mistake **3 or more times**, Scaffold will automatically shift from giving hints to generating a conceptual **practice question** to reinforce your understanding. You can submit your answer using `scaffold answer "<your explanation>"`.

---

## 📂 Project Structure
```text
Scaffold/
├── pyproject.toml      # Package dependencies and CLI entry point
├── README.md           # Documentation
├── .gitignore          # Git exclusion rules
└── scaffold/
    ├── __init__.py     # Package version metadata
    ├── cli.py          # Click CLI router and command definitions
    ├── ollama_client.py# Local Ollama library connector
    ├── prompts.py      # Socratic prompts enforcing the NO_CODE rule
    ├── display.py      # Terminal UI rendering using Rich
    ├── mistake_log.py  # Local JSON mistake log database (~/.scaffold/mistakes.json)
    └── state.py        # Lightweight JSON state persistence (~/.scaffold/state.json)
```
