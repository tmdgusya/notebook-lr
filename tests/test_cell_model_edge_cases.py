"""
Edge case tests for the Cell model.
Focuses on areas not covered in test_notebook.py.
"""

import pytest
from datetime import datetime

from notebook_lr.notebook import Cell, CellType, Comment


class TestCellIdGeneration:
    """Test Cell ID auto-generation behavior."""

    def test_id_is_auto_generated(self):
        """Cell gets a unique ID by default."""
        cell = Cell()
        assert cell.id.startswith("cell_")

    def test_ids_are_unique(self):
        """Two cells created in sequence get different IDs."""
        cell1 = Cell()
        cell2 = Cell()
        assert cell1.id != cell2.id

    def test_custom_id_is_preserved(self):
        """Explicitly provided ID is not overwritten."""
        cell = Cell(id="my_custom_id")
        assert cell.id == "my_custom_id"

    def test_id_format(self):
        """Auto-generated ID follows expected format: cell_YYYYMMDDHHMMSSXXXXXX."""
        cell = Cell()
        # Should be "cell_" followed by digits only
        suffix = cell.id[len("cell_"):]
        assert suffix.isdigit(), f"Expected numeric suffix, got: {suffix!r}"


class TestCellTypeEnum:
    """Test CellType enum and Cell.type field."""

    def test_cell_type_code_string_value(self):
        assert CellType.CODE.value == "code"

    def test_cell_type_markdown_string_value(self):
        assert CellType.MARKDOWN.value == "markdown"

    def test_cell_type_is_str_subclass(self):
        """CellType values can be compared to plain strings."""
        assert CellType.CODE == "code"
        assert CellType.MARKDOWN == "markdown"

    def test_cell_created_with_string_type_code(self):
        """Cell accepts 'code' string for type."""
        cell = Cell(type="code")
        assert cell.type == CellType.CODE

    def test_cell_created_with_string_type_markdown(self):
        """Cell accepts 'markdown' string for type."""
        cell = Cell(type="markdown")
        assert cell.type == CellType.MARKDOWN

    def test_invalid_type_raises(self):
        """Providing an unsupported type value raises a validation error."""
        with pytest.raises(Exception):
            Cell(type="invalid_type")


class TestCellDefaults:
    """Test that Cell default field values are correct."""

    def test_default_type_is_code(self):
        cell = Cell()
        assert cell.type == CellType.CODE

    def test_default_source_is_empty_string(self):
        cell = Cell()
        assert cell.source == ""

    def test_default_outputs_is_empty_list(self):
        cell = Cell()
        assert cell.outputs == []

    def test_default_execution_count_is_none(self):
        cell = Cell()
        assert cell.execution_count is None

    def test_default_metadata_is_empty_dict(self):
        cell = Cell()
        assert cell.metadata == {}

    def test_default_comments_is_empty_list(self):
        cell = Cell()
        assert cell.comments == []

    def test_outputs_list_is_independent_per_instance(self):
        """Each Cell gets its own outputs list, not a shared reference."""
        cell1 = Cell()
        cell2 = Cell()
        cell1.outputs.append({"type": "stream", "text": "hello"})
        assert cell2.outputs == []

    def test_metadata_dict_is_independent_per_instance(self):
        """Each Cell gets its own metadata dict."""
        cell1 = Cell()
        cell2 = Cell()
        cell1.metadata["key"] = "value"
        assert "key" not in cell2.metadata

    def test_comments_list_is_independent_per_instance(self):
        """Each Cell gets its own comments list."""
        cell1 = Cell()
        cell2 = Cell()
        cell1.comments.append(Comment(
            from_line=0, from_ch=0, to_line=0, to_ch=5,
            selected_text="hello", user_comment="test"
        ))
        assert cell2.comments == []


class TestCellToDict:
    """Edge cases for Cell.to_dict()."""

    def test_to_dict_contains_all_keys(self):
        cell = Cell()
        d = cell.to_dict()
        expected_keys = {"id", "type", "source", "outputs", "execution_count", "metadata", "comments"}
        assert set(d.keys()) == expected_keys

    def test_to_dict_type_is_string(self):
        """type field in dict should be string 'code', not enum."""
        cell = Cell(type=CellType.CODE)
        d = cell.to_dict()
        assert isinstance(d["type"], str)
        assert d["type"] == "code"

    def test_to_dict_markdown_type_is_string(self):
        cell = Cell(type=CellType.MARKDOWN)
        d = cell.to_dict()
        assert d["type"] == "markdown"

    def test_to_dict_none_execution_count(self):
        cell = Cell(execution_count=None)
        d = cell.to_dict()
        assert d["execution_count"] is None

    def test_to_dict_with_execution_count(self):
        cell = Cell(execution_count=5)
        d = cell.to_dict()
        assert d["execution_count"] == 5

    def test_to_dict_with_outputs(self):
        outputs = [{"type": "stream", "text": "out"}, {"type": "error", "ename": "ValueError"}]
        cell = Cell(outputs=outputs)
        d = cell.to_dict()
        assert d["outputs"] == outputs

    def test_to_dict_with_metadata(self):
        meta = {"collapsed": True, "scrolled": False}
        cell = Cell(metadata=meta)
        d = cell.to_dict()
        assert d["metadata"] == meta

    def test_to_dict_comments_serialized(self):
        """Comments are serialized via model_dump."""
        comment = Comment(
            from_line=1, from_ch=0, to_line=1, to_ch=10,
            selected_text="x = 1", user_comment="What is this?"
        )
        cell = Cell(comments=[comment])
        d = cell.to_dict()
        assert len(d["comments"]) == 1
        c = d["comments"][0]
        assert c["from_line"] == 1
        assert c["selected_text"] == "x = 1"
        assert c["user_comment"] == "What is this?"

    def test_to_dict_empty_source(self):
        cell = Cell(source="")
        d = cell.to_dict()
        assert d["source"] == ""

    def test_to_dict_multiline_source(self):
        src = "x = 1\ny = 2\nprint(x + y)"
        cell = Cell(source=src)
        d = cell.to_dict()
        assert d["source"] == src

    def test_to_dict_outputs_is_same_reference(self):
        """to_dict() returns the live outputs list (not a copy) — documenting actual behavior."""
        cell = Cell(outputs=[{"type": "stream", "text": "hello"}])
        d = cell.to_dict()
        assert d["outputs"] is cell.outputs


class TestCellFromDict:
    """Edge cases for Cell.from_dict()."""

    def test_from_dict_minimal(self):
        """from_dict works with only required-ish fields."""
        d = {"type": "code", "source": "x = 1"}
        cell = Cell.from_dict(d)
        assert cell.type == CellType.CODE
        assert cell.source == "x = 1"

    def test_from_dict_missing_id_generates_new(self):
        """If id is missing, a new one is generated."""
        d = {"type": "code", "source": ""}
        cell = Cell.from_dict(d)
        assert cell.id.startswith("cell_")

    def test_from_dict_explicit_id(self):
        d = {"id": "abc123", "type": "code", "source": ""}
        cell = Cell.from_dict(d)
        assert cell.id == "abc123"

    def test_from_dict_markdown_type(self):
        d = {"type": "markdown", "source": "# Heading"}
        cell = Cell.from_dict(d)
        assert cell.type == CellType.MARKDOWN
        assert cell.source == "# Heading"

    def test_from_dict_missing_outputs_defaults_to_empty(self):
        d = {"type": "code", "source": ""}
        cell = Cell.from_dict(d)
        assert cell.outputs == []

    def test_from_dict_missing_execution_count_defaults_to_none(self):
        d = {"type": "code", "source": ""}
        cell = Cell.from_dict(d)
        assert cell.execution_count is None

    def test_from_dict_with_execution_count(self):
        d = {"type": "code", "source": "", "execution_count": 7}
        cell = Cell.from_dict(d)
        assert cell.execution_count == 7

    def test_from_dict_missing_metadata_defaults_to_empty(self):
        d = {"type": "code", "source": ""}
        cell = Cell.from_dict(d)
        assert cell.metadata == {}

    def test_from_dict_with_metadata(self):
        d = {"type": "code", "source": "", "metadata": {"collapsed": True}}
        cell = Cell.from_dict(d)
        assert cell.metadata == {"collapsed": True}

    def test_from_dict_missing_comments_defaults_to_empty(self):
        d = {"type": "code", "source": ""}
        cell = Cell.from_dict(d)
        assert cell.comments == []

    def test_from_dict_with_comments(self):
        d = {
            "type": "code",
            "source": "x = 1",
            "comments": [
                {
                    "id": "cmt_001",
                    "from_line": 0,
                    "from_ch": 0,
                    "to_line": 0,
                    "to_ch": 5,
                    "selected_text": "x = 1",
                    "user_comment": "Explain this",
                    "ai_response": "",
                    "status": "pending",
                    "provider": "claude",
                    "created_at": datetime.now().isoformat(),
                }
            ],
        }
        cell = Cell.from_dict(d)
        assert len(cell.comments) == 1
        assert cell.comments[0].user_comment == "Explain this"
        assert cell.comments[0].id == "cmt_001"

    def test_from_dict_missing_type_defaults_to_code(self):
        """type field missing defaults to 'code'."""
        d = {"source": "x = 1"}
        cell = Cell.from_dict(d)
        assert cell.type == CellType.CODE

    def test_roundtrip_to_dict_from_dict(self):
        """Cell survives a round-trip through to_dict/from_dict."""
        original = Cell(
            type=CellType.MARKDOWN,
            source="# Title\n\nSome text.",
            outputs=[],
            execution_count=None,
            metadata={"key": "val"},
        )
        d = original.to_dict()
        restored = Cell.from_dict(d)

        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.source == original.source
        assert restored.outputs == original.outputs
        assert restored.execution_count == original.execution_count
        assert restored.metadata == original.metadata

    def test_roundtrip_with_comments(self):
        """Cell with comments survives round-trip."""
        comment = Comment(
            from_line=2, from_ch=4, to_line=2, to_ch=10,
            selected_text="result", user_comment="Is this right?",
            ai_response="Yes!", status="resolved", provider="claude",
        )
        original = Cell(source="result = compute()", comments=[comment])
        d = original.to_dict()
        restored = Cell.from_dict(d)

        assert len(restored.comments) == 1
        c = restored.comments[0]
        assert c.from_line == 2
        assert c.from_ch == 4
        assert c.to_line == 2
        assert c.to_ch == 10
        assert c.selected_text == "result"
        assert c.user_comment == "Is this right?"
        assert c.ai_response == "Yes!"
        assert c.status == "resolved"


class TestCellWithComplexOutputs:
    """Test Cell with various output types."""

    def test_cell_with_stream_output(self):
        outputs = [{"type": "stream", "name": "stdout", "text": "hello\n"}]
        cell = Cell(outputs=outputs)
        assert cell.outputs[0]["type"] == "stream"

    def test_cell_with_error_output(self):
        outputs = [{"type": "error", "ename": "ZeroDivisionError", "evalue": "division by zero", "traceback": []}]
        cell = Cell(outputs=outputs)
        assert cell.outputs[0]["ename"] == "ZeroDivisionError"

    def test_cell_with_multiple_outputs(self):
        outputs = [
            {"type": "stream", "text": "step 1\n"},
            {"type": "stream", "text": "step 2\n"},
            {"type": "display_data", "data": {"text/plain": "42"}},
        ]
        cell = Cell(outputs=outputs)
        assert len(cell.outputs) == 3

    def test_cell_with_rich_output(self):
        outputs = [{"type": "display_data", "data": {"text/html": "<b>bold</b>", "text/plain": "bold"}}]
        cell = Cell(outputs=outputs)
        d = cell.to_dict()
        assert d["outputs"][0]["data"]["text/html"] == "<b>bold</b>"


class TestCellFieldAssignment:
    """Test direct field mutation on Cell (Pydantic model)."""

    def test_can_update_source(self):
        cell = Cell(source="original")
        cell.source = "updated"
        assert cell.source == "updated"

    def test_can_update_execution_count(self):
        cell = Cell()
        cell.execution_count = 3
        assert cell.execution_count == 3

    def test_can_append_to_outputs(self):
        cell = Cell()
        cell.outputs.append({"type": "stream", "text": "hi"})
        assert len(cell.outputs) == 1

    def test_can_set_metadata_key(self):
        cell = Cell()
        cell.metadata["collapsed"] = True
        assert cell.metadata["collapsed"] is True

    def test_can_add_comment(self):
        cell = Cell(source="x = 1")
        comment = Comment(
            from_line=0, from_ch=0, to_line=0, to_ch=5,
            selected_text="x = 1", user_comment="Why?"
        )
        cell.comments.append(comment)
        assert len(cell.comments) == 1
        assert cell.comments[0].user_comment == "Why?"
