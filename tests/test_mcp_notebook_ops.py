"""
Tests for MCP server notebook-level operations.

Covers:
- get_notebook_info(): cell counts, executed count, metadata fields
- save_notebook(): path handling, include_session, return value, file validity
- _validate_index(): boundary conditions
- _cell_to_output(): Cell -> CellOutput conversion
- Global state: get_notebook, get_kernel, get_session_manager, _reset_notebook
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from notebook_lr import Notebook, Cell, CellType, NotebookKernel, SessionManager
from notebook_lr.mcp_server import (
    get_notebook,
    get_kernel,
    get_session_manager,
    get_notebook_info,
    save_notebook,
    _validate_index,
    _cell_to_output,
    _reset_notebook,
    add_cell,
    NotebookInfo,
    CellOutput,
)
import notebook_lr.mcp_server as mcp_server


# =============================================================================
# get_notebook_info()
# =============================================================================

class TestGetNotebookInfo:

    def test_empty_notebook_has_zero_counts(self):
        result = get_notebook_info()
        assert isinstance(result, NotebookInfo)
        assert result.cell_count == 0
        assert result.code_count == 0
        assert result.markdown_count == 0

    def test_mixed_cells_returns_correct_counts(self):
        add_cell(cell_type="code", source="x = 1")
        add_cell(cell_type="markdown", source="# Title")
        add_cell(cell_type="code", source="y = 2")

        result = get_notebook_info()
        assert result.cell_count == 3
        assert result.code_count == 2
        assert result.markdown_count == 1

    def test_executed_count_counts_non_none_execution_count(self):
        add_cell(cell_type="code", source="a = 1")
        add_cell(cell_type="code", source="b = 2")
        add_cell(cell_type="code", source="c = 3")

        nb = get_notebook()
        nb.cells[0].execution_count = 1
        nb.cells[1].execution_count = 2
        # cells[2] has execution_count=None (unexecuted)

        result = get_notebook_info()
        assert result.executed_count == 2

    def test_name_comes_from_metadata(self):
        nb = get_notebook()
        nb.metadata["name"] = "My Test Notebook"
        result = get_notebook_info()
        assert result.name == "My Test Notebook"

    def test_version_is_1_0(self):
        result = get_notebook_info()
        assert result.version == "1.0"

    def test_path_is_none_by_default(self):
        result = get_notebook_info()
        assert result.path is None


# =============================================================================
# save_notebook()
# =============================================================================

class TestSaveNotebook:

    def test_save_without_path_uses_metadata_path(self, tmp_path):
        nb = get_notebook()
        default_path = str(tmp_path / "notebook.nblr")
        nb.metadata["path"] = default_path

        result = save_notebook()
        assert result["path"] == default_path
        assert Path(default_path).exists()

    def test_save_with_custom_path(self, tmp_path):
        custom_path = str(tmp_path / "custom.nblr")
        result = save_notebook(path=custom_path)
        assert result["path"] == custom_path
        assert Path(custom_path).exists()

    def test_save_without_session(self, tmp_path):
        save_path = str(tmp_path / "no_session.nblr")
        result = save_notebook(path=save_path, include_session=False)
        assert result["status"] == "saved"

        with open(save_path) as f:
            data = json.load(f)
        assert data.get("session_state") is None

    def test_save_with_session(self, tmp_path):
        mock_kernel = MagicMock()
        mock_kernel.get_namespace.return_value = {"x": 1}
        mock_kernel.execution_count = 1
        mcp_server._kernel = mock_kernel

        save_path = str(tmp_path / "with_session.nblr")
        result = save_notebook(path=save_path, include_session=True)
        assert result["status"] == "saved with session"

        with open(save_path) as f:
            data = json.load(f)
        assert data["session_state"] is not None
        assert data["session_state"]["user_ns"] == {"x": 1}

    def test_save_returns_dict_with_status_and_path(self, tmp_path):
        save_path = str(tmp_path / "nb.nblr")
        result = save_notebook(path=save_path)
        assert "status" in result
        assert "path" in result

    def test_saved_file_is_valid_and_loadable(self, tmp_path):
        add_cell(cell_type="code", source="print('hello')")
        add_cell(cell_type="markdown", source="# Title")
        save_path = str(tmp_path / "loadable.nblr")
        save_notebook(path=save_path)

        loaded = Notebook.load(Path(save_path))
        assert len(loaded.cells) == 2
        assert loaded.cells[0].source == "print('hello')"
        assert loaded.cells[1].source == "# Title"
        assert loaded.version == "1.0"

    def test_save_updates_metadata_path(self, tmp_path):
        save_path = str(tmp_path / "meta.nblr")
        save_notebook(path=save_path)
        nb = get_notebook()
        assert nb.metadata["path"] == save_path

    def test_save_default_fallback_to_notebook_nblr(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = save_notebook()
        assert result["path"] == "notebook.nblr"
        assert Path(tmp_path / "notebook.nblr").exists()


# =============================================================================
# _validate_index()
# =============================================================================

class TestValidateIndex:

    def test_valid_index_zero_does_not_raise(self):
        add_cell(source="first")
        _validate_index(0)  # should not raise

    def test_valid_index_last_does_not_raise(self):
        add_cell(source="a")
        add_cell(source="b")
        add_cell(source="c")
        _validate_index(2)  # should not raise

    def test_negative_index_raises_value_error(self):
        add_cell(source="cell")
        with pytest.raises(ValueError):
            _validate_index(-1)

    def test_index_equal_to_length_raises_value_error(self):
        add_cell(source="only")
        with pytest.raises(ValueError):
            _validate_index(1)  # len == 1, so index 1 is out of range

    def test_index_on_empty_notebook_raises_value_error(self):
        # notebook is empty (reset by conftest)
        with pytest.raises(ValueError):
            _validate_index(0)


# =============================================================================
# _cell_to_output()
# =============================================================================

class TestCellToOutput:

    def test_converts_cell_to_cell_output(self):
        cell = Cell(type=CellType.CODE, source="x = 1")
        result = _cell_to_output(cell, 0)
        assert isinstance(result, CellOutput)

    def test_includes_correct_index(self):
        cell = Cell(type=CellType.CODE, source="y = 2")
        result = _cell_to_output(cell, 5)
        assert result.index == 5

    def test_type_is_string_not_enum(self):
        code_cell = Cell(type=CellType.CODE, source="")
        md_cell = Cell(type=CellType.MARKDOWN, source="")
        assert _cell_to_output(code_cell, 0).type == "code"
        assert _cell_to_output(md_cell, 0).type == "markdown"

    def test_source_is_preserved(self):
        cell = Cell(type=CellType.CODE, source="print('test')")
        result = _cell_to_output(cell, 0)
        assert result.source == "print('test')"

    def test_id_is_preserved(self):
        cell = Cell(type=CellType.CODE, source="")
        result = _cell_to_output(cell, 0)
        assert result.id == cell.id

    def test_outputs_is_list(self):
        cell = Cell(type=CellType.CODE, source="", outputs=[{"type": "text", "text": "hi"}])
        result = _cell_to_output(cell, 0)
        assert isinstance(result.outputs, list)
        assert len(result.outputs) == 1

    def test_execution_count_preserved(self):
        cell = Cell(type=CellType.CODE, source="", execution_count=7)
        result = _cell_to_output(cell, 0)
        assert result.execution_count == 7

    def test_execution_count_none_when_not_set(self):
        cell = Cell(type=CellType.CODE, source="")
        result = _cell_to_output(cell, 0)
        assert result.execution_count is None


# =============================================================================
# Global state helpers
# =============================================================================

class TestGlobalState:

    def test_get_notebook_creates_new_notebook_if_none(self):
        # conftest already reset; _notebook should be None
        assert mcp_server._notebook is None
        nb = get_notebook()
        assert isinstance(nb, Notebook)
        assert mcp_server._notebook is nb

    def test_get_notebook_returns_same_instance_on_repeat_calls(self):
        nb1 = get_notebook()
        nb2 = get_notebook()
        assert nb1 is nb2

    def test_get_kernel_creates_new_kernel_if_none(self):
        assert mcp_server._kernel is None
        k = get_kernel()
        assert isinstance(k, NotebookKernel)
        assert mcp_server._kernel is k

    def test_get_kernel_returns_same_instance_on_repeat_calls(self):
        k1 = get_kernel()
        k2 = get_kernel()
        assert k1 is k2

    def test_get_session_manager_creates_new_if_none(self):
        assert mcp_server._session_manager is None
        sm = get_session_manager()
        assert isinstance(sm, SessionManager)
        assert mcp_server._session_manager is sm

    def test_get_session_manager_returns_same_instance(self):
        sm1 = get_session_manager()
        sm2 = get_session_manager()
        assert sm1 is sm2

    def test_reset_notebook_sets_all_globals_to_none(self):
        # Force creation of all globals
        get_notebook()
        get_kernel()
        get_session_manager()

        assert mcp_server._notebook is not None
        assert mcp_server._kernel is not None
        assert mcp_server._session_manager is not None

        _reset_notebook()

        assert mcp_server._notebook is None
        assert mcp_server._kernel is None
        assert mcp_server._session_manager is None
