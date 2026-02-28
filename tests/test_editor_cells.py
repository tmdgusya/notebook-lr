"""
Tests for NotebookEditor cell management methods.

Covers: add_cell_after, add_cell_before, undo_delete, move_cell_up,
move_cell_down, duplicate_cell, toggle_cell_type, clear_outputs, _set_message.
"""

import pytest
from notebook_lr.cli import NotebookEditor
from notebook_lr import Notebook, Cell, CellType, NotebookKernel


@pytest.fixture
def editor():
    """Create a NotebookEditor with three cells for testing."""
    nb = Notebook.new()
    nb.add_cell(type=CellType.CODE, source="x = 1")
    nb.add_cell(type=CellType.CODE, source="y = 2")
    nb.add_cell(type=CellType.MARKDOWN, source="# Title")
    return NotebookEditor(nb)


@pytest.fixture
def empty_editor():
    """Create a NotebookEditor with an empty notebook."""
    nb = Notebook.new()
    return NotebookEditor(nb)


# ---------------------------------------------------------------------------
# add_cell_after
# ---------------------------------------------------------------------------

class TestAddCellAfter:

    def test_adds_cell_after_current(self, editor):
        """add_cell_after inserts a cell after current_cell_index."""
        editor.current_cell_index = 0
        initial_count = len(editor.notebook.cells)
        editor.add_cell_after()
        assert len(editor.notebook.cells) == initial_count + 1
        # New cell is at index 1 (after index 0)
        assert editor.notebook.cells[1].source == ""
        assert editor.notebook.cells[1].type == CellType.CODE

    def test_increments_current_cell_index(self, editor):
        """add_cell_after sets current_cell_index to the new cell's index."""
        editor.current_cell_index = 0
        editor.add_cell_after()
        assert editor.current_cell_index == 1

    def test_sets_modified(self, editor):
        """add_cell_after sets modified=True."""
        editor.modified = False
        editor.add_cell_after()
        assert editor.modified is True

    def test_new_cell_is_code_with_empty_source(self, editor):
        """The new cell has CODE type and empty source."""
        editor.current_cell_index = 0
        editor.add_cell_after()
        new_cell = editor.notebook.cells[editor.current_cell_index]
        assert new_cell.type == CellType.CODE
        assert new_cell.source == ""

    def test_on_empty_notebook_adds_at_index_0(self, empty_editor):
        """add_cell_after on empty notebook inserts at index 0."""
        empty_editor.add_cell_after()
        assert len(empty_editor.notebook.cells) == 1
        assert empty_editor.current_cell_index == 0

    def test_add_after_last_cell(self, editor):
        """add_cell_after on the last cell appends at the end."""
        last_idx = len(editor.notebook.cells) - 1
        editor.current_cell_index = last_idx
        editor.add_cell_after()
        assert editor.current_cell_index == last_idx + 1
        assert len(editor.notebook.cells) == last_idx + 2


# ---------------------------------------------------------------------------
# add_cell_before
# ---------------------------------------------------------------------------

class TestAddCellBefore:

    def test_adds_cell_before_current(self, editor):
        """add_cell_before inserts a cell at the current index."""
        editor.current_cell_index = 1
        original_source_at_1 = editor.notebook.cells[1].source
        initial_count = len(editor.notebook.cells)
        editor.add_cell_before()
        assert len(editor.notebook.cells) == initial_count + 1
        # The new cell is now at index 1; old cell[1] shifted to index 2
        assert editor.notebook.cells[1].source == ""
        assert editor.notebook.cells[2].source == original_source_at_1

    def test_sets_modified(self, editor):
        """add_cell_before sets modified=True."""
        editor.modified = False
        editor.add_cell_before()
        assert editor.modified is True

    def test_current_cell_index_points_to_new_cell(self, editor):
        """After add_cell_before, current_cell_index is unchanged (points to new cell)."""
        editor.current_cell_index = 1
        editor.add_cell_before()
        # current_cell_index stays at 1 (the new cell)
        assert editor.current_cell_index == 1
        assert editor.notebook.cells[1].source == ""

    def test_on_empty_notebook_adds_at_index_0(self, empty_editor):
        """add_cell_before on empty notebook inserts at index 0."""
        empty_editor.add_cell_before()
        assert len(empty_editor.notebook.cells) == 1
        assert empty_editor.current_cell_index == 0

    def test_new_cell_is_code_type(self, editor):
        """New cell inserted by add_cell_before is CODE type."""
        editor.current_cell_index = 0
        editor.add_cell_before()
        assert editor.notebook.cells[0].type == CellType.CODE


# ---------------------------------------------------------------------------
# undo_delete
# ---------------------------------------------------------------------------

class TestUndoDelete:

    def test_undo_restores_deleted_cell(self, editor):
        """undo_delete restores a cell that was manually added to _deleted_cells."""
        cell = editor.notebook.cells[1]
        editor.notebook.cells.pop(1)
        editor._deleted_cells.append((1, cell))
        initial_count = len(editor.notebook.cells)
        editor.undo_delete()
        assert len(editor.notebook.cells) == initial_count + 1
        assert editor.notebook.cells[1].source == cell.source

    def test_undo_with_nothing_sets_message(self, editor):
        """undo_delete with empty _deleted_cells sets a status message."""
        editor._deleted_cells.clear()
        editor.undo_delete()
        assert editor._status_message != ""

    def test_undo_sets_current_cell_index(self, editor):
        """undo_delete sets current_cell_index to the restored cell's index."""
        cell = editor.notebook.cells[0]
        editor.notebook.cells.pop(0)
        editor._deleted_cells.append((0, cell))
        editor.undo_delete()
        assert editor.current_cell_index == 0

    def test_undo_sets_modified(self, editor):
        """undo_delete sets modified=True."""
        cell = editor.notebook.cells[0]
        editor.notebook.cells.pop(0)
        editor._deleted_cells.append((0, cell))
        editor.modified = False
        editor.undo_delete()
        assert editor.modified is True

    def test_multiple_undo_lifo_order(self, editor):
        """Multiple undo operations restore cells in LIFO order."""
        cell0 = editor.notebook.cells[0]
        cell1 = editor.notebook.cells[1]
        # Simulate deleting cell0 then cell1
        editor.notebook.cells.pop(0)
        editor._deleted_cells.append((0, cell0))
        editor.notebook.cells.pop(0)
        editor._deleted_cells.append((0, cell1))

        # First undo restores cell1
        editor.undo_delete()
        assert editor.notebook.cells[0].source == cell1.source

        # Second undo restores cell0
        editor.undo_delete()
        assert editor.notebook.cells[0].source == cell0.source


# ---------------------------------------------------------------------------
# move_cell_up
# ---------------------------------------------------------------------------

class TestMoveCellUp:

    def test_moves_current_cell_up(self, editor):
        """move_cell_up swaps cell with the one above it."""
        editor.current_cell_index = 1
        source_at_0 = editor.notebook.cells[0].source
        source_at_1 = editor.notebook.cells[1].source
        editor.move_cell_up()
        assert editor.notebook.cells[0].source == source_at_1
        assert editor.notebook.cells[1].source == source_at_0

    def test_decrements_current_cell_index(self, editor):
        """move_cell_up decrements current_cell_index by 1."""
        editor.current_cell_index = 2
        editor.move_cell_up()
        assert editor.current_cell_index == 1

    def test_at_index_0_sets_cannot_move_message(self, editor):
        """move_cell_up at index 0 sets a 'cannot move' message."""
        editor.current_cell_index = 0
        editor.move_cell_up()
        assert editor._status_message != ""

    def test_at_index_0_does_not_change_order(self, editor):
        """move_cell_up at index 0 leaves cells unchanged."""
        sources = [c.source for c in editor.notebook.cells]
        editor.current_cell_index = 0
        editor.move_cell_up()
        assert [c.source for c in editor.notebook.cells] == sources

    def test_empty_notebook_sets_message(self, empty_editor):
        """move_cell_up on empty notebook sets a status message."""
        empty_editor.move_cell_up()
        assert empty_editor._status_message != ""

    def test_sets_modified(self, editor):
        """move_cell_up sets modified=True when successful."""
        editor.current_cell_index = 1
        editor.modified = False
        editor.move_cell_up()
        assert editor.modified is True


# ---------------------------------------------------------------------------
# move_cell_down
# ---------------------------------------------------------------------------

class TestMoveCellDown:

    def test_moves_current_cell_down(self, editor):
        """move_cell_down swaps cell with the one below it."""
        editor.current_cell_index = 0
        source_at_0 = editor.notebook.cells[0].source
        source_at_1 = editor.notebook.cells[1].source
        editor.move_cell_down()
        assert editor.notebook.cells[0].source == source_at_1
        assert editor.notebook.cells[1].source == source_at_0

    def test_increments_current_cell_index(self, editor):
        """move_cell_down increments current_cell_index by 1."""
        editor.current_cell_index = 0
        editor.move_cell_down()
        assert editor.current_cell_index == 1

    def test_at_last_index_sets_cannot_move_message(self, editor):
        """move_cell_down at last index sets a 'cannot move' message."""
        last = len(editor.notebook.cells) - 1
        editor.current_cell_index = last
        editor.move_cell_down()
        assert editor._status_message != ""

    def test_at_last_index_does_not_change_order(self, editor):
        """move_cell_down at last index leaves cells unchanged."""
        last = len(editor.notebook.cells) - 1
        editor.current_cell_index = last
        sources = [c.source for c in editor.notebook.cells]
        editor.move_cell_down()
        assert [c.source for c in editor.notebook.cells] == sources

    def test_sets_modified(self, editor):
        """move_cell_down sets modified=True when successful."""
        editor.current_cell_index = 0
        editor.modified = False
        editor.move_cell_down()
        assert editor.modified is True


# ---------------------------------------------------------------------------
# duplicate_cell
# ---------------------------------------------------------------------------

class TestDuplicateCell:

    def test_creates_copy_after_current(self, editor):
        """duplicate_cell inserts a copy of the current cell right after it."""
        editor.current_cell_index = 0
        original_source = editor.notebook.cells[0].source
        initial_count = len(editor.notebook.cells)
        editor.duplicate_cell()
        assert len(editor.notebook.cells) == initial_count + 1
        assert editor.notebook.cells[1].source == original_source

    def test_new_cell_has_different_id(self, editor):
        """The duplicated cell has a different id than the original."""
        editor.current_cell_index = 0
        original_id = editor.notebook.cells[0].id
        editor.duplicate_cell()
        new_cell = editor.notebook.cells[editor.current_cell_index]
        assert new_cell.id != original_id

    def test_new_cell_has_same_source_and_type(self, editor):
        """The duplicated cell has the same source and type as the original."""
        editor.current_cell_index = 2  # MARKDOWN cell
        original = editor.notebook.cells[2]
        editor.duplicate_cell()
        new_cell = editor.notebook.cells[editor.current_cell_index]
        assert new_cell.source == original.source
        assert new_cell.type == original.type

    def test_sets_modified(self, editor):
        """duplicate_cell sets modified=True."""
        editor.current_cell_index = 0
        editor.modified = False
        editor.duplicate_cell()
        assert editor.modified is True

    def test_current_cell_index_moves_to_duplicate(self, editor):
        """After duplicating, current_cell_index points to the new cell."""
        editor.current_cell_index = 0
        editor.duplicate_cell()
        assert editor.current_cell_index == 1

    def test_empty_notebook_sets_message(self, empty_editor):
        """duplicate_cell on empty notebook sets a status message."""
        empty_editor.duplicate_cell()
        assert empty_editor._status_message != ""


# ---------------------------------------------------------------------------
# toggle_cell_type
# ---------------------------------------------------------------------------

class TestToggleCellType:

    def test_code_to_markdown(self, editor):
        """toggle_cell_type changes CODE cell to MARKDOWN."""
        editor.current_cell_index = 0
        assert editor.notebook.cells[0].type == CellType.CODE
        editor.toggle_cell_type()
        assert editor.notebook.cells[0].type == CellType.MARKDOWN

    def test_markdown_to_code(self, editor):
        """toggle_cell_type changes MARKDOWN cell to CODE."""
        editor.current_cell_index = 2
        assert editor.notebook.cells[2].type == CellType.MARKDOWN
        editor.toggle_cell_type()
        assert editor.notebook.cells[2].type == CellType.CODE

    def test_clears_outputs(self, editor):
        """toggle_cell_type clears outputs on the toggled cell."""
        editor.notebook.cells[0].outputs = [{"type": "stream", "text": "hi"}]
        editor.current_cell_index = 0
        editor.toggle_cell_type()
        assert editor.notebook.cells[0].outputs == []

    def test_clears_execution_count(self, editor):
        """toggle_cell_type clears execution_count on the toggled cell."""
        editor.notebook.cells[0].execution_count = 3
        editor.current_cell_index = 0
        editor.toggle_cell_type()
        assert editor.notebook.cells[0].execution_count is None

    def test_sets_modified(self, editor):
        """toggle_cell_type sets modified=True."""
        editor.current_cell_index = 0
        editor.modified = False
        editor.toggle_cell_type()
        assert editor.modified is True

    def test_empty_notebook_sets_message(self, empty_editor):
        """toggle_cell_type on empty notebook sets a status message."""
        empty_editor.toggle_cell_type()
        assert empty_editor._status_message != ""


# ---------------------------------------------------------------------------
# clear_outputs
# ---------------------------------------------------------------------------

class TestClearOutputs:

    def test_clears_all_outputs(self, editor):
        """clear_outputs removes all outputs from all cells."""
        for cell in editor.notebook.cells:
            cell.outputs = [{"type": "stream", "text": "output"}]
        editor.clear_outputs()
        for cell in editor.notebook.cells:
            assert cell.outputs == []

    def test_clears_all_execution_counts(self, editor):
        """clear_outputs sets execution_count to None for all cells."""
        for i, cell in enumerate(editor.notebook.cells):
            cell.execution_count = i + 1
        editor.clear_outputs()
        for cell in editor.notebook.cells:
            assert cell.execution_count is None

    def test_reports_number_of_cleared_cells(self, editor):
        """clear_outputs sets a message reporting how many cells were cleared."""
        editor.notebook.cells[0].outputs = [{"type": "stream", "text": "x"}]
        editor.notebook.cells[0].execution_count = 1
        editor.clear_outputs()
        assert "1" in editor._status_message

    def test_noop_when_no_outputs(self, editor):
        """clear_outputs sets a 'no outputs' message when nothing to clear."""
        for cell in editor.notebook.cells:
            cell.outputs = []
            cell.execution_count = None
        editor.clear_outputs()
        assert editor._status_message != ""
        # Should NOT set modified since nothing was cleared
        assert editor.modified is False

    def test_sets_modified_when_outputs_cleared(self, editor):
        """clear_outputs sets modified=True when at least one cell had output."""
        editor.notebook.cells[0].outputs = [{"type": "stream", "text": "x"}]
        editor.modified = False
        editor.clear_outputs()
        assert editor.modified is True

    def test_clears_multiple_cells(self, editor):
        """clear_outputs clears outputs from all cells with outputs."""
        for cell in editor.notebook.cells:
            cell.outputs = [{"type": "stream", "text": "data"}]
            cell.execution_count = 1
        editor.clear_outputs()
        assert all(c.outputs == [] for c in editor.notebook.cells)
        assert all(c.execution_count is None for c in editor.notebook.cells)


# ---------------------------------------------------------------------------
# _set_message
# ---------------------------------------------------------------------------

class TestSetMessage:

    def test_set_message_stores_value(self, editor):
        """_set_message sets the _status_message field."""
        editor._set_message("hello")
        assert editor._status_message == "hello"

    def test_set_message_overwrites_previous(self, editor):
        """_set_message replaces any previous message."""
        editor._set_message("first")
        editor._set_message("second")
        assert editor._status_message == "second"

    def test_set_message_empty_string(self, editor):
        """_set_message can set an empty string."""
        editor._set_message("something")
        editor._set_message("")
        assert editor._status_message == ""

    def test_set_message_with_rich_markup(self, editor):
        """_set_message stores rich markup strings as-is."""
        msg = "[green]Done[/green]"
        editor._set_message(msg)
        assert editor._status_message == msg
