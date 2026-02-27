"""
TDD RED Phase: Failing tests for Cell Management MCP tools.

These tests import from notebook_lr.mcp_server which doesn't exist yet.
The tests define the expected API for cell management operations:
- add_cell
- delete_cell
- move_cell
- get_cell
- list_cells

All tests should FAIL until the MCP server is implemented.
"""

import pytest
from pydantic import ValidationError

# Import MCP tools - these will fail because the module doesn't exist yet
from notebook_lr.mcp_server import (
    add_cell,
    delete_cell,
    move_cell,
    get_cell,
    list_cells,
    CellOutput,
    CellList,
)


class TestAddCell:
    """Tests for add_cell tool."""

    def test_add_cell_default_code_type(self):
        """Test adding a new code cell with default parameters."""
        # Add a cell with defaults
        result = add_cell()

        # Should return CellOutput with the new cell's info
        assert isinstance(result, CellOutput)
        assert result.type == "code"
        assert result.source == ""
        assert result.index == 0  # First cell should be at index 0
        assert result.id is not None
        assert len(result.id) > 0

    def test_add_cell_markdown_type(self):
        """Test adding a markdown cell."""
        result = add_cell(cell_type="markdown", source="# Hello")

        assert isinstance(result, CellOutput)
        assert result.type == "markdown"
        assert result.source == "# Hello"

    def test_add_cell_with_source(self):
        """Test adding a cell with initial source content."""
        result = add_cell(cell_type="code", source="print('hello')")

        assert isinstance(result, CellOutput)
        assert result.source == "print('hello')"

    def test_add_cell_after_index(self):
        """Test adding a cell after a specific index."""
        # First add a cell
        first = add_cell(source="first")
        assert first.index == 0

        # Add another after index 0
        second = add_cell(after_index=0, source="second")
        assert second.index == 1
        assert second.source == "second"

    def test_add_cell_appends_to_end_when_no_after_index(self):
        """Test that cells are appended when after_index is not specified."""
        cell1 = add_cell(source="cell1")
        cell2 = add_cell(source="cell2")
        cell3 = add_cell(source="cell3")

        assert cell1.index == 0
        assert cell2.index == 1
        assert cell3.index == 2

    def test_add_cell_invalid_type_raises_error(self):
        """Test that invalid cell type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cell type"):
            add_cell(cell_type="invalid")


class TestDeleteCell:
    """Tests for delete_cell tool."""

    def test_delete_cell(self):
        """Test deleting a cell by index."""
        # Add a few cells
        add_cell(source="first")
        add_cell(source="second")
        add_cell(source="third")

        # Delete the middle cell
        result = delete_cell(index=1)

        assert result is True

        # Verify the cell was deleted
        cells = list_cells()
        assert len(cells.cells) == 2
        assert [c.source for c in cells.cells] == ["first", "third"]

    def test_delete_cell_invalid_index_raises_error(self):
        """Test deleting with invalid index raises ValueError."""
        with pytest.raises(ValueError, match="out of range|index"):
            delete_cell(index=999)

    def test_delete_last_cell(self):
        """Test deleting the last cell."""
        add_cell(source="only")
        result = delete_cell(index=0)

        assert result is True

        cells = list_cells()
        assert len(cells.cells) == 0


class TestMoveCell:
    """Tests for move_cell tool."""

    def test_move_cell_up(self):
        """Test moving a cell up."""
        add_cell(source="first")
        add_cell(source="second")

        result = move_cell(index=1, direction="up")

        assert result["ok"] is True
        assert result["new_index"] == 0

        # Verify the move
        cells = list_cells()
        assert cells.cells[0].source == "second"
        assert cells.cells[1].source == "first"

    def test_move_cell_down(self):
        """Test moving a cell down."""
        add_cell(source="first")
        add_cell(source="second")

        result = move_cell(index=0, direction="down")

        assert result["ok"] is True
        assert result["new_index"] == 1

        # Verify the move
        cells = list_cells()
        assert cells.cells[0].source == "second"
        assert cells.cells[1].source == "first"

    def test_move_cell_up_at_boundary_raises_error(self):
        """Test moving first cell up raises ValueError."""
        add_cell(source="first")

        with pytest.raises(ValueError, match="Cannot move"):
            move_cell(index=0, direction="up")

    def test_move_cell_down_at_boundary_raises_error(self):
        """Test moving last cell down raises ValueError."""
        add_cell(source="only")

        with pytest.raises(ValueError, match="Cannot move"):
            move_cell(index=0, direction="down")

    def test_move_cell_invalid_direction_raises_error(self):
        """Test invalid direction raises ValueError."""
        add_cell(source="cell")

        with pytest.raises(ValueError, match="direction"):
            move_cell(index=0, direction="sideways")


class TestGetCell:
    """Tests for get_cell tool."""

    def test_get_cell(self):
        """Test getting a cell by index."""
        add_cell(source="my code", cell_type="code")
        # Execute the cell to set execution_count
        # (This would require execute_cell tool, skip for now)

        result = get_cell(index=0)

        assert isinstance(result, CellOutput)
        assert result.index == 0
        assert result.source == "my code"
        assert result.type == "code"
        assert result.id is not None
        assert isinstance(result.outputs, list)

    def test_get_cell_invalid_index_raises_error(self):
        """Test getting with invalid index raises ValueError."""
        with pytest.raises(ValueError, match="out of range|index"):
            get_cell(index=999)


class TestListCells:
    """Tests for list_cells tool."""

    def test_list_cells_empty_notebook(self):
        """Test listing cells when notebook is empty."""
        result = list_cells()

        assert isinstance(result, CellList)
        assert len(result.cells) == 0

    def test_list_cells_multiple_cells(self):
        """Test listing all cells."""
        add_cell(source="first", cell_type="code")
        add_cell(source="# header", cell_type="markdown")
        add_cell(source="third", cell_type="code")

        result = list_cells()

        assert isinstance(result, CellList)
        assert len(result.cells) == 3

        # Check cell properties
        assert result.cells[0].source == "first"
        assert result.cells[0].type == "code"
        assert result.cells[0].index == 0

        assert result.cells[1].source == "# header"
        assert result.cells[1].type == "markdown"
        assert result.cells[1].index == 1

        assert result.cells[2].source == "third"
        assert result.cells[2].type == "code"
        assert result.cells[2].index == 2

    def test_list_cells_includes_all_fields(self):
        """Test that listed cells include all expected fields."""
        add_cell(source="test")

        result = list_cells()
        cell = result.cells[0]

        # Check all CellOutput fields are present
        assert hasattr(cell, "index")
        assert hasattr(cell, "id")
        assert hasattr(cell, "type")
        assert hasattr(cell, "source")
        assert hasattr(cell, "outputs")
        assert hasattr(cell, "execution_count")
