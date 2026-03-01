"""
MCP server for notebook-lr using FastMCP.

This module provides MCP tools for interacting with Jupyter-like notebooks:
- Cell Content Operations: get_cell_source, update_cell_source
- Cell Management: add_cell, delete_cell, move_cell, get_cell, list_cells
- Notebook Operations: get_notebook_info, save_notebook
"""

import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from notebook_lr import Notebook, Cell, CellType, NotebookKernel, SessionManager, Comment


# Pydantic models for structured output
class CellOutput(BaseModel):
    """Output data from a cell."""
    index: int = Field(description="Cell index in the notebook")
    id: str = Field(description="Unique cell identifier")
    type: str = Field(description="Cell type: 'code' or 'markdown'")
    source: str = Field(description="Cell source content")
    outputs: list[dict] = Field(default_factory=list, description="Execution outputs")
    execution_count: Optional[int] = Field(default=None, description="Execution count")


class NotebookInfo(BaseModel):
    """Information about the notebook."""
    name: str = Field(description="Notebook name")
    cell_count: int = Field(description="Total number of cells")
    code_count: int = Field(description="Number of code cells")
    markdown_count: int = Field(description="Number of markdown cells")
    executed_count: int = Field(description="Number of executed cells")
    version: str = Field(description="Notebook format version")
    path: Optional[str] = Field(default=None, description="File path")


class CellList(BaseModel):
    """List of cells."""
    cells: list[CellOutput] = Field(description="Array of cells")


# Global state (would be managed properly in production)
_notebook: Optional[Notebook] = None
_kernel: Optional[NotebookKernel] = None
_session_manager: Optional[SessionManager] = None
_notebook_path: Optional[str] = None
_notebook_mtime: float = 0.0

mcp = FastMCP("notebook-lr")


def get_notebook() -> Notebook:
    """Get or create the current notebook, loading from NOTEBOOK_LR_PATH if set."""
    global _notebook, _notebook_path, _notebook_mtime
    if _notebook is None:
        env_path = os.environ.get("NOTEBOOK_LR_PATH")
        if env_path and os.path.isfile(env_path):
            _notebook_path = env_path
            _notebook = Notebook.load(Path(env_path))
            _notebook_mtime = os.path.getmtime(env_path)
        else:
            _notebook = Notebook.new()
            if env_path:
                _notebook_path = env_path
    return _notebook


def _maybe_reload() -> None:
    """Reload notebook from file if it was modified externally."""
    global _notebook, _notebook_mtime
    if _notebook_path is None:
        return
    try:
        current_mtime = os.path.getmtime(_notebook_path)
        if current_mtime != _notebook_mtime:
            _notebook = Notebook.load(Path(_notebook_path))
            _notebook_mtime = current_mtime
    except OSError:
        pass


def _auto_save() -> None:
    """Save notebook to file after mutations."""
    global _notebook_mtime
    if _notebook_path is None or _notebook is None:
        return
    _notebook.save(Path(_notebook_path))
    _notebook_mtime = os.path.getmtime(_notebook_path)


def get_kernel() -> NotebookKernel:
    """Get or create the current kernel."""
    global _kernel
    if _kernel is None:
        _kernel = NotebookKernel()
    return _kernel


def get_session_manager() -> SessionManager:
    """Get or create the session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def _validate_index(index: int) -> None:
    """Validate that an index is within range."""
    notebook = get_notebook()
    if index < 0 or index >= len(notebook.cells):
        raise ValueError(f"Cell index {index} out of range (0-{len(notebook.cells) - 1})")


def _cell_to_output(cell: Cell, index: int) -> CellOutput:
    """Convert a Cell to CellOutput."""
    return CellOutput(
        index=index,
        id=cell.id,
        type=cell.type.value,
        source=cell.source,
        outputs=cell.outputs,
        execution_count=cell.execution_count
    )


# =============================================================================
# Cell Content Operations
# =============================================================================

@mcp.tool()
def get_cell_source(index: int) -> str:
    """Get the source content of a cell at the specified index.

    Args:
        index: Zero-based index of the cell

    Returns:
        The cell's source code as a string

    Raises:
        ValueError: If index is out of range
    """
    _maybe_reload()
    notebook = get_notebook()
    _validate_index(index)
    cell = notebook.get_cell(index)
    return cell.source


@mcp.tool()
def update_cell_source(index: int, source: str) -> bool:
    """Update the source content of a cell at the specified index.

    Args:
        index: Zero-based index of the cell
        source: New source code to set

    Returns:
        True if successful

    Raises:
        ValueError: If index is out of range
    """
    notebook = get_notebook()
    _validate_index(index)
    notebook.update_cell(index, source=source)
    _auto_save()
    return True


# =============================================================================
# Cell Management Operations
# =============================================================================

@mcp.tool()
def add_cell(
    cell_type: str = "code",
    after_index: Optional[int] = None,
    source: str = ""
) -> CellOutput:
    """Add a new cell to the notebook.

    Args:
        cell_type: Type of cell - 'code' or 'markdown' (default: 'code')
        after_index: Insert after this index. If None, append to end. (default: None)
        source: Initial source content (default: empty string)

    Returns:
        CellOutput with index, id, type, and source of the new cell

    Raises:
        ValueError: If cell_type is invalid
    """
    notebook = get_notebook()

    # Validate cell type
    if cell_type not in ("code", "markdown"):
        raise ValueError(f"Invalid cell type: {cell_type}. Must be 'code' or 'markdown'.")

    ct = CellType.CODE if cell_type == "code" else CellType.MARKDOWN
    cell = Cell(type=ct, source=source)

    # Determine insertion index
    if after_index is not None:
        _validate_index(after_index)
        new_idx = after_index + 1
    else:
        new_idx = len(notebook.cells)

    notebook.insert_cell(new_idx, cell)
    _auto_save()

    return _cell_to_output(cell, new_idx)


@mcp.tool()
def delete_cell(index: int) -> bool:
    """Delete a cell at the specified index.

    Args:
        index: Zero-based index of the cell to delete

    Returns:
        True if successful

    Raises:
        ValueError: If index is out of range
    """
    notebook = get_notebook()
    _validate_index(index)
    notebook.remove_cell(index)
    _auto_save()
    return True


@mcp.tool()
def move_cell(index: int, direction: str) -> dict:
    """Move a cell up or down in the notebook.

    Args:
        index: Zero-based index of the cell to move
        direction: Direction to move - 'up' or 'down'

    Returns:
        Dict with 'ok' (bool) and 'new_index' (int) if successful

    Raises:
        ValueError: If move is not possible (at boundaries) or direction is invalid
    """
    notebook = get_notebook()
    _validate_index(index)

    if direction not in ("up", "down"):
        raise ValueError(f"Invalid direction: {direction}. Must be 'up' or 'down'.")

    if direction == "up":
        if index == 0:
            raise ValueError("Cannot move first cell up.")
        notebook.cells[index], notebook.cells[index - 1] = (
            notebook.cells[index - 1],
            notebook.cells[index],
        )
        _auto_save()
        return {"ok": True, "new_index": index - 1}
    else:  # direction == "down"
        if index == len(notebook.cells) - 1:
            raise ValueError("Cannot move last cell down.")
        notebook.cells[index], notebook.cells[index + 1] = (
            notebook.cells[index + 1],
            notebook.cells[index],
        )
        _auto_save()
        return {"ok": True, "new_index": index + 1}


@mcp.tool()
def get_cell(index: int) -> CellOutput:
    """Get complete information about a cell at the specified index.

    Args:
        index: Zero-based index of the cell

    Returns:
        CellOutput with all cell properties including outputs

    Raises:
        ValueError: If index is out of range
    """
    _maybe_reload()
    notebook = get_notebook()
    _validate_index(index)
    cell = notebook.get_cell(index)
    return _cell_to_output(cell, index)


@mcp.tool()
def list_cells() -> CellList:
    """Get a list of all cells in the notebook.

    Returns:
        CellList containing an array of all cells with their indices
    """
    _maybe_reload()
    notebook = get_notebook()
    cells = [
        _cell_to_output(cell, i)
        for i, cell in enumerate(notebook.cells)
    ]
    return CellList(cells=cells)


# =============================================================================
# Notebook Operations
# =============================================================================

@mcp.tool()
def get_notebook_info() -> NotebookInfo:
    """Get information about the current notebook.

    Returns:
        NotebookInfo with metadata including name, cell counts, and version
    """
    _maybe_reload()
    notebook = get_notebook()
    name = notebook.metadata.get("name", "Untitled")
    cell_count = len(notebook.cells)
    code_count = sum(1 for c in notebook.cells if c.type == CellType.CODE)
    md_count = cell_count - code_count
    executed_count = sum(
        1 for c in notebook.cells if c.execution_count is not None
    )

    return NotebookInfo(
        name=name,
        cell_count=cell_count,
        code_count=code_count,
        markdown_count=md_count,
        executed_count=executed_count,
        version=notebook.version,
        path=notebook.metadata.get("path")
    )


@mcp.tool()
def save_notebook(
    path: Optional[str] = None,
    include_session: bool = False
) -> dict:
    """Save the notebook to a file.

    Args:
        path: File path to save to. If None, uses existing path or 'notebook.nblr'
        include_session: Whether to include kernel session state (default: False)

    Returns:
        Dict with 'status', 'path', and optionally session info
    """
    notebook = get_notebook()
    kernel = get_kernel()
    session_manager = get_session_manager()

    save_path = path or notebook.metadata.get("path", "notebook.nblr")

    if include_session:
        session_data = {
            "user_ns": kernel.get_namespace(),
            "execution_count": kernel.execution_count,
        }
        notebook.save(Path(save_path), include_session=True, session_data=session_data)
        session_manager.save_checkpoint(kernel, Path(save_path))
        status = "saved with session"
    else:
        notebook.save(Path(save_path))
        status = "saved"

    notebook.metadata["path"] = save_path
    # Update mtime tracking after explicit save
    global _notebook_mtime
    if _notebook_path:
        _notebook_mtime = os.path.getmtime(save_path)

    return {
        "status": status,
        "path": save_path
    }


# =============================================================================
# Comment & Context Operations
# =============================================================================

@mcp.tool()
def get_cell_comments(index: int) -> list[dict]:
    """Get all comments for the cell at the specified index."""
    _maybe_reload()
    notebook = get_notebook()
    _validate_index(index)
    cell = notebook.get_cell(index)
    return [c.model_dump() for c in cell.comments]


@mcp.tool()
def get_notebook_context(index: int) -> dict:
    """Get rich context about a cell for LLM consumption. Includes neighboring cells and comments."""
    _maybe_reload()
    notebook = get_notebook()
    _validate_index(index)
    cell = notebook.get_cell(index)

    previous_cell = None
    if index > 0:
        prev = notebook.get_cell(index - 1)
        previous_cell = {
            "type": prev.type.value,
            "source_preview": "\n".join(prev.source.splitlines()[:5]),
        }

    next_cell = None
    if index < len(notebook.cells) - 1:
        nxt = notebook.get_cell(index + 1)
        next_cell = {
            "type": nxt.type.value,
            "source_preview": "\n".join(nxt.source.splitlines()[:5]),
        }

    return {
        "cell_index": index,
        "total_cells": len(notebook.cells),
        "cell_type": cell.type.value,
        "cell_source": cell.source,
        "cell_outputs": cell.outputs[:3],
        "previous_cell": previous_cell,
        "next_cell": next_cell,
        "comments": [
            {
                "user_comment": c.user_comment,
                "status": c.status,
                "selected_text": c.selected_text,
            }
            for c in cell.comments
        ],
    }


# =============================================================================
# Module Reset (for testing)
# =============================================================================

def _reset_notebook() -> None:
    """Reset the global notebook state. Useful for testing."""
    global _notebook, _kernel, _session_manager, _notebook_path, _notebook_mtime
    _notebook = None
    _kernel = None
    _session_manager = None
    _notebook_path = None
    _notebook_mtime = 0.0


if __name__ == "__main__":
    mcp.run()
