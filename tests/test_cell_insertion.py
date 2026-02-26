"""
Tests for cell insertion behavior (Google Colab style).

Verifies that adding cells inserts them directly after the current cell
and moves the cursor/selection to the new cell.
"""

import pytest

from notebook_lr.notebook import Notebook, Cell, CellType
from notebook_lr.cli import NotebookEditor


class TestNotebookEditorAddCellAfter:
    """Test NotebookEditor.add_cell_after (TUI 'a' key)."""

    def _make_editor(self, sources: list[str]) -> NotebookEditor:
        """Create an editor with cells having the given sources."""
        nb = Notebook.new("Test")
        for src in sources:
            nb.add_cell(type=CellType.CODE, source=src)
        return NotebookEditor(nb)

    def test_add_cell_after_first_cell(self):
        """Adding after cell 0 inserts at index 1."""
        editor = self._make_editor(["cell_A", "cell_B", "cell_C"])
        editor.current_cell_index = 0

        editor.add_cell_after()

        assert len(editor.notebook.cells) == 4
        assert editor.notebook.cells[0].source == "cell_A"
        assert editor.notebook.cells[1].source == ""  # new cell
        assert editor.notebook.cells[2].source == "cell_B"
        assert editor.notebook.cells[3].source == "cell_C"
        assert editor.current_cell_index == 1

    def test_add_cell_after_middle_cell(self):
        """Adding after cell 1 inserts at index 2."""
        editor = self._make_editor(["cell_A", "cell_B", "cell_C"])
        editor.current_cell_index = 1

        editor.add_cell_after()

        assert len(editor.notebook.cells) == 4
        assert editor.notebook.cells[0].source == "cell_A"
        assert editor.notebook.cells[1].source == "cell_B"
        assert editor.notebook.cells[2].source == ""  # new cell
        assert editor.notebook.cells[3].source == "cell_C"
        assert editor.current_cell_index == 2

    def test_add_cell_after_last_cell(self):
        """Adding after the last cell appends to end."""
        editor = self._make_editor(["cell_A", "cell_B", "cell_C"])
        editor.current_cell_index = 2

        editor.add_cell_after()

        assert len(editor.notebook.cells) == 4
        assert editor.notebook.cells[2].source == "cell_C"
        assert editor.notebook.cells[3].source == ""  # new cell at end
        assert editor.current_cell_index == 3

    def test_add_cell_to_empty_notebook(self):
        """Adding to empty notebook creates cell at index 0."""
        editor = self._make_editor([])
        editor.current_cell_index = 0

        editor.add_cell_after()

        assert len(editor.notebook.cells) == 1
        assert editor.notebook.cells[0].source == ""
        assert editor.current_cell_index == 0

    def test_sequential_adds_stack_correctly(self):
        """Adding multiple cells in sequence stacks them below each other."""
        editor = self._make_editor(["cell_A", "cell_B"])
        editor.current_cell_index = 0

        # First add: insert after cell_A
        editor.add_cell_after()
        assert editor.current_cell_index == 1
        editor.notebook.cells[1].source = "new_1"

        # Second add: insert after new_1 (cursor is now at 1)
        editor.add_cell_after()
        assert editor.current_cell_index == 2
        editor.notebook.cells[2].source = "new_2"

        # Third add: insert after new_2 (cursor is now at 2)
        editor.add_cell_after()
        assert editor.current_cell_index == 3
        editor.notebook.cells[3].source = "new_3"

        # Verify order: cell_A, new_1, new_2, new_3, cell_B
        assert len(editor.notebook.cells) == 5
        assert editor.notebook.cells[0].source == "cell_A"
        assert editor.notebook.cells[1].source == "new_1"
        assert editor.notebook.cells[2].source == "new_2"
        assert editor.notebook.cells[3].source == "new_3"
        assert editor.notebook.cells[4].source == "cell_B"

    def test_add_cell_sets_modified_flag(self):
        """Adding a cell marks the notebook as modified."""
        editor = self._make_editor(["cell_A"])
        assert not editor.modified

        editor.add_cell_after()

        assert editor.modified

    def test_add_cell_creates_code_cell(self):
        """New cells are code cells by default."""
        editor = self._make_editor(["cell_A"])
        editor.current_cell_index = 0

        editor.add_cell_after()

        new_cell = editor.notebook.cells[1]
        assert new_cell.type == CellType.CODE

    def test_add_cell_creates_empty_source(self):
        """New cells have empty source."""
        editor = self._make_editor(["cell_A"])
        editor.current_cell_index = 0

        editor.add_cell_after()

        new_cell = editor.notebook.cells[1]
        assert new_cell.source == ""
        assert new_cell.outputs == []
        assert new_cell.execution_count is None


class TestNotebookEditorAddCellBefore:
    """Test NotebookEditor.add_cell_before (TUI 'b' key)."""

    def _make_editor(self, sources: list[str]) -> NotebookEditor:
        nb = Notebook.new("Test")
        for src in sources:
            nb.add_cell(type=CellType.CODE, source=src)
        return NotebookEditor(nb)

    def test_add_cell_before_first_cell(self):
        """Adding before cell 0 inserts at index 0."""
        editor = self._make_editor(["cell_A", "cell_B"])
        editor.current_cell_index = 0

        editor.add_cell_before()

        assert len(editor.notebook.cells) == 3
        assert editor.notebook.cells[0].source == ""  # new cell
        assert editor.notebook.cells[1].source == "cell_A"
        assert editor.notebook.cells[2].source == "cell_B"
        # Cursor stays at position 0 (the new cell)
        assert editor.current_cell_index == 0

    def test_add_cell_before_middle_cell(self):
        """Adding before cell 1 inserts at index 1."""
        editor = self._make_editor(["cell_A", "cell_B", "cell_C"])
        editor.current_cell_index = 1

        editor.add_cell_before()

        assert len(editor.notebook.cells) == 4
        assert editor.notebook.cells[0].source == "cell_A"
        assert editor.notebook.cells[1].source == ""  # new cell
        assert editor.notebook.cells[2].source == "cell_B"
        assert editor.notebook.cells[3].source == "cell_C"
        assert editor.current_cell_index == 1

    def test_add_cell_before_last_cell(self):
        """Adding before the last cell inserts just before it."""
        editor = self._make_editor(["cell_A", "cell_B", "cell_C"])
        editor.current_cell_index = 2

        editor.add_cell_before()

        assert len(editor.notebook.cells) == 4
        assert editor.notebook.cells[1].source == "cell_B"
        assert editor.notebook.cells[2].source == ""  # new cell
        assert editor.notebook.cells[3].source == "cell_C"
        assert editor.current_cell_index == 2


class TestNotebookEditorCellOrderPreservation:
    """Test that cell execution order is preserved after insertions."""

    def _make_editor(self, sources: list[str]) -> NotebookEditor:
        nb = Notebook.new("Test")
        for i, src in enumerate(sources):
            cell = nb.add_cell(type=CellType.CODE, source=src)
            cell.execution_count = i + 1
        return NotebookEditor(nb)

    def test_execution_counts_preserved_after_add(self):
        """Existing cells retain their execution counts after insertion."""
        editor = self._make_editor(["a = 1", "b = 2", "c = 3"])
        editor.current_cell_index = 1

        editor.add_cell_after()

        assert editor.notebook.cells[0].execution_count == 1
        assert editor.notebook.cells[1].execution_count == 2
        assert editor.notebook.cells[2].execution_count is None  # new cell
        assert editor.notebook.cells[3].execution_count == 3

    def test_cell_sources_preserved_after_multiple_adds(self):
        """Cell sources stay in correct order after multiple insertions."""
        editor = self._make_editor(["first", "last"])
        editor.current_cell_index = 0

        editor.add_cell_after()
        editor.notebook.cells[editor.current_cell_index].source = "second"

        editor.add_cell_after()
        editor.notebook.cells[editor.current_cell_index].source = "third"

        sources = [c.source for c in editor.notebook.cells]
        assert sources == ["first", "second", "third", "last"]


class TestWebAddCell:
    """Test that web.py add_cell inserts after the selected cell."""

    def test_add_after_selected_cell(self):
        """Web add_cell inserts after the dropdown-selected cell."""
        nb = Notebook.new("Test")
        nb.add_cell(type=CellType.CODE, source="cell_A")
        nb.add_cell(type=CellType.CODE, source="cell_B")
        nb.add_cell(type=CellType.CODE, source="cell_C")

        # Simulate what web.py add_cell does: parse index, insert at idx+1
        cell_index_str = "1: Code [ ] | cell_B"
        idx = int(cell_index_str.split(":")[0])
        new_idx = idx + 1

        new_cell = Cell(type=CellType.CODE, source="")
        nb.insert_cell(new_idx, new_cell)

        assert len(nb.cells) == 4
        assert nb.cells[0].source == "cell_A"
        assert nb.cells[1].source == "cell_B"
        assert nb.cells[2].source == ""  # new cell inserted after cell_B
        assert nb.cells[3].source == "cell_C"

    def test_add_after_first_cell(self):
        """Web add_cell with first cell selected inserts at index 1."""
        nb = Notebook.new("Test")
        nb.add_cell(type=CellType.CODE, source="cell_A")
        nb.add_cell(type=CellType.CODE, source="cell_B")

        cell_index_str = "0: Code [ ] | cell_A"
        idx = int(cell_index_str.split(":")[0])
        new_idx = idx + 1

        nb.insert_cell(new_idx, Cell(type=CellType.CODE, source=""))

        assert len(nb.cells) == 3
        assert nb.cells[0].source == "cell_A"
        assert nb.cells[1].source == ""  # new cell
        assert nb.cells[2].source == "cell_B"

    def test_add_after_last_cell(self):
        """Web add_cell with last cell selected appends at end."""
        nb = Notebook.new("Test")
        nb.add_cell(type=CellType.CODE, source="cell_A")
        nb.add_cell(type=CellType.CODE, source="cell_B")

        cell_index_str = "1: Code [ ] | cell_B"
        idx = int(cell_index_str.split(":")[0])
        new_idx = idx + 1

        nb.insert_cell(new_idx, Cell(type=CellType.CODE, source=""))

        assert len(nb.cells) == 3
        assert nb.cells[1].source == "cell_B"
        assert nb.cells[2].source == ""  # new cell at end

    def test_add_with_no_selection_appends(self):
        """Web add_cell with no selection (None) appends to end."""
        nb = Notebook.new("Test")
        nb.add_cell(type=CellType.CODE, source="cell_A")

        cell_index_str = None
        new_idx = len(nb.cells)  # default: end
        try:
            idx = int(cell_index_str.split(":")[0])
            new_idx = idx + 1
        except (ValueError, IndexError, TypeError, AttributeError):
            pass

        nb.insert_cell(new_idx, Cell(type=CellType.CODE, source=""))

        assert len(nb.cells) == 2
        assert nb.cells[0].source == "cell_A"
        assert nb.cells[1].source == ""  # appended at end
