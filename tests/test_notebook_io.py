"""
Tests for Notebook file I/O and serialization.

Focuses on save/load round-trips, serialization fidelity,
directory creation, session state handling, and edge cases
not covered in test_notebook.py.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from notebook_lr.notebook import Notebook, Cell, CellType, Comment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_comment(**kwargs) -> Comment:
    defaults = dict(
        from_line=0, from_ch=0, to_line=0, to_ch=5,
        selected_text="x = 1", user_comment="What does this do?",
    )
    defaults.update(kwargs)
    return Comment(**defaults)


# ---------------------------------------------------------------------------
# Cell serialization round-trips
# ---------------------------------------------------------------------------

class TestCellSerialization:

    def test_code_cell_round_trip(self):
        cell = Cell(type=CellType.CODE, source="print('hello')",
                    outputs=[{"type": "stream", "text": "hello\n"}],
                    execution_count=3)
        d = cell.to_dict()
        restored = Cell.from_dict(d)

        assert restored.id == cell.id
        assert restored.type == CellType.CODE
        assert restored.source == "print('hello')"
        assert restored.execution_count == 3
        assert restored.outputs == [{"type": "stream", "text": "hello\n"}]

    def test_markdown_cell_round_trip(self):
        cell = Cell(type=CellType.MARKDOWN, source="# Header\n\nParagraph.")
        d = cell.to_dict()
        restored = Cell.from_dict(d)

        assert restored.type == CellType.MARKDOWN
        assert restored.source == "# Header\n\nParagraph."

    def test_cell_with_metadata_round_trip(self):
        cell = Cell(metadata={"collapsed": True, "tags": ["important"]})
        d = cell.to_dict()
        restored = Cell.from_dict(d)

        assert restored.metadata == {"collapsed": True, "tags": ["important"]}

    def test_cell_with_comments_round_trip(self):
        comment = _make_comment(ai_response="It assigns 1 to x.", status="resolved")
        cell = Cell(source="x = 1", comments=[comment])
        d = cell.to_dict()
        restored = Cell.from_dict(d)

        assert len(restored.comments) == 1
        c = restored.comments[0]
        assert c.user_comment == "What does this do?"
        assert c.ai_response == "It assigns 1 to x."
        assert c.status == "resolved"

    def test_cell_to_dict_type_is_string(self):
        """to_dict must serialize type as a plain string, not enum."""
        cell = Cell(type=CellType.MARKDOWN)
        d = cell.to_dict()
        assert isinstance(d["type"], str)
        assert d["type"] == "markdown"

    def test_cell_from_dict_missing_optional_fields(self):
        """from_dict should handle missing optional fields gracefully."""
        minimal = {"type": "code", "source": "pass"}
        cell = Cell.from_dict(minimal)
        assert cell.source == "pass"
        assert cell.outputs == []
        assert cell.execution_count is None
        assert cell.metadata == {}
        assert cell.comments == []

    def test_cell_from_dict_with_unknown_type_raises(self):
        """CellType enum should reject unknown type strings."""
        with pytest.raises(ValueError):
            Cell.from_dict({"type": "notebook", "source": ""})

    def test_cell_multiple_outputs_preserved(self):
        outputs = [
            {"type": "stream", "text": "line1\n"},
            {"type": "execute_result", "data": {"text/plain": "42"}},
        ]
        cell = Cell(outputs=outputs)
        restored = Cell.from_dict(cell.to_dict())
        assert restored.outputs == outputs


# ---------------------------------------------------------------------------
# Notebook serialization (to_dict / from_dict)
# ---------------------------------------------------------------------------

class TestNotebookSerialization:

    def test_to_dict_structure(self):
        nb = Notebook.new("Serialization Test")
        nb.add_cell(source="a = 1")
        nb.add_cell(type=CellType.MARKDOWN, source="## Section")

        d = nb.to_dict()

        assert set(d.keys()) >= {"version", "cells", "metadata", "session_state"}
        assert d["version"] == "1.0"
        assert len(d["cells"]) == 2
        assert d["metadata"]["name"] == "Serialization Test"

    def test_from_dict_preserves_cells(self):
        d = {
            "version": "1.0",
            "metadata": {"name": "Loaded"},
            "cells": [
                {"type": "code", "source": "x = 10", "outputs": [],
                 "execution_count": 2, "metadata": {}},
                {"type": "markdown", "source": "# Hi", "outputs": [],
                 "execution_count": None, "metadata": {}},
            ],
            "session_state": None,
        }
        nb = Notebook.from_dict(d)

        assert nb.metadata["name"] == "Loaded"
        assert len(nb.cells) == 2
        assert nb.cells[0].source == "x = 10"
        assert nb.cells[0].execution_count == 2
        assert nb.cells[1].type == CellType.MARKDOWN

    def test_from_dict_no_cells_key(self):
        """from_dict should handle missing 'cells' key."""
        nb = Notebook.from_dict({"version": "1.0", "metadata": {"name": "Empty"}})
        assert nb.cells == []

    def test_from_dict_session_state_preserved(self):
        state = {"user_ns": {"x": 99}, "execution_count": 5}
        d = {
            "version": "1.0",
            "cells": [],
            "metadata": {},
            "session_state": state,
        }
        nb = Notebook.from_dict(d)
        assert nb.session_state == state

    def test_from_dict_missing_version_defaults(self):
        nb = Notebook.from_dict({"cells": [], "metadata": {"name": "No Version"}})
        assert nb.version == "1.0"

    def test_to_dict_session_state_none_by_default(self):
        nb = Notebook.new("Fresh")
        d = nb.to_dict()
        assert d["session_state"] is None

    def test_round_trip_with_comments(self):
        nb = Notebook.new("Comment NB")
        comment = _make_comment(provider="glm", status="loading")
        cell = Cell(source="y = 2", comments=[comment])
        nb.add_cell(cell=cell)

        d = nb.to_dict()
        restored = Notebook.from_dict(d)

        assert len(restored.cells[0].comments) == 1
        assert restored.cells[0].comments[0].provider == "glm"


# ---------------------------------------------------------------------------
# File I/O: save and load
# ---------------------------------------------------------------------------

class TestNotebookFileIO:

    def test_save_creates_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("Save Test")
            nb.save(path)
            assert path.exists()

    def test_saved_file_is_valid_json(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("JSON Test")
            nb.add_cell(source="1 + 1")
            nb.save(path)

            with open(path) as f:
                data = json.load(f)

            assert "version" in data
            assert "cells" in data

    def test_save_and_load_preserves_all_cell_types(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("Mixed")
            nb.add_cell(type=CellType.CODE, source="x = 1", execution_count=1)
            nb.add_cell(type=CellType.MARKDOWN, source="# Title")
            nb.save(path)

            loaded = Notebook.load(path)

            assert loaded.cells[0].type == CellType.CODE
            assert loaded.cells[0].execution_count == 1
            assert loaded.cells[1].type == CellType.MARKDOWN
            assert loaded.cells[1].source == "# Title"

    def test_save_and_load_preserves_outputs(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            outputs = [{"type": "execute_result", "data": {"text/plain": "42"}}]
            nb = Notebook.new("Output NB")
            nb.add_cell(source="42", outputs=outputs, execution_count=1)
            nb.save(path)

            loaded = Notebook.load(path)

            assert loaded.cells[0].outputs == outputs

    def test_save_and_load_preserves_metadata(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("Meta NB")
            nb.metadata["author"] = "Test User"
            nb.metadata["tags"] = ["science", "data"]
            nb.save(path)

            loaded = Notebook.load(path)

            assert loaded.metadata["name"] == "Meta NB"
            assert loaded.metadata["author"] == "Test User"
            assert loaded.metadata["tags"] == ["science", "data"]

    def test_save_with_session_data(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb_session.nblr"
            nb = Notebook.new("Session NB")
            session = {"user_ns": {"a": 1, "b": [1, 2, 3]}, "execution_count": 7}
            nb.save(path, include_session=True, session_data=session)

            loaded = Notebook.load(path)

            assert loaded.session_state is not None
            assert loaded.session_state["user_ns"]["b"] == [1, 2, 3]
            assert loaded.session_state["execution_count"] == 7

    def test_save_without_session_clears_session_state(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("No Session")
            # Manually set session state, then save without it
            nb.session_state = {"user_ns": {"x": 1}}
            nb.save(path, include_session=False)

            loaded = Notebook.load(path)

            assert loaded.session_state is None

    def test_save_include_session_false_with_data_ignores_data(self):
        """include_session=False should suppress session even if session_data given."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("No Session")
            nb.save(path, include_session=False, session_data={"user_ns": {"z": 9}})

            loaded = Notebook.load(path)

            assert loaded.session_state is None

    def test_save_creates_parent_directories(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "deep" / "nb.nblr"
            nb = Notebook.new("Deep")
            nb.save(path)
            assert path.exists()

    def test_load_preserves_version(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            data = {"version": "2.0", "cells": [], "metadata": {"name": "V2"}, "session_state": None}
            with open(path, "w") as f:
                json.dump(data, f)

            nb = Notebook.load(path)

            assert nb.version == "2.0"

    def test_load_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            Notebook.load(Path("/tmp/does_not_exist_xyz.nblr"))

    def test_save_and_load_empty_notebook(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "empty.nblr"
            nb = Notebook.new("Empty NB")
            nb.save(path)

            loaded = Notebook.load(path)

            assert loaded.cells == []
            assert loaded.metadata["name"] == "Empty NB"

    def test_save_overwrites_existing_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb1 = Notebook.new("First Version")
            nb1.save(path)

            nb2 = Notebook.new("Second Version")
            nb2.save(path)

            loaded = Notebook.load(path)
            assert loaded.metadata["name"] == "Second Version"

    def test_load_minimal_json_without_cells_key(self):
        """Backwards compat: files missing 'cells' key should load fine."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "min.nblr"
            with open(path, "w") as f:
                json.dump({"version": "1.0", "metadata": {"name": "Minimal"}}, f)

            nb = Notebook.load(path)
            assert nb.cells == []

    def test_save_and_load_cell_with_comments(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "comments.nblr"
            comment = _make_comment(
                user_comment="Why?", ai_response="Because.", status="resolved"
            )
            nb = Notebook.new("Comment NB")
            nb.add_cell(source="pass", comments=[comment])
            nb.save(path)

            loaded = Notebook.load(path)
            assert len(loaded.cells[0].comments) == 1
            c = loaded.cells[0].comments[0]
            assert c.user_comment == "Why?"
            assert c.ai_response == "Because."
            assert c.status == "resolved"

    def test_save_produces_indented_json(self):
        """Saved files should be human-readable (indented)."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("Indent Test")
            nb.save(path)

            raw = path.read_text()
            # Indented JSON has newlines and spaces
            assert "\n" in raw
            assert "  " in raw

    def test_load_path_as_string(self):
        """Notebook.load should accept string paths."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nb.nblr"
            nb = Notebook.new("String Path")
            nb.save(str(path))

            loaded = Notebook.load(str(path))
            assert loaded.metadata["name"] == "String Path"


# ---------------------------------------------------------------------------
# Notebook.new factory
# ---------------------------------------------------------------------------

class TestNotebookNew:

    def test_new_sets_name(self):
        nb = Notebook.new("My Book")
        assert nb.metadata["name"] == "My Book"

    def test_new_default_name(self):
        nb = Notebook.new()
        assert nb.metadata["name"] == "Untitled"

    def test_new_has_created_and_modified(self):
        nb = Notebook.new("Timestamps")
        assert "created" in nb.metadata
        assert "modified" in nb.metadata

    def test_new_cells_empty(self):
        nb = Notebook.new("Empty")
        assert nb.cells == []

    def test_new_version_is_1_0(self):
        nb = Notebook.new("V")
        assert nb.version == "1.0"
