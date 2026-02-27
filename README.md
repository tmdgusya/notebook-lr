# notebook-lr

> A Jupyter-like notebook system with persistent session context for learning and experimentation.

## Features

- **Persistent Execution State**: Variables, imports, and functions persist across cell executions
- **Session Persistence**: Save and restore the entire kernel state
- **Rich TUI**: Beautiful terminal interface with syntax highlighting
- **Web Interface**: Optional Gradio-based web UI
- **Simple Format**: JSON-based `.nblr` notebook files

## Installation

```bash
# Clone and install
git clone <repo-url>
cd notebook-lr
pip install -e .

# Or install with optional dependencies
pip install -e ".[web,dev]"
```

## Quick Start

### CLI Usage

```bash
# Create a new notebook
notebook-lr new my_notebook.nblr

# Edit with the interactive TUI
notebook-lr edit my_notebook.nblr

# Run non-interactively
notebook-lr run my_notebook.nblr

# List saved sessions
notebook-lr sessions

# Launch web interface
notebook-lr web my_notebook.nblr
```

### Python API

```python
from notebook_lr import Notebook, NotebookKernel, SessionManager

# Create a notebook with persistent kernel
nb = Notebook.new("My Notebook")
kernel = NotebookKernel()

# Execute cells - state persists!
kernel.execute_cell("x = 42")
result = kernel.execute_cell("print(x + 8)")  # Output: 50

# Add cells to notebook
nb.add_cell(source="x = 42")
nb.add_cell(source="print(x + 8)")

# Save with session state
nb.save("my_notebook.nblr", include_session=True,
        session_data={"user_ns": kernel.get_namespace()})

# Later: restore session
nb2 = Notebook.load("my_notebook.nblr")
kernel2 = NotebookKernel()
# ... restore session ...
```

## TUI Commands

| Key | Action |
|-----|--------|
| `Enter` | Edit current cell |
| `e` | Execute current cell |
| `E` | Execute all cells |
| `a` | Add cell after |
| `b` | Add cell before |
| `d` | Delete current cell |
| `m` | Toggle markdown/code |
| `s` | Save notebook |
| `S` | Save with session |
| `l` | Load session |
| `j/k` | Navigate cells |
| `?` | Show variables |
| `q` | Quit |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   CLI TUI    │  │   Web UI     │  │  Notebook File  │   │
│  │   (rich)     │  │  (gradio)    │  │   (.nblr)       │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Kernel Layer                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           IPython Kernel (persistent)               │   │
│  │  - Execution namespace (globals/locals)            │   │
│  │  - Import cache                                    │   │
│  │  - History and execution count                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Persistence Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Session Pickle│  │  Notebook    │  │   History    │      │
│  │   (state)    │  │   (.nblr)    │  │   (sqlite)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Notebook Format (.nblr)

Notebooks are stored as JSON files:

```json
{
  "version": "1.0",
  "cells": [
    {
      "id": "cell_1",
      "type": "code",
      "source": "x = 42",
      "outputs": [],
      "execution_count": 1,
      "metadata": {}
    }
  ],
  "metadata": {
    "name": "My Notebook",
    "created": "2024-01-01T00:00:00",
    "modified": "2024-01-01T00:00:00"
  },
  "session_state": null
}
```

## MCP Server

notebook-lr provides an MCP (Model Context Protocol) server that allows AI assistants like Claude to interact with your notebooks programmatically.

### Available Tools

**Cell Content Operations:**
- `get_cell_source(index)` - Get cell source code
- `update_cell_source(index, source)` - Update cell source

**Cell Management:**
- `add_cell(cell_type, after_index, source)` - Add new cell
- `delete_cell(index)` - Delete cell
- `move_cell(index, direction)` - Move cell up/down
- `get_cell(index)` - Get cell info
- `list_cells()` - List all cells

**Notebook Operations:**
- `get_notebook_info()` - Get notebook metadata
- `save_notebook(path, include_session)` - Save notebook

### Configure in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "notebook-lr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/notebook-lr", "python", "-m", "notebook_lr.mcp_server"],
      "cwd": "/path/to/notebook-lr"
    }
  }
}
```

Or use the CLI:

```bash
claude mcp add notebook-lr -- uv run --directory /path/to/notebook-lr python -m notebook_lr.mcp_server
```

### Run MCP Server Standalone

```bash
# Using uv
uv run python -m notebook_lr.mcp_server

# Or directly
python -m notebook_lr.mcp_server
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=notebook_lr
```

## License

MIT
