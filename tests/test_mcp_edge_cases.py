"""
Edge case tests for MCP cell operations in notebook_lr/mcp_server.py.

The conftest.py reset_mcp_state fixture handles state cleanup between tests.
"""

import pytest

from notebook_lr.mcp_server import (
    add_cell,
    delete_cell,
    move_cell,
    get_cell,
    get_cell_source,
    update_cell_source,
    list_cells,
    CellOutput,
    CellList,
)


# ---------------------------------------------------------------------------
# get_cell_source
# ---------------------------------------------------------------------------

class TestGetCellSource:

    def test_valid_index_returns_source(self):
        """Valid index returns the cell's source."""
        add_cell(source="hello world")
        result = get_cell_source(index=0)
        assert result == "hello world"

    def test_invalid_index_raises_value_error(self):
        """Out-of-range index raises ValueError."""
        with pytest.raises(ValueError):
            get_cell_source(index=999)

    def test_source_with_unicode_content(self):
        """Unicode source content is returned verbatim."""
        src = "# Unicode: cafe\nx = 'naif'"
        add_cell(source=src)
        assert get_cell_source(index=0) == src


# ---------------------------------------------------------------------------
# update_cell_source
# ---------------------------------------------------------------------------

class TestUpdateCellSource:

    def test_updates_source_and_returns_true(self):
        """Updates cell source and returns True."""
        add_cell(source="original")
        result = update_cell_source(index=0, source="updated")
        assert result is True
        assert get_cell_source(index=0) == "updated"

    def test_invalid_index_raises_value_error(self):
        """Out-of-range index raises ValueError."""
        with pytest.raises(ValueError):
            update_cell_source(index=999, source="new")

    def test_update_with_empty_string(self):
        """Updating with empty string clears the source."""
        add_cell(source="some content")
        update_cell_source(index=0, source="")
        assert get_cell_source(index=0) == ""

    def test_update_with_multiline_code(self):
        """Multiline source is preserved after update."""
        add_cell(source="single")
        multiline = "def foo():\n    return 42\n\nfoo()"
        update_cell_source(index=0, source=multiline)
        assert get_cell_source(index=0) == multiline


# ---------------------------------------------------------------------------
# add_cell
# ---------------------------------------------------------------------------

class TestAddCell:

    def test_add_code_cell_to_empty_notebook(self):
        """Adding to empty notebook creates cell at index 0."""
        result = add_cell()
        assert isinstance(result, CellOutput)
        assert result.index == 0
        assert result.type == "code"

    def test_add_markdown_cell(self):
        """Adding a markdown cell returns correct type."""
        result = add_cell(cell_type="markdown", source="# Title")
        assert result.type == "markdown"
        assert result.source == "# Title"

    def test_add_after_specific_index(self):
        """after_index places cell immediately after given index."""
        add_cell(source="first")
        add_cell(source="third")
        result = add_cell(after_index=0, source="second")
        assert result.index == 1
        cells = list_cells()
        assert [c.source for c in cells.cells] == ["first", "second", "third"]

    def test_add_after_index_none_appends_to_end(self):
        """after_index=None appends cell to end."""
        add_cell(source="a")
        add_cell(source="b")
        result = add_cell(after_index=None, source="c")
        assert result.index == 2

    def test_invalid_cell_type_raises_value_error(self):
        """Invalid cell_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cell type"):
            add_cell(cell_type="raw")

    def test_code_cell_type_is_valid(self):
        """'code' is a valid cell type."""
        result = add_cell(cell_type="code")
        assert result.type == "code"

    def test_markdown_cell_type_is_valid(self):
        """'markdown' is a valid cell type."""
        result = add_cell(cell_type="markdown")
        assert result.type == "markdown"

    def test_add_with_source_content(self):
        """Source content is stored in the new cell."""
        result = add_cell(source="x = 42")
        assert result.source == "x = 42"


# ---------------------------------------------------------------------------
# delete_cell
# ---------------------------------------------------------------------------

class TestDeleteCell:

    def test_delete_from_middle(self):
        """Deleting middle cell removes it and shifts others."""
        add_cell(source="a")
        add_cell(source="b")
        add_cell(source="c")
        result = delete_cell(index=1)
        assert result is True
        cells = list_cells()
        assert [c.source for c in cells.cells] == ["a", "c"]

    def test_delete_first_cell(self):
        """Deleting first cell shifts remaining cells."""
        add_cell(source="first")
        add_cell(source="second")
        delete_cell(index=0)
        cells = list_cells()
        assert len(cells.cells) == 1
        assert cells.cells[0].source == "second"

    def test_delete_last_cell(self):
        """Deleting last cell leaves preceding cells."""
        add_cell(source="first")
        add_cell(source="last")
        delete_cell(index=1)
        cells = list_cells()
        assert len(cells.cells) == 1
        assert cells.cells[0].source == "first"

    def test_delete_invalid_index_raises_value_error(self):
        """Out-of-range index raises ValueError."""
        add_cell(source="x")
        with pytest.raises(ValueError):
            delete_cell(index=5)


# ---------------------------------------------------------------------------
# move_cell
# ---------------------------------------------------------------------------

class TestMoveCell:

    def test_move_down_from_first_cell(self):
        """Moving first cell down places it at index 1."""
        add_cell(source="first")
        add_cell(source="second")
        result = move_cell(index=0, direction="down")
        assert result["ok"] is True
        assert result["new_index"] == 1
        cells = list_cells()
        assert cells.cells[0].source == "second"
        assert cells.cells[1].source == "first"

    def test_move_up_from_last_cell(self):
        """Moving last cell up places it at second-to-last position."""
        add_cell(source="first")
        add_cell(source="second")
        result = move_cell(index=1, direction="up")
        assert result["ok"] is True
        assert result["new_index"] == 0
        cells = list_cells()
        assert cells.cells[0].source == "second"
        assert cells.cells[1].source == "first"

    def test_move_first_cell_up_raises_value_error(self):
        """Moving cell at index 0 up raises ValueError."""
        add_cell(source="only")
        with pytest.raises(ValueError, match="Cannot move"):
            move_cell(index=0, direction="up")

    def test_move_last_cell_down_raises_value_error(self):
        """Moving last cell down raises ValueError."""
        add_cell(source="a")
        add_cell(source="b")
        with pytest.raises(ValueError, match="Cannot move"):
            move_cell(index=1, direction="down")

    def test_invalid_direction_raises_value_error(self):
        """Invalid direction raises ValueError."""
        add_cell(source="a")
        add_cell(source="b")
        with pytest.raises(ValueError):
            move_cell(index=0, direction="sideways")

    def test_move_returns_new_index_correctly(self):
        """move_cell returns the correct new_index after move."""
        add_cell(source="a")
        add_cell(source="b")
        add_cell(source="c")
        result = move_cell(index=2, direction="up")
        assert result["new_index"] == 1

        result2 = move_cell(index=0, direction="down")
        assert result2["new_index"] == 1


# ---------------------------------------------------------------------------
# get_cell
# ---------------------------------------------------------------------------

class TestGetCell:

    def test_returns_cell_output_with_correct_fields(self):
        """get_cell returns CellOutput with all expected fields."""
        add_cell(cell_type="code", source="x = 1")
        result = get_cell(index=0)
        assert isinstance(result, CellOutput)
        assert result.index == 0
        assert result.type == "code"
        assert result.source == "x = 1"
        assert isinstance(result.id, str) and len(result.id) > 0
        assert isinstance(result.outputs, list)
        assert result.execution_count is None

    def test_invalid_index_raises_value_error(self):
        """Out-of-range index raises ValueError."""
        with pytest.raises(ValueError):
            get_cell(index=0)


# ---------------------------------------------------------------------------
# list_cells
# ---------------------------------------------------------------------------

class TestListCells:

    def test_empty_notebook_returns_empty_list(self):
        """list_cells on empty notebook returns CellList with no cells."""
        result = list_cells()
        assert isinstance(result, CellList)
        assert result.cells == []

    def test_returns_all_cells_with_correct_indices(self):
        """list_cells returns all cells with sequential indices."""
        add_cell(source="first", cell_type="code")
        add_cell(source="second", cell_type="markdown")
        add_cell(source="third", cell_type="code")

        result = list_cells()
        assert len(result.cells) == 3
        assert result.cells[0].index == 0
        assert result.cells[0].source == "first"
        assert result.cells[0].type == "code"
        assert result.cells[1].index == 1
        assert result.cells[1].source == "second"
        assert result.cells[1].type == "markdown"
        assert result.cells[2].index == 2
        assert result.cells[2].source == "third"

    def test_list_reflects_changes_after_add_and_delete(self):
        """list_cells reflects the notebook state after add and delete."""
        add_cell(source="a")
        add_cell(source="b")
        add_cell(source="c")
        delete_cell(index=1)  # remove "b"
        add_cell(source="d")  # append "d"

        result = list_cells()
        sources = [c.source for c in result.cells]
        assert sources == ["a", "c", "d"]
        # Indices should be sequential
        indices = [c.index for c in result.cells]
        assert indices == [0, 1, 2]
