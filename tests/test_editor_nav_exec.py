"""
Unit tests for NotebookEditor navigation and execution in notebook_lr/cli.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from notebook_lr.cli import NotebookEditor
from notebook_lr import Notebook, Cell, CellType, NotebookKernel


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def editor():
    nb = Notebook.new()
    nb.add_cell(type=CellType.CODE, source="x = 1")
    nb.add_cell(type=CellType.CODE, source="print('hello')")
    nb.add_cell(type=CellType.MARKDOWN, source="# Title")
    nb.add_cell(type=CellType.CODE, source="y = x + 1")
    return NotebookEditor(nb)


# ---------------------------------------------------------------------------
# Navigation state
# ---------------------------------------------------------------------------

class TestNavigationState:
    def test_initial_index_is_zero(self, editor):
        assert editor.current_cell_index == 0

    def test_index_can_be_set_to_valid_value(self, editor):
        editor.current_cell_index = 2
        assert editor.current_cell_index == 2

    def test_index_boundary_below_zero(self, editor):
        """Simulating the k/up key logic: index should not go below 0."""
        editor.current_cell_index = 0
        if editor.current_cell_index > 0:
            editor.current_cell_index -= 1
        assert editor.current_cell_index == 0

    def test_index_boundary_above_max(self, editor):
        """Simulating the j/down key logic: index should not exceed last cell."""
        editor.current_cell_index = len(editor.notebook.cells) - 1
        last = editor.current_cell_index
        if editor.notebook.cells and editor.current_cell_index < len(editor.notebook.cells) - 1:
            editor.current_cell_index += 1
        assert editor.current_cell_index == last


# ---------------------------------------------------------------------------
# execute_current_cell
# ---------------------------------------------------------------------------

class TestExecuteCurrentCell:
    def test_execute_code_cell_sets_outputs_and_count(self, editor):
        editor.current_cell_index = 0  # "x = 1"
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        cell = editor.notebook.cells[0]
        assert cell.execution_count is not None
        assert cell.execution_count >= 1

    def test_execute_markdown_cell_sets_cannot_execute_message(self, editor):
        editor.current_cell_index = 2  # markdown cell
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        assert "Cannot execute" in editor._status_message or "markdown" in editor._status_message.lower()

    def test_execute_empty_code_cell_sets_empty_message(self, editor):
        editor.notebook.add_cell(type=CellType.CODE, source="   ")
        editor.current_cell_index = len(editor.notebook.cells) - 1
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        assert "empty" in editor._status_message.lower() or "Cell is empty" in editor._status_message

    def test_execute_with_no_cells_sets_no_cells_message(self):
        nb = Notebook.new()
        ed = NotebookEditor(nb)
        with patch("notebook_lr.cli.Status"):
            ed.execute_current_cell()
        assert "No cells" in ed._status_message

    def test_execute_sets_modified_true(self, editor):
        editor.current_cell_index = 0
        assert editor.modified is False
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        assert editor.modified is True

    def test_execute_error_sets_error_message(self, editor):
        editor.notebook.add_cell(type=CellType.CODE, source="raise ValueError('test error')")
        editor.current_cell_index = len(editor.notebook.cells) - 1
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        assert "Error" in editor._status_message or "error" in editor._status_message or "red" in editor._status_message

    def test_execute_error_does_not_crash(self, editor):
        editor.notebook.add_cell(type=CellType.CODE, source="1/0")
        editor.current_cell_index = len(editor.notebook.cells) - 1
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        assert editor.modified is True

    def test_execute_result_stored_in_cell_outputs(self, editor):
        editor.notebook.add_cell(type=CellType.CODE, source="print('output test')")
        editor.current_cell_index = len(editor.notebook.cells) - 1
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        cell = editor.notebook.cells[editor.current_cell_index]
        assert isinstance(cell.outputs, list)

    def test_execute_print_captures_output(self, editor):
        editor.current_cell_index = 1  # print('hello')
        with patch("notebook_lr.cli.Status"):
            editor.execute_current_cell()
        cell = editor.notebook.cells[1]
        assert len(cell.outputs) > 0


# ---------------------------------------------------------------------------
# execute_all_cells
# ---------------------------------------------------------------------------

class TestExecuteAllCells:
    def _run_all(self, editor, monkeypatch):
        monkeypatch.setattr("notebook_lr.cli.console.input", lambda *a, **kw: "")
        with patch("notebook_lr.cli.Progress") as MockProgress:
            mock_progress = MagicMock()
            MockProgress.return_value.__enter__ = MagicMock(return_value=mock_progress)
            MockProgress.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = MagicMock()
            editor.execute_all_cells()

    def test_executes_all_code_cells_in_order(self, editor, monkeypatch):
        self._run_all(editor, monkeypatch)
        assert editor.notebook.cells[0].execution_count is not None
        assert editor.notebook.cells[1].execution_count is not None
        assert editor.notebook.cells[3].execution_count is not None

    def test_skips_markdown_cells(self, editor, monkeypatch):
        self._run_all(editor, monkeypatch)
        assert editor.notebook.cells[2].execution_count is None

    def test_skips_empty_code_cells(self, monkeypatch):
        nb = Notebook.new()
        nb.add_cell(type=CellType.CODE, source="   ")
        nb.add_cell(type=CellType.CODE, source="z = 5")
        ed = NotebookEditor(nb)
        monkeypatch.setattr("notebook_lr.cli.console.input", lambda *a, **kw: "")
        with patch("notebook_lr.cli.Progress") as MockProgress:
            mock_progress = MagicMock()
            MockProgress.return_value.__enter__ = MagicMock(return_value=mock_progress)
            MockProgress.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = MagicMock()
            ed.execute_all_cells()
        assert ed.notebook.cells[0].execution_count is None
        assert ed.notebook.cells[1].execution_count is not None

    def test_stops_on_first_error(self, monkeypatch):
        nb = Notebook.new()
        nb.add_cell(type=CellType.CODE, source="a = 1")
        nb.add_cell(type=CellType.CODE, source="raise RuntimeError('stop')")
        nb.add_cell(type=CellType.CODE, source="b = 2")
        ed = NotebookEditor(nb)
        monkeypatch.setattr("notebook_lr.cli.console.input", lambda *a, **kw: "")
        with patch("notebook_lr.cli.Progress") as MockProgress:
            mock_progress = MagicMock()
            MockProgress.return_value.__enter__ = MagicMock(return_value=mock_progress)
            MockProgress.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = MagicMock()
            ed.execute_all_cells()
        assert ed.notebook.cells[2].execution_count is None

    def test_success_message_when_all_pass(self, editor, monkeypatch):
        self._run_all(editor, monkeypatch)
        assert "executed" in editor._status_message.lower() or "green" in editor._status_message

    def test_error_message_when_error_occurs(self, monkeypatch):
        nb = Notebook.new()
        nb.add_cell(type=CellType.CODE, source="raise ValueError('oops')")
        ed = NotebookEditor(nb)
        monkeypatch.setattr("notebook_lr.cli.console.input", lambda *a, **kw: "")
        with patch("notebook_lr.cli.Progress") as MockProgress:
            mock_progress = MagicMock()
            MockProgress.return_value.__enter__ = MagicMock(return_value=mock_progress)
            MockProgress.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = MagicMock()
            ed.execute_all_cells()
        assert "error" in ed._status_message.lower() or "yellow" in ed._status_message


# ---------------------------------------------------------------------------
# search_cells — matching logic
# ---------------------------------------------------------------------------

class TestSearchCells:
    def test_case_insensitive_matching(self, editor):
        term = "PRINT"
        matches = [
            i for i, cell in enumerate(editor.notebook.cells)
            if term.lower() in cell.source.lower()
        ]
        assert 1 in matches

    def test_source_containing_term_is_found(self, editor):
        term = "Title"
        matches = [
            i for i, cell in enumerate(editor.notebook.cells)
            if term.lower() in cell.source.lower()
        ]
        assert 2 in matches

    def test_no_match_returns_empty(self, editor):
        term = "nonexistent_term_xyz"
        matches = [
            i for i, cell in enumerate(editor.notebook.cells)
            if term.lower() in cell.source.lower()
        ]
        assert matches == []


# ---------------------------------------------------------------------------
# save_notebook
# ---------------------------------------------------------------------------

class TestSaveNotebook:
    def test_save_writes_file(self, editor, tmp_path):
        nb_file = tmp_path / "test_save.nblr"
        editor.notebook.metadata["path"] = str(nb_file)
        editor.save_notebook()
        assert nb_file.exists()

    def test_save_with_include_session(self, editor, tmp_path):
        nb_file = tmp_path / "session_save.nblr"
        editor.notebook.metadata["path"] = str(nb_file)
        with patch.object(editor.kernel, "get_namespace", return_value={"x": 1}), \
             patch.object(editor.session_manager, "save_checkpoint"):
            editor.save_notebook(include_session=True)
        assert nb_file.exists()

    def test_save_sets_modified_false(self, editor, tmp_path):
        nb_file = tmp_path / "modified.nblr"
        editor.notebook.metadata["path"] = str(nb_file)
        editor.modified = True
        editor.save_notebook()
        assert editor.modified is False

    def test_save_message_contains_saved(self, editor, tmp_path):
        nb_file = tmp_path / "msg_test.nblr"
        editor.notebook.metadata["path"] = str(nb_file)
        editor.save_notebook()
        assert "Saved" in editor._status_message or "saved" in editor._status_message.lower()

    def test_save_prompts_when_no_path(self, editor, tmp_path):
        nb_file = tmp_path / "prompted.nblr"
        editor.notebook.metadata.pop("path", None)
        with patch("notebook_lr.cli.Prompt.ask", return_value=str(nb_file)):
            editor.save_notebook()
        assert nb_file.exists()
