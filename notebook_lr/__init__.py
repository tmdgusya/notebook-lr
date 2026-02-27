"""
notebook-lr: A Jupyter-like notebook system with persistent session context.

This package provides a lightweight notebook system where:
- Code cells can be executed sequentially
- Session context (variables, imports, state) persists across cell executions
- Perfect for learning, experimentation, and documentation
"""

from notebook_lr.kernel import NotebookKernel, ExecutionResult
from notebook_lr.notebook import Notebook, Cell, CellType, Comment
from notebook_lr.session import SessionManager

__version__ = "0.1.0"
__all__ = [
    "NotebookKernel",
    "ExecutionResult",
    "Notebook",
    "Cell",
    "CellType",
    "Comment",
    "SessionManager",
]
