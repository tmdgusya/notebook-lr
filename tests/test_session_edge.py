"""
Edge case tests for SessionManager save/load operations.
"""

import dill
import pytest
from pathlib import Path

from notebook_lr.kernel import NotebookKernel, ExecutionResult
from notebook_lr.session import SessionManager


@pytest.fixture
def sm(tmp_path):
    return SessionManager(sessions_dir=tmp_path)


@pytest.fixture
def kernel():
    return NotebookKernel()


# --- save_session edge cases ---

def test_save_unpicklable_filtered_and_listed(sm, kernel, tmp_path):
    """Unpicklable objects (open file handle) are excluded and listed in unpicklable_vars."""
    import socket
    kernel.set_variable("good", 42)
    sock = socket.socket()
    kernel.set_variable("bad_sock", sock)

    path = sm.save_session(kernel, name="unp")
    sock.close()

    with open(path, "rb") as f:
        state = dill.load(f)

    assert "good" in state["user_ns"]
    assert "bad_sock" not in state["user_ns"]
    assert "bad_sock" in state["unpicklable_vars"]


def test_save_large_namespace(sm, kernel, tmp_path):
    """Saving a kernel with 100+ variables works correctly."""
    for i in range(120):
        kernel.set_variable(f"var_{i}", i * 2)

    path = sm.save_session(kernel, name="large")
    assert path.exists()

    new_kernel = NotebookKernel()
    info = sm.load_session(new_kernel, path)

    assert len(info["restored_vars"]) >= 120
    assert new_kernel.get_variable("var_0") == 0
    assert new_kernel.get_variable("var_99") == 198
    assert new_kernel.get_variable("var_119") == 238


def test_save_with_name_generates_correct_filename(sm, kernel, tmp_path):
    """save_session with name= stores file as <sessions_dir>/<name>.session."""
    path = sm.save_session(kernel, name="mytest")
    assert path == tmp_path / "mytest.session"
    assert path.exists()


def test_save_without_name_generates_timestamped_filename(sm, kernel):
    """save_session without name generates a timestamped filename."""
    path = sm.save_session(kernel)
    assert path.exists()
    assert path.suffix == ".session"
    assert "session_" in path.stem


def test_save_with_explicit_path(sm, kernel, tmp_path):
    """save_session with path= uses that exact path."""
    explicit = tmp_path / "subdir" / "custom.session"
    path = sm.save_session(kernel, path=explicit)
    assert path == explicit
    assert path.exists()


def test_save_creates_parent_directories(sm, kernel, tmp_path):
    """save_session creates missing parent directories."""
    deep = tmp_path / "a" / "b" / "c" / "deep.session"
    path = sm.save_session(kernel, path=deep)
    assert path.exists()


def test_save_captures_execution_count(sm, kernel, tmp_path):
    """save_session stores the kernel's execution_count in the session file."""
    kernel.execute_cell("x = 1")
    kernel.execute_cell("y = 2")
    assert kernel.execution_count == 2

    path = sm.save_session(kernel, name="ec")

    with open(path, "rb") as f:
        state = dill.load(f)

    assert state["execution_count"] == 2


def test_save_captures_history_with_to_dict(sm, kernel, tmp_path):
    """save_session stores history as (count, code, result_dict) tuples."""
    kernel.execute_cell("a = 10")
    path = sm.save_session(kernel, name="hist")

    with open(path, "rb") as f:
        state = dill.load(f)

    assert len(state["history"]) == 1
    count, code, result_dict = state["history"][0]
    assert count == 1
    assert code == "a = 10"
    # result_dict should be the output of ExecutionResult.to_dict()
    assert isinstance(result_dict, dict)
    assert "success" in result_dict
    assert "outputs" in result_dict
    assert "execution_count" in result_dict


# --- load_session edge cases ---

def test_load_restores_picklable_variables(sm, kernel, tmp_path):
    """load_session restores all picklable variables into the kernel."""
    kernel.execute_cell("n = 7")
    kernel.execute_cell("s = 'hello'")
    kernel.execute_cell("lst = [1, 2, 3]")
    path = sm.save_session(kernel, name="vars")

    new_kernel = NotebookKernel()
    sm.load_session(new_kernel, path)

    assert new_kernel.get_variable("n") == 7
    assert new_kernel.get_variable("s") == "hello"
    assert new_kernel.get_variable("lst") == [1, 2, 3]


def test_load_restores_execution_count(sm, kernel, tmp_path):
    """load_session restores the saved execution_count."""
    kernel.execute_cell("x = 1")
    kernel.execute_cell("y = 2")
    kernel.execute_cell("z = 3")
    path = sm.save_session(kernel, name="ec_restore")

    new_kernel = NotebookKernel()
    sm.load_session(new_kernel, path)

    assert new_kernel.execution_count == 3


def test_load_restores_history_as_execution_result_objects(sm, kernel, tmp_path):
    """load_session restores history entries as ExecutionResult instances."""
    kernel.execute_cell("a = 1")
    kernel.execute_cell("b = 2")
    path = sm.save_session(kernel, name="hist_restore")

    new_kernel = NotebookKernel()
    sm.load_session(new_kernel, path)

    history = new_kernel.get_history()
    assert len(history) == 2
    assert isinstance(history[0][2], ExecutionResult)
    assert isinstance(history[1][2], ExecutionResult)
    assert history[0][1] == "a = 1"
    assert history[1][1] == "b = 2"


def test_load_reports_unpicklable_vars(sm, kernel, tmp_path):
    """load_session info includes unpicklable_vars that were skipped during save."""
    import socket
    kernel.set_variable("ok", 1)
    sock = socket.socket()
    kernel.set_variable("bad", sock)
    path = sm.save_session(kernel, name="unp_load")
    sock.close()

    new_kernel = NotebookKernel()
    info = sm.load_session(new_kernel, path)

    assert "bad" in info["unpicklable_vars"]
    assert "ok" in info["restored_vars"]


def test_load_reports_saved_at_timestamp(sm, kernel, tmp_path):
    """load_session info includes a non-empty saved_at timestamp."""
    path = sm.save_session(kernel, name="ts")

    new_kernel = NotebookKernel()
    info = sm.load_session(new_kernel, path)

    assert "saved_at" in info
    assert info["saved_at"]  # non-empty string


def test_load_nonexistent_file_raises(sm, kernel, tmp_path):
    """load_session raises FileNotFoundError for a missing path."""
    missing = tmp_path / "ghost.session"
    with pytest.raises(FileNotFoundError):
        sm.load_session(kernel, missing)


# --- complex type round-trips ---

def test_save_load_list_of_lists(sm, kernel, tmp_path):
    """Save/load numpy-like array (list of lists) preserves structure."""
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    kernel.set_variable("matrix", matrix)
    path = sm.save_session(kernel, name="matrix")

    new_kernel = NotebookKernel()
    sm.load_session(new_kernel, path)

    result = new_kernel.get_variable("matrix")
    assert result == matrix
    assert result[1][2] == 6


def test_save_load_nested_dicts(sm, kernel, tmp_path):
    """Save/load deeply nested dicts preserves all values."""
    data = {"outer": {"middle": {"inner": [1, 2, {"deep": True}]}}}
    kernel.set_variable("data", data)
    path = sm.save_session(kernel, name="nested")

    new_kernel = NotebookKernel()
    sm.load_session(new_kernel, path)

    result = new_kernel.get_variable("data")
    assert result["outer"]["middle"]["inner"][2]["deep"] is True


def test_save_load_class_instances(sm, kernel, tmp_path):
    """Save/load custom class instances via dill preserves type and attributes."""
    kernel.execute_cell("""
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
p = Point(3, 7)
""")
    path = sm.save_session(kernel, name="cls")

    new_kernel = NotebookKernel()
    sm.load_session(new_kernel, path)

    p = new_kernel.get_variable("p")
    assert p is not None
    assert p.x == 3
    assert p.y == 7


def test_save_load_functions_defined_in_cells(sm, kernel, tmp_path):
    """Save/load functions defined in executed cells via dill."""
    kernel.execute_cell("""
def multiply(a, b):
    return a * b
""")
    path = sm.save_session(kernel, name="func")

    new_kernel = NotebookKernel()
    sm.load_session(new_kernel, path)

    fn = new_kernel.get_variable("multiply")
    assert fn is not None
    assert fn(4, 5) == 20
