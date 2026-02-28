"""
Tests for Notebook cell CRUD operations.

Covers add_cell, insert_cell, remove_cell, get_cell, update_cell, and _touch.
"""

import pytest
from notebook_lr.notebook import Notebook, Cell, CellType


class TestAddCell:

    def test_add_cell_no_args_creates_default_code_cell(self):
        nb = Notebook()
        cell = nb.add_cell()
        assert cell.type == CellType.CODE
        assert cell.source == ""
        assert len(nb.cells) == 1

    def test_add_cell_with_cell_object_adds_that_cell(self):
        nb = Notebook()
        c = Cell(type=CellType.CODE, source="x = 1")
        returned = nb.add_cell(cell=c)
        assert returned is c
        assert nb.cells[0] is c

    def test_add_cell_with_kwargs(self):
        nb = Notebook()
        cell = nb.add_cell(type=CellType.MARKDOWN, source="# Hi")
        assert cell.type == CellType.MARKDOWN
        assert cell.source == "# Hi"

    def test_add_cell_updates_modified_timestamp(self):
        nb = Notebook()
        before = nb.metadata["modified"]
        nb.add_cell(source="x")
        assert nb.metadata["modified"] >= before

    def test_multiple_add_cell_calls_append_in_order(self):
        nb = Notebook()
        for i in range(5):
            nb.add_cell(source=str(i))
        assert [c.source for c in nb.cells] == ["0", "1", "2", "3", "4"]


class TestInsertCell:

    def test_insert_cell_at_index_0_beginning(self):
        nb = Notebook()
        nb.add_cell(source="second")
        nb.insert_cell(0, source="first")
        assert nb.cells[0].source == "first"
        assert nb.cells[1].source == "second"

    def test_insert_cell_at_middle_index(self):
        nb = Notebook()
        nb.add_cell(source="a")
        nb.add_cell(source="c")
        nb.insert_cell(1, source="b")
        assert nb.cells[1].source == "b"
        assert nb.cells[2].source == "c"

    def test_insert_cell_at_end(self):
        nb = Notebook()
        nb.add_cell(source="a")
        nb.add_cell(source="b")
        nb.insert_cell(len(nb.cells), source="c")
        assert nb.cells[-1].source == "c"

    def test_insert_cell_with_cell_none_and_kwargs(self):
        nb = Notebook()
        cell = nb.insert_cell(0, cell=None, source="from kwargs", type=CellType.MARKDOWN)
        assert cell.source == "from kwargs"
        assert cell.type == CellType.MARKDOWN

    def test_insert_cell_updates_modified_timestamp(self):
        nb = Notebook()
        nb.add_cell(source="a")
        before = nb.metadata["modified"]
        nb.insert_cell(0, source="new")
        assert nb.metadata["modified"] >= before


class TestRemoveCell:

    def test_remove_cell_returns_the_removed_cell(self):
        nb = Notebook()
        cell = nb.add_cell(source="target")
        nb.add_cell(source="other")
        removed = nb.remove_cell(0)
        assert removed is cell

    def test_remove_cell_at_index_0(self):
        nb = Notebook()
        nb.add_cell(source="first")
        nb.add_cell(source="second")
        nb.remove_cell(0)
        assert len(nb.cells) == 1
        assert nb.cells[0].source == "second"

    def test_remove_cell_at_last_index(self):
        nb = Notebook()
        nb.add_cell(source="first")
        nb.add_cell(source="last")
        nb.remove_cell(1)
        assert len(nb.cells) == 1
        assert nb.cells[0].source == "first"

    def test_remove_cell_from_single_cell_notebook(self):
        nb = Notebook()
        nb.add_cell(source="only")
        nb.remove_cell(0)
        assert nb.cells == []

    def test_remove_cell_out_of_range_raises_index_error(self):
        nb = Notebook()
        nb.add_cell(source="only")
        with pytest.raises(IndexError):
            nb.remove_cell(5)


class TestGetCell:

    def test_get_cell_returns_correct_cell_by_index(self):
        nb = Notebook()
        nb.add_cell(source="first")
        nb.add_cell(source="second")
        assert nb.get_cell(0).source == "first"
        assert nb.get_cell(1).source == "second"

    def test_get_cell_with_negative_index(self):
        nb = Notebook()
        nb.add_cell(source="first")
        nb.add_cell(source="last")
        assert nb.get_cell(-1).source == "last"

    def test_get_cell_out_of_range_raises_index_error(self):
        nb = Notebook()
        nb.add_cell(source="only")
        with pytest.raises(IndexError):
            nb.get_cell(10)


class TestUpdateCell:

    def test_update_cell_changes_source(self):
        nb = Notebook()
        nb.add_cell(source="old")
        nb.update_cell(0, source="new")
        assert nb.cells[0].source == "new"

    def test_update_cell_changes_type(self):
        nb = Notebook()
        nb.add_cell(type=CellType.CODE, source="x")
        nb.update_cell(0, type=CellType.MARKDOWN)
        assert nb.cells[0].type == CellType.MARKDOWN

    def test_update_cell_non_existent_attribute_is_ignored(self):
        nb = Notebook()
        nb.add_cell(source="x")
        # Should not raise for unknown attribute
        nb.update_cell(0, totally_fake_field="ignored", source="updated")
        assert nb.cells[0].source == "updated"

    def test_update_cell_updates_modified_timestamp(self):
        nb = Notebook()
        nb.add_cell(source="x")
        before = nb.metadata["modified"]
        nb.update_cell(0, source="y")
        assert nb.metadata["modified"] >= before


class TestTouch:

    def test_touch_updates_metadata_modified(self):
        nb = Notebook()
        old_modified = nb.metadata["modified"]
        nb._touch()
        assert nb.metadata["modified"] >= old_modified
