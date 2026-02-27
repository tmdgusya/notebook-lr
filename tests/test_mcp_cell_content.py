"""
TDD RED Phase: Failing tests for Cell Content MCP tools.

These tests import from notebook_lr.mcp_server which doesn't exist yet.
The tests define the expected API for cell content operations:
- get_cell_source
- update_cell_source

All tests should FAIL until the MCP server is implemented.
"""

import pytest

# Import MCP tools - these will fail because the module doesn't exist yet
from notebook_lr.mcp_server import (
    add_cell,
    get_cell_source,
    update_cell_source,
)


class TestGetCellSource:
    """Tests for get_cell_source tool."""

    def test_get_cell_source_returns_string(self):
        """Test getting cell source returns a string."""
        # Add a cell first
        add_cell(source="print('hello world')")
        add_cell(source="x = 42")

        # Get source of second cell
        result = get_cell_source(index=1)

        assert isinstance(result, str)
        assert result == "x = 42"

    def test_get_cell_source_empty_cell(self):
        """Test getting source from an empty cell."""
        add_cell(source="")

        result = get_cell_source(index=0)

        assert isinstance(result, str)
        assert result == ""

    def test_get_cell_source_multiline_code(self):
        """Test getting source from a cell with multiline code."""
        multiline = """def foo():
    return 'bar'

print(foo())"""

        add_cell(source=multiline)

        result = get_cell_source(index=0)

        assert isinstance(result, str)
        assert result == multiline

    def test_get_cell_source_markdown_cell(self):
        """Test getting source from a markdown cell."""
        add_cell(cell_type="markdown", source="# Header\n\nSome text")

        result = get_cell_source(index=0)

        assert isinstance(result, str)
        assert result == "# Header\n\nSome text"

    def test_get_cell_source_invalid_index_raises_error(self):
        """Test getting source with invalid index raises ValueError."""
        with pytest.raises(ValueError, match="out of range|index"):
            get_cell_source(index=999)

    def test_get_cell_source_negative_index_raises_error(self):
        """Test getting source with negative index raises ValueError."""
        with pytest.raises(ValueError, match="out of range|index"):
            get_cell_source(index=-1)


class TestUpdateCellSource:
    """Tests for update_cell_source tool."""

    def test_update_cell_source(self):
        """Test updating a cell's source content."""
        add_cell(source="original")

        result = update_cell_source(index=0, source="updated")

        assert result is True

        # Verify the update
        content = get_cell_source(index=0)
        assert content == "updated"

    def test_update_cell_source_to_multiline(self):
        """Test updating to multiline source."""
        add_cell(source="single")

        multiline = """line1
line2
line3"""

        result = update_cell_source(index=0, source=multiline)

        assert result is True

        content = get_cell_source(index=0)
        assert content == multiline

    def test_update_cell_source_to_empty_string(self):
        """Test updating a cell to empty source."""
        add_cell(source="has content")

        result = update_cell_source(index=0, source="")

        assert result is True

        content = get_cell_source(index=0)
        assert content == ""

    def test_update_cell_source_invalid_index_raises_error(self):
        """Test updating with invalid index raises ValueError."""
        with pytest.raises(ValueError, match="out of range|index"):
            update_cell_source(index=999, source="new content")

    def test_update_cell_source_preserves_cell_type(self):
        """Test that updating source doesn't change cell type."""
        # This test would need get_cell to verify type
        add_cell(cell_type="markdown", source="# Old")

        update_cell_source(index=0, source="# New")

        # Cell should still be markdown (would need get_cell to verify)
        # For now, just verify source changed
        content = get_cell_source(index=0)
        assert content == "# New"

    def test_update_multiple_cells(self):
        """Test updating multiple different cells."""
        add_cell(source="first")
        add_cell(source="second")
        add_cell(source="third")

        update_cell_source(index=0, source="FIRST")
        update_cell_source(index=2, source="THIRD")

        assert get_cell_source(index=0) == "FIRST"
        assert get_cell_source(index=1) == "second"  # unchanged
        assert get_cell_source(index=2) == "THIRD"
