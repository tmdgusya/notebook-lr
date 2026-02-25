# 📓 notebook-lr: Learning Notebook System

> A Jupyter-like notebook system with persistent session context for learning and experimentation.

---

## 🎯 Goal

Create a lightweight, Jupyter notebook-inspired system where:
- Code cells can be executed sequentially
- **Session context (variables, imports, state) persists across cell executions**
- Perfect for learning, experimentation, and documentation
- Works in both CLI and web interface

---

## 🏗️ Architecture

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

---

## 📋 Requirements

### Core Features
1. **Cell Execution**: Execute Python code cells with persistent state
2. **Session Management**: Save/load full execution context (variables, imports, etc.)
3. **Notebook Format**: Custom `.nblr` format (JSON-based)
4. **Output Capture**: stdout, stderr, rich outputs (images, tables)
5. **History**: Execution history with undo/redo

### UI Options
1. **CLI TUI**: Rich-based terminal interface
2. **Web UI**: Gradio-based web interface

### Persistence
1. **Session State**: Pickle the entire namespace after each cell
2. **Notebook Files**: Save code cells and outputs
3. **Checkpoints**: Auto-save every N cells

---

## 🗂️ Directory Structure

```
notebook-lr/
├── notebook_lr/
│   ├── __init__.py
│   ├── kernel.py          # IPython kernel wrapper
│   ├── notebook.py        # Notebook file format
│   ├── session.py         # Session persistence
│   ├── cli.py             # CLI interface
│   ├── web.py             # Web interface
│   └── utils.py           # Utilities
├── tests/
│   ├── test_kernel.py
│   ├── test_notebook.py
│   └── test_session.py
├── examples/
│   ├── hello.nblr
│   └── ml_intro.nblr
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 🔧 Implementation Details

### 1. Kernel (`kernel.py`)
```python
class NotebookKernel:
    """
    Persistent IPython kernel that maintains execution state.
    """
    def __init__(self):
        self.ip = InteractiveShell.instance()
        self.execution_count = 0
        self.history = []
    
    def execute_cell(self, code: str) -> ExecutionResult:
        """Execute code and return result with outputs."""
        # Run in the persistent namespace
        result = self.ip.run_cell(code)
        self.execution_count += 1
        return ExecutionResult(
            success=result.success,
            outputs=self._capture_outputs(),
            execution_count=self.execution_count
        )
    
    def get_namespace(self) -> dict:
        """Get current namespace for serialization."""
        return self.ip.user_ns.copy()
    
    def restore_namespace(self, namespace: dict):
        """Restore namespace from previous session."""
        self.ip.user_ns.update(namespace)
```

### 2. Notebook Format (`notebook.py`)
```python
class Notebook:
    """
    .nblr file format - JSON-based notebook storage.
    """
    def __init__(self, cells: list[Cell] = None):
        self.cells = cells or []
        self.metadata = {}
        self.session_state = None
    
    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "cells": [cell.to_dict() for cell in self.cells],
            "metadata": self.metadata,
            "session_state": self.session_state
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Notebook":
        # Load cells and restore session if present
        ...
```

### 3. Session Persistence (`session.py`)
```python
class SessionManager:
    """
    Manages saving/loading of kernel state.
    """
    def save_session(self, kernel: NotebookKernel, path: Path):
        """Pickle the entire kernel namespace."""
        state = {
            "user_ns": kernel.get_namespace(),
            "execution_count": kernel.execution_count,
            "history": kernel.history
        }
        pickle.dump(state, path.open("wb"))
    
    def load_session(self, kernel: NotebookKernel, path: Path):
        """Restore kernel from saved state."""
        state = pickle.load(path.open("rb"))
        kernel.restore_namespace(state["user_ns"])
        kernel.execution_count = state["execution_count"]
        kernel.history = state["history"]
```

### 4. CLI TUI (`cli.py`)
```python
# Rich-based interactive interface
# - Cell editor with syntax highlighting
# - Output display with rich formatting
# - Command palette for actions
```

### 5. Web UI (`web.py`)
```python
# Gradio-based web interface
# - Code editor component
# - Output display
# - Cell navigation
```

---

## 🧪 Testing Requirements

1. **Kernel Tests**:
   - Execute code and verify persistence
   - Test import caching
   - Test error handling

2. **Session Tests**:
   - Save/load roundtrip
   - Verify namespace restoration
   - Test with complex objects (pandas, matplotlib)

3. **Integration Tests**:
   - Full notebook workflow
   - CLI interactions
   - Web UI interactions (if applicable)

---

## 📦 Dependencies

```
ipython>=8.0.0
rich>=13.0.0
pydantic>=2.0.0
click>=8.0.0
gradio>=4.0.0  # optional, for web UI
pickle5        # for older Python versions
```

---

## 🚀 Usage Flow

### CLI Mode
```bash
# Create new notebook
notebook-lr new hello.nblr

# Open with TUI
notebook-lr edit hello.nblr

# Run notebook
notebook-lr run hello.nblr
```

### Web Mode
```bash
# Launch web interface
notebook-lr web hello.nblr
```

### Python API
```python
from notebook_lr import Notebook, NotebookKernel

# Create notebook with persistent session
nb = Notebook()
kernel = NotebookKernel()

# Execute cells with state persistence
result1 = kernel.execute_cell("x = 42")
result2 = kernel.execute_cell("print(x + 8)")  # Output: 50

# Save notebook with session
nb.save("session.nblr", include_session=True)

# Later: restore session
nb2 = Notebook.load("session.nblr")
kernel2 = NotebookKernel()
nb2.restore_session(kernel2)
# x is still 42!
```

---

## ✅ Success Criteria

1. ✅ Execute code cells with persistent state
2. ✅ Save/load notebook with full session context
3. ✅ CLI TUI works with rich output
4. ✅ Web UI works (if implemented)
5. ✅ Tests pass with >90% coverage
6. ✅ Example notebooks demonstrate features

---

## 🔄 Claude Code Instructions

Implement the notebook-lr system following this plan:

1. Create the package structure
2. Implement the kernel with IPython
3. Implement session persistence with pickle
4. Create CLI interface with Rich
5. Add tests for all components
6. Create example notebooks
7. Verify everything works end-to-end

**CRITICAL**: 
- Test thoroughly before declaring success
- Run the example notebook and verify state persistence
- Take screenshots of working CLI
- All tests must pass
