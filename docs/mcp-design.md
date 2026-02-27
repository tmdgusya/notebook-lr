# MCP Server Design for notebook-lr

This document outlines the Model Context Protocol (MCP) server design for the notebook-lr project, which provides tools for interacting with Jupyter-like notebooks through the MCP protocol.

## Overview

The MCP server will expose tools for:
1. **Cell Content Operations** - Reading and updating cell source code
2. **Cell Management** - Adding, deleting, moving, and querying cells
3. **Notebook Operations** - Getting notebook info and saving notebooks

## Implementation Approach

We'll use the **FastMCP** approach from the MCP Python SDK (`mcp.server.fastmcp`) for its simplicity and automatic schema generation from type hints.

```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional

mcp = FastMCP("notebook-lr")
```

---

## Data Models

### Cell Output Model
```python
class CellOutput(BaseModel):
    """Output data from a cell execution."""
    index: int = Field(description="Cell index in the notebook")
    id: str = Field(description="Unique cell identifier")
    type: str = Field(description="Cell type: 'code' or 'markdown'")
    source: str = Field(description="Cell source content")
    outputs: list[dict] = Field(default_factory=list, description="Execution outputs")
    execution_count: Optional[int] = Field(default=None, description="Execution count for code cells")
```

### Notebook Info Model
```python
class NotebookInfo(BaseModel):
    """Information about the notebook."""
    name: str = Field(description="Notebook name")
    cell_count: int = Field(description="Total number of cells")
    code_count: int = Field(description="Number of code cells")
    markdown_count: int = Field(description="Number of markdown cells")
    executed_count: int = Field(description="Number of cells that have been executed")
    version: str = Field(description="Notebook format version")
    path: Optional[str] = Field(default=None, description="File path if loaded/saved")
```

### Cell List Model
```python
class CellList(BaseModel):
    """List of cells in the notebook."""
    cells: list[CellOutput] = Field(description="Array of cell data")
```

---

## Tool Specifications

### 1. Cell Content Operations

#### `get_cell_source`
Get the source code of a specific cell.

```python
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
    cell = notebook.get_cell(index)
    return cell.source
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "index": {
      "type": "integer",
      "description": "Zero-based index of the cell"
    }
  },
  "required": ["index"]
}
```

**Return Type:** `str`

---

#### `update_cell_source`
Update the source code of a specific cell.

```python
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
    notebook.update_cell(index, source=source)
    return True
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "index": {
      "type": "integer",
      "description": "Zero-based index of the cell"
    },
    "source": {
      "type": "string",
      "description": "New source code to set"
    }
  },
  "required": ["index", "source"]
}
```

**Return Type:** `bool`

---

### 2. Cell Management Operations

#### `add_cell`
Add a new cell to the notebook.

```python
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
    """
    ct = CellType.CODE if cell_type == "code" else CellType.MARKDOWN
    cell = Cell(type=ct, source=source)

    if after_index is not None:
        new_idx = after_index + 1
    else:
        new_idx = len(notebook.cells)

    notebook.insert_cell(new_idx, cell)

    return CellOutput(
        index=new_idx,
        id=cell.id,
        type=cell.type.value,
        source=cell.source,
        outputs=cell.outputs,
        execution_count=cell.execution_count
    )
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "cell_type": {
      "type": "string",
      "enum": ["code", "markdown"],
      "description": "Type of cell to create"
    },
    "after_index": {
      "type": "integer",
      "description": "Insert after this index. If not provided, appends to end."
    },
    "source": {
      "type": "string",
      "description": "Initial source content for the cell"
    }
  },
  "required": []
}
```

**Return Type:** `CellOutput`

---

#### `delete_cell`
Delete a cell from the notebook.

```python
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
    notebook.remove_cell(index)
    return True
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "index": {
      "type": "integer",
      "description": "Zero-based index of the cell to delete"
    }
  },
  "required": ["index"]
}
```

**Return Type:** `bool`

---

#### `move_cell`
Move a cell up or down in the notebook.

```python
@mcp.tool()
def move_cell(index: int, direction: str) -> dict:
    """Move a cell up or down in the notebook.

    Args:
        index: Zero-based index of the cell to move
        direction: Direction to move - 'up' or 'down'

    Returns:
        Dict with 'ok' (bool) and 'new_index' (int) if successful

    Raises:
        ValueError: If move is not possible (at boundaries)
    """
    if direction == "up":
        if 0 < index < len(notebook.cells):
            notebook.cells[index], notebook.cells[index - 1] = (
                notebook.cells[index - 1],
                notebook.cells[index],
            )
            return {"ok": True, "new_index": index - 1}
    elif direction == "down":
        if 0 <= index < len(notebook.cells) - 1:
            notebook.cells[index], notebook.cells[index + 1] = (
                notebook.cells[index + 1],
                notebook.cells[index],
            )
            return {"ok": True, "new_index": index + 1}

    raise ValueError(f"Cannot move cell at index {index} {direction}")
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "index": {
      "type": "integer",
      "description": "Zero-based index of the cell to move"
    },
    "direction": {
      "type": "string",
      "enum": ["up", "down"],
      "description": "Direction to move the cell"
    }
  },
  "required": ["index", "direction"]
}
```

**Return Type:** `dict` with `ok: bool` and `new_index: int`

---

#### `get_cell`
Get complete information about a specific cell.

```python
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
    cell = notebook.get_cell(index)
    return CellOutput(
        index=index,
        id=cell.id,
        type=cell.type.value,
        source=cell.source,
        outputs=cell.outputs,
        execution_count=cell.execution_count
    )
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "index": {
      "type": "integer",
      "description": "Zero-based index of the cell"
    }
  },
  "required": ["index"]
}
```

**Return Type:** `CellOutput`

---

#### `list_cells`
List all cells in the notebook.

```python
@mcp.tool()
def list_cells() -> CellList:
    """Get a list of all cells in the notebook.

    Returns:
        CellList containing an array of all cells with their indices
    """
    cells = [
        CellOutput(
            index=i,
            id=cell.id,
            type=cell.type.value,
            source=cell.source,
            outputs=cell.outputs,
            execution_count=cell.execution_count
        )
        for i, cell in enumerate(notebook.cells)
    ]
    return CellList(cells=cells)
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

**Return Type:** `CellList`

---

### 3. Notebook Operations

#### `get_notebook_info`
Get metadata and statistics about the notebook.

```python
@mcp.tool()
def get_notebook_info() -> NotebookInfo:
    """Get information about the current notebook.

    Returns:
        NotebookInfo with metadata including name, cell counts, and version
    """
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
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

**Return Type:** `NotebookInfo`

---

#### `save_notebook`
Save the notebook to a file.

```python
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

    return {
        "status": status,
        "path": save_path
    }
```

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "File path to save to (.nblr format)"
    },
    "include_session": {
      "type": "boolean",
      "description": "Whether to include kernel session state",
      "default": false
    }
  },
  "required": []
}
```

**Return Type:** `dict` with `status: str` and `path: str`

---

## Server Implementation Structure

```python
# File: notebook_lr/mcp_server.py
"""
MCP server for notebook-lr using FastMCP.
"""

from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from notebook_lr import Notebook, Cell, CellType, NotebookKernel, SessionManager


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

mcp = FastMCP("notebook-lr")


def get_notebook() -> Notebook:
    """Get or create the current notebook."""
    global _notebook
    if _notebook is None:
        _notebook = Notebook.new()
    return _notebook


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


# Tool implementations here...


if __name__ == "__main__":
    mcp.run()
```

---

## Usage Example

### Starting the Server

```bash
# From command line
python -m notebook_lr.mcp_server

# Or via Claude Code MCP configuration
# In claude_desktop_config.json:
{
  "mcpServers": {
    "notebook-lr": {
      "command": "uv",
      "args": ["run", "python", "-m", "notebook_lr.mcp_server"]
    }
  }
}
```

### Example Tool Calls

```python
# Add a new code cell
add_cell(cell_type="code", after_index=0, source="print('Hello, World!')")

# Get cell source
get_cell_source(index=0)

# Update cell source
update_cell_source(index=0, source="print('Updated!')")

# List all cells
list_cells()

# Get notebook info
get_notebook_info()

# Save notebook
save_notebook(path="my_notebook.nblr")
```

---

## Error Handling

All tools should raise `ValueError` with descriptive messages for invalid operations:

- Index out of range
- Invalid cell type
- Invalid direction for move operations
- File system errors for save/load

FastMCP will automatically convert these to appropriate MCP error responses.

---

## Future Enhancements

Potential additional tools not in initial scope:

1. **Execution tools**: `execute_cell`, `execute_all`
2. **Load operations**: `load_notebook`
3. **Variable inspection**: `list_variables`, `get_variable`
4. **Cell type conversion**: `convert_cell_type`
5. **Search/find**: `find_in_cells`, `replace_in_cells`
