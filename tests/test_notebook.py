"""
Tests for Notebook and Cell classes.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from notebook_lr.notebook import Notebook, Cell, CellType


class TestCell:
    """Test cases for Cell."""

    def test_create_code_cell(self):
        """Test creating a code cell."""
        cell = Cell(type=CellType.CODE, source="x = 42")

        assert cell.type == CellType.CODE
        assert cell.source == "x = 42"
        assert cell.outputs == []

    def test_create_markdown_cell(self):
        """Test creating a markdown cell."""
        cell = Cell(type=CellType.MARKDOWN, source="# Hello")

        assert cell.type == CellType.MARKDOWN
        assert cell.source == "# Hello"

    def test_cell_to_dict(self):
        """Test converting cell to dictionary."""
        cell = Cell(
            type=CellType.CODE,
            source="print('hello')",
            outputs=[{"type": "stream", "text": "hello\n"}],
            execution_count=1,
        )

        d = cell.to_dict()

        assert d["type"] == "code"
        assert d["source"] == "print('hello')"
        assert len(d["outputs"]) == 1
        assert d["execution_count"] == 1

    def test_cell_from_dict(self):
        """Test creating cell from dictionary."""
        d = {
            "id": "test_cell",
            "type": "code",
            "source": "x = 1",
            "outputs": [],
            "execution_count": None,
            "metadata": {},
        }

        cell = Cell.from_dict(d)

        assert cell.id == "test_cell"
        assert cell.type == CellType.CODE
        assert cell.source == "x = 1"

    def test_default_values(self):
        """Test default values for cell."""
        cell = Cell()

        assert cell.type == CellType.CODE
        assert cell.source == ""
        assert cell.outputs == []
        assert cell.metadata == {}


class TestNotebook:
    """Test cases for Notebook."""

    def test_create_empty_notebook(self):
        """Test creating an empty notebook."""
        nb = Notebook()

        assert nb.cells == []
        assert nb.version == "1.0"
        assert "name" in nb.metadata

    def test_create_notebook_with_name(self):
        """Test creating notebook with name."""
        nb = Notebook.new("My Notebook")

        assert nb.metadata["name"] == "My Notebook"

    def test_add_cell(self):
        """Test adding cells."""
        nb = Notebook()

        cell1 = nb.add_cell(type=CellType.CODE, source="x = 1")
        cell2 = nb.add_cell(type=CellType.MARKDOWN, source="# Title")

        assert len(nb.cells) == 2
        assert nb.cells[0] == cell1
        assert nb.cells[1] == cell2

    def test_insert_cell(self):
        """Test inserting cells at specific position."""
        nb = Notebook()
        nb.add_cell(source="first")
        nb.add_cell(source="third")

        nb.insert_cell(1, source="second")

        assert len(nb.cells) == 3
        assert nb.cells[0].source == "first"
        assert nb.cells[1].source == "second"
        assert nb.cells[2].source == "third"

    def test_remove_cell(self):
        """Test removing cells."""
        nb = Notebook()
        nb.add_cell(source="keep")
        nb.add_cell(source="remove")
        nb.add_cell(source="keep2")

        removed = nb.remove_cell(1)

        assert removed.source == "remove"
        assert len(nb.cells) == 2
        assert nb.cells[1].source == "keep2"

    def test_get_cell(self):
        """Test getting cell by index."""
        nb = Notebook()
        nb.add_cell(source="first")
        nb.add_cell(source="second")

        cell = nb.get_cell(1)

        assert cell.source == "second"

    def test_update_cell(self):
        """Test updating cell attributes."""
        nb = Notebook()
        nb.add_cell(source="original")

        nb.update_cell(0, source="updated", execution_count=1)

        assert nb.cells[0].source == "updated"
        assert nb.cells[0].execution_count == 1

    def test_to_dict(self):
        """Test converting notebook to dictionary."""
        nb = Notebook.new("Test")
        nb.add_cell(source="x = 1")

        d = nb.to_dict()

        assert d["version"] == "1.0"
        assert d["metadata"]["name"] == "Test"
        assert len(d["cells"]) == 1

    def test_from_dict(self):
        """Test creating notebook from dictionary."""
        d = {
            "version": "1.0",
            "cells": [
                {"type": "code", "source": "x = 1", "outputs": [], "execution_count": None, "metadata": {}}
            ],
            "metadata": {"name": "Test"},
            "session_state": None,
        }

        nb = Notebook.from_dict(d)

        assert nb.version == "1.0"
        assert nb.metadata["name"] == "Test"
        assert len(nb.cells) == 1

    def test_save_and_load(self):
        """Test saving and loading notebook."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.nblr"

            nb = Notebook.new("Test Notebook")
            nb.add_cell(source="x = 42")
            nb.add_cell(type=CellType.MARKDOWN, source="# Title")
            nb.save(path)

            # Load the notebook
            loaded = Notebook.load(path)

            assert loaded.metadata["name"] == "Test Notebook"
            assert len(loaded.cells) == 2
            assert loaded.cells[0].source == "x = 42"
            assert loaded.cells[1].type == CellType.MARKDOWN

    def test_save_with_session(self):
        """Test saving notebook with session state."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_session.nblr"

            nb = Notebook.new("Test")
            session_data = {"user_ns": {"x": 42}, "execution_count": 1}
            nb.save(path, include_session=True, session_data=session_data)

            loaded = Notebook.load(path)

            assert loaded.session_state is not None
            assert loaded.session_state["user_ns"]["x"] == 42

    def test_modified_timestamp_updates(self):
        """Test that modified timestamp updates on changes."""
        nb = Notebook()
        initial_modified = nb.metadata["modified"]

        # Add cell should update modified
        nb.add_cell(source="test")

        assert nb.metadata["modified"] >= initial_modified


class TestNotebookFormat:
    """Test the .nblr file format."""

    def test_file_format_valid_json(self):
        """Test that saved file is valid JSON."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.nblr"

            nb = Notebook.new("Format Test")
            nb.add_cell(source="x = 1")
            nb.save(path)

            with open(path) as f:
                data = json.load(f)

            assert "version" in data
            assert "cells" in data
            assert "metadata" in data

    def test_file_extension(self):
        """Test file extension handling."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_notebook.nblr"

            nb = Notebook()
            nb.save(path)

            assert path.exists()
            assert path.suffix == ".nblr"

    def test_backwards_compatibility(self):
        """Test loading notebooks with missing fields."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "minimal.nblr"

            # Create minimal notebook JSON
            minimal_data = {
                "version": "1.0",
                "cells": [{"type": "code", "source": "x = 1"}],
                "metadata": {},
            }

            with open(path, "w") as f:
                json.dump(minimal_data, f)

            nb = Notebook.load(path)

            assert len(nb.cells) == 1
            assert nb.cells[0].source == "x = 1"
