# PhantomShell — Phase-1 GitHub Codespaces Simulation

**AgenticX 2.0 Hackathon · Track 01 (Software: Agentic AI) · Team Vada Pav**

## 1-Click Run on GitHub Codespaces
1. Push this repository to GitHub and click **Code → Codespaces → Create codespace on main**.
2. `.devcontainer/devcontainer.json` automatically installs dependencies and runs the 35-test suite.
3. Launch the live Split-Screen Judge Demo UI:
   ```bash
   streamlit run app.py --server.port 8501 --server.address 0.0.0.0
   ```
   Port `8501` auto-forwards directly in your browser!

## Run Terminal Simulation & Tests
```bash
# Run all 35 verification, security & self-healing tests
python3 -m unittest -v tests/test_shell.py

# Run the automated 4-minute CLI demo simulation
python3 demo_cli.py
```

## Supported Worker Modes (Sidebar Selector)
* **`codespaces_sim` (Default):** Instant zero-GPU simulation with `<20 ms` SQLite POSIX Fast-Path, optional 4–12 ms OS timing jitter, realistic SQL/network replies, and live Manager Gate + Loop A giveaway self-healing.
* **`ollama`:** Connects to local `http://localhost:11434` (`qwen2.5:7b`).
* **`openai_compat`:** Uses `OPENAI_API_BASE` + `OPENAI_API_KEY` env vars (Groq / OpenRouter / Adaption) for live LLM inference inside Codespaces.
