## Cursor Cloud specific instructions

**notebook-lr** is a Jupyter-like notebook system with persistent session context (Python ≥3.10, built with Hatchling, managed with `uv`).

### Services

| Service | Purpose | Command |
|---|---|---|
| CLI (TUI) | Interactive terminal notebook editor | `uv run notebook-lr edit <file.nblr>` |
| Web UI (Flask) | Browser-based notebook interface on port 7860 | `uv run notebook-lr web <file.nblr>` |
| MCP Server | AI assistant integration | `uv run python -m notebook_lr.mcp_server` |

### Running tests

```bash
uv run pytest --ignore=tests/test_e2e_web.py
```

The `test_e2e_web.py` file requires `playwright` which is not in the project's declared dependencies; skip it.

### Lint

No linter is configured in `pyproject.toml`. Python import validation can be checked with `uv run python -c "import notebook_lr"`.

### Build

```bash
uv build
```

### Key caveats

- The web server binds to `0.0.0.0:7860` (hardcoded in `notebook_lr/web.py`). No `--port` flag is available.
- `requirements.txt` references `gradio` but the actual web implementation uses Flask. The `pyproject.toml` dependencies are authoritative.
- The CLI `edit` command requires a TTY; use `run` for non-interactive execution or the Web UI / Python API for testing.
