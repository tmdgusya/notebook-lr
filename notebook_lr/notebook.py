"""
Notebook: .nblr file format - JSON-based notebook storage.
"""

import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from notebook_lr.kernel import ExecutionResult


class CellType(str, Enum):
    """Type of notebook cell."""
    CODE = "code"
    MARKDOWN = "markdown"


class Comment(BaseModel):
    """An inline code comment with optional AI response."""
    id: str = Field(default_factory=lambda: f"cmt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    from_line: int
    from_ch: int
    to_line: int
    to_ch: int
    selected_text: str
    user_comment: str
    ai_response: str = ""
    status: str = "pending"  # pending | loading | resolved | error
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Cell(BaseModel):
    """A single notebook cell."""
    id: str = Field(default_factory=lambda: f"cell_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    type: CellType = CellType.CODE
    source: str = ""
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    execution_count: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    comments: list[Comment] = Field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source,
            "outputs": self.outputs,
            "execution_count": self.execution_count,
            "metadata": self.metadata,
            "comments": [c.model_dump() for c in self.comments],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Cell":
        """Create from dictionary."""
        return cls(
            id=data.get("id", f"cell_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"),
            type=CellType(data.get("type", "code")),
            source=data.get("source", ""),
            outputs=data.get("outputs", []),
            execution_count=data.get("execution_count"),
            metadata=data.get("metadata", {}),
            comments=[Comment(**c) for c in data.get("comments", [])],
        )


class Notebook(BaseModel):
    """
    .nblr file format - JSON-based notebook storage.

    A notebook contains:
    - Cells (code and markdown)
    - Metadata (name, created, modified, etc.)
    - Optional session state for persistence
    """

    version: str = "1.0"
    cells: list[Cell] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    session_state: Optional[dict[str, Any]] = None

    def __init__(self, **data):
        super().__init__(**data)
        # Set default metadata
        if not self.metadata:
            self.metadata = {
                "name": "Untitled",
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat(),
            }

    def add_cell(self, cell: Optional[Cell] = None, **kwargs) -> Cell:
        """
        Add a new cell to the notebook.

        Args:
            cell: Cell to add, or create new one
            **kwargs: Arguments for new cell if cell not provided

        Returns:
            The added cell
        """
        if cell is None:
            cell = Cell(**kwargs)
        self.cells.append(cell)
        self._touch()
        return cell

    def insert_cell(self, index: int, cell: Optional[Cell] = None, **kwargs) -> Cell:
        """Insert a cell at a specific index."""
        if cell is None:
            cell = Cell(**kwargs)
        self.cells.insert(index, cell)
        self._touch()
        return cell

    def remove_cell(self, index: int) -> Cell:
        """Remove a cell by index."""
        cell = self.cells.pop(index)
        self._touch()
        return cell

    def get_cell(self, index: int) -> Cell:
        """Get a cell by index."""
        return self.cells[index]

    def update_cell(self, index: int, **kwargs):
        """Update a cell's attributes."""
        cell = self.cells[index]
        for key, value in kwargs.items():
            if hasattr(cell, key):
                setattr(cell, key, value)
        self._touch()

    def _touch(self):
        """Update the modified timestamp."""
        self.metadata["modified"] = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "cells": [cell.to_dict() for cell in self.cells],
            "metadata": self.metadata,
            "session_state": self.session_state,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Notebook":
        """Create from dictionary."""
        cells = [Cell.from_dict(c) for c in data.get("cells", [])]
        return cls(
            version=data.get("version", "1.0"),
            cells=cells,
            metadata=data.get("metadata", {}),
            session_state=data.get("session_state"),
        )

    def save(self, path: Path, include_session: bool = False, session_data: Optional[dict] = None):
        """
        Save notebook to .nblr file.

        Args:
            path: Path to save to
            include_session: Whether to include session state
            session_data: Session state data to include
        """
        if include_session and session_data:
            self.session_state = session_data
        else:
            self.session_state = None

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "Notebook":
        """
        Load notebook from .nblr file.

        Args:
            path: Path to load from

        Returns:
            Loaded notebook
        """
        path = Path(path)
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def new(cls, name: str = "Untitled") -> "Notebook":
        """Create a new empty notebook."""
        return cls(
            metadata={
                "name": name,
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat(),
            }
        )
