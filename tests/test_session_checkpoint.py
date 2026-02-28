"""
Tests for SessionManager checkpoint and list operations.
"""

import pytest
import time
from pathlib import Path

from notebook_lr.kernel import NotebookKernel
from notebook_lr.session import SessionManager


# ---------------------------------------------------------------------------
# get_checkpoint_path
# ---------------------------------------------------------------------------

def test_get_checkpoint_path_under_sessions_checkpoints(tmp_path):
    """Returns path under sessions_dir/checkpoints/."""
    manager = SessionManager(sessions_dir=tmp_path)
    notebook_path = Path("/some/path/my_notebook.nblr")
    cp_path = manager.get_checkpoint_path(notebook_path)
    assert str(cp_path).startswith(str(tmp_path))
    assert cp_path.parent.name == "checkpoints"


def test_get_checkpoint_path_uses_stem_with_checkpoint_extension(tmp_path):
    """Uses notebook stem as filename with .checkpoint extension."""
    manager = SessionManager(sessions_dir=tmp_path)
    notebook_path = Path("/a/b/analysis.nblr")
    cp_path = manager.get_checkpoint_path(notebook_path)
    assert cp_path.stem == "analysis"
    assert cp_path.suffix == ".checkpoint"


def test_get_checkpoint_path_different_notebooks_produce_different_paths(tmp_path):
    """Different notebook paths produce different checkpoint paths."""
    manager = SessionManager(sessions_dir=tmp_path)
    path_a = manager.get_checkpoint_path(Path("/notebooks/alpha.nblr"))
    path_b = manager.get_checkpoint_path(Path("/notebooks/beta.nblr"))
    assert path_a != path_b
    assert path_a.stem == "alpha"
    assert path_b.stem == "beta"


# ---------------------------------------------------------------------------
# save_checkpoint
# ---------------------------------------------------------------------------

def test_save_checkpoint_creates_file(tmp_path):
    """save_checkpoint creates file at checkpoint path."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    notebook_path = tmp_path / "notebook.nblr"

    cp_path = manager.save_checkpoint(kernel, notebook_path)
    assert cp_path.exists()


def test_save_checkpoint_creates_checkpoints_directory(tmp_path):
    """save_checkpoint creates checkpoints directory."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    notebook_path = tmp_path / "notebook.nblr"

    cp_path = manager.save_checkpoint(kernel, notebook_path)
    assert cp_path.parent.is_dir()
    assert cp_path.parent.name == "checkpoints"


def test_save_checkpoint_with_populated_kernel_saves_state(tmp_path):
    """save_checkpoint with populated kernel saves state."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    kernel.execute_cell("x = 42")
    kernel.execute_cell("y = 'hello'")
    notebook_path = tmp_path / "populated.nblr"

    cp_path = manager.save_checkpoint(kernel, notebook_path)
    assert cp_path.exists()
    assert cp_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# load_checkpoint
# ---------------------------------------------------------------------------

def test_load_checkpoint_restores_state_from_checkpoint_file(tmp_path):
    """load_checkpoint restores state from checkpoint file."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    kernel.execute_cell("score = 99")
    notebook_path = tmp_path / "restore.nblr"
    manager.save_checkpoint(kernel, notebook_path)

    new_kernel = NotebookKernel()
    new_kernel.reset()
    info = manager.load_checkpoint(new_kernel, notebook_path)

    assert info is not None
    assert new_kernel.get_variable("score") == 99


def test_load_checkpoint_returns_none_when_no_checkpoint_exists(tmp_path):
    """load_checkpoint returns None when no checkpoint exists."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    notebook_path = tmp_path / "nonexistent.nblr"

    result = manager.load_checkpoint(kernel, notebook_path)
    assert result is None


def test_save_load_checkpoint_round_trip_preserves_data(tmp_path):
    """save_checkpoint then load_checkpoint round-trip preserves data."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    kernel.execute_cell("items = [1, 2, 3]")
    kernel.execute_cell("name = 'roundtrip'")
    notebook_path = tmp_path / "roundtrip.nblr"
    manager.save_checkpoint(kernel, notebook_path)

    new_kernel = NotebookKernel()
    new_kernel.reset()
    info = manager.load_checkpoint(new_kernel, notebook_path)

    assert info is not None
    assert new_kernel.get_variable("items") == [1, 2, 3]
    assert new_kernel.get_variable("name") == "roundtrip"


def test_load_checkpoint_restores_variables_into_kernel(tmp_path):
    """load_checkpoint restores variables into kernel."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    kernel.execute_cell("a = 10")
    kernel.execute_cell("b = 20")
    notebook_path = tmp_path / "vars.nblr"
    manager.save_checkpoint(kernel, notebook_path)

    new_kernel = NotebookKernel()
    new_kernel.reset()
    info = manager.load_checkpoint(new_kernel, notebook_path)

    assert "a" in info["restored_vars"]
    assert "b" in info["restored_vars"]
    assert new_kernel.get_variable("a") == 10
    assert new_kernel.get_variable("b") == 20


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

def test_list_sessions_returns_empty_list_when_no_sessions(tmp_path):
    """list_sessions returns empty list when no sessions."""
    manager = SessionManager(sessions_dir=tmp_path)
    assert manager.list_sessions() == []


def test_list_sessions_finds_session_files(tmp_path):
    """list_sessions finds .session files."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    manager.save_session(kernel, name="session_one")
    manager.save_session(kernel, name="session_two")

    sessions = manager.list_sessions()
    names = [s["name"] for s in sessions]
    assert "session_one" in names
    assert "session_two" in names


def test_list_sessions_sorted_by_saved_at_newest_first(tmp_path):
    """list_sessions returns sorted by saved_at (newest first)."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()

    manager.save_session(kernel, name="oldest")
    time.sleep(0.05)
    manager.save_session(kernel, name="middle")
    time.sleep(0.05)
    manager.save_session(kernel, name="newest")

    sessions = manager.list_sessions()
    names = [s["name"] for s in sessions]
    assert names[0] == "newest"
    assert names[-1] == "oldest"


def test_list_sessions_handles_corrupted_session_files_gracefully(tmp_path):
    """list_sessions handles corrupted session files gracefully (includes error key)."""
    manager = SessionManager(sessions_dir=tmp_path)
    corrupt_file = tmp_path / "corrupt.session"
    corrupt_file.write_bytes(b"not valid dill data!!!!")

    sessions = manager.list_sessions()
    corrupt = next((s for s in sessions if s["name"] == "corrupt"), None)
    assert corrupt is not None
    assert "error" in corrupt


def test_list_sessions_returns_required_fields_for_valid_sessions(tmp_path):
    """list_sessions returns name, path, saved_at, var_count for valid sessions."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    kernel.execute_cell("val = 1")
    manager.save_session(kernel, name="complete_info")

    sessions = manager.list_sessions()
    session = next(s for s in sessions if s["name"] == "complete_info")

    assert "name" in session
    assert "path" in session
    assert "saved_at" in session
    assert "var_count" in session
    assert session["name"] == "complete_info"
    assert session["saved_at"] is not None
    assert session["var_count"] >= 1


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

def test_delete_session_returns_true_and_removes_file(tmp_path):
    """delete_session returns True and removes file."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    path = manager.save_session(kernel, name="to_delete")

    assert path.exists()
    result = manager.delete_session(path)
    assert result is True
    assert not path.exists()


def test_delete_session_returns_false_for_nonexistent_path(tmp_path):
    """delete_session returns False for non-existent path."""
    manager = SessionManager(sessions_dir=tmp_path)
    nonexistent = tmp_path / "does_not_exist.session"

    result = manager.delete_session(nonexistent)
    assert result is False


def test_after_delete_session_list_sessions_no_longer_includes_it(tmp_path):
    """After delete_session, list_sessions no longer includes it."""
    manager = SessionManager(sessions_dir=tmp_path)
    kernel = NotebookKernel()
    path = manager.save_session(kernel, name="gone")
    manager.save_session(kernel, name="stays")

    manager.delete_session(path)

    sessions = manager.list_sessions()
    names = [s["name"] for s in sessions]
    assert "gone" not in names
    assert "stays" in names


# ---------------------------------------------------------------------------
# SessionManager init
# ---------------------------------------------------------------------------

def test_default_sessions_dir_is_in_home():
    """Default sessions_dir is ~/.notebook_lr/sessions."""
    manager = SessionManager()
    expected = Path.home() / ".notebook_lr" / "sessions"
    assert manager.sessions_dir == expected


def test_custom_sessions_dir_is_used_and_created(tmp_path):
    """Custom sessions_dir is used and created."""
    custom_dir = tmp_path / "my_sessions"
    assert not custom_dir.exists()

    manager = SessionManager(sessions_dir=custom_dir)
    assert manager.sessions_dir == custom_dir
    assert custom_dir.exists()
    assert custom_dir.is_dir()
