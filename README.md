# Phantomshell (Phase 1)

A multi-agent Python codebase built around a filesystem world-twin graph, agent orchestration modules, and dual adaptation evolution loops, configured for GitHub Codespaces[cite: 1].

## What Is Inside

- `app.py` and `demo_cli.py`: Main application entry points and command-line demo runner[cite: 1].
- `world_twin/fs_graph.py`: Filesystem world-twin graph model[cite: 1].
- `agents/manager_gate.py`, `agents/profiler_weaver.py`, and `agents/shell_worker.py`: Agent gating, profiling, and shell worker components[cite: 1].
- `evolution/loop_a_pace.py` and `evolution/loop_b_adaption.py`: Adaptation evolution loops[cite: 1].
- `tests/test_shell.py`: Test suite for shell behavior[cite: 1].
- `requirements.txt` and `.devcontainer/devcontainer.json`: Dependencies and dev container configuration[cite: 1].

## Run Locally

1. Install dependencies:
   pip install -r requirements.txt[cite: 1]
2. Run the demo:
   python demo_cli.py[cite: 1]
3. Run tests:
   pytest[cite: 1]
