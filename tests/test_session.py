"""
Tests for SessionManager.
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from notebook_lr.kernel import NotebookKernel
from notebook_lr.session import SessionManager


class TestSessionManager:
    """Test cases for SessionManager."""

    def setup_method(self):
        """Set up a fresh session manager for each test."""
        self.temp_dir = TemporaryDirectory()
        self.session_manager = SessionManager(sessions_dir=Path(self.temp_dir.name))

    def teardown_method(self):
        """Clean up temp directory."""
        self.temp_dir.cleanup()

    def test_save_and_load_session(self):
        """Test saving and loading a kernel session."""
        kernel = NotebookKernel()
        kernel.execute_cell("x = 42")
        kernel.execute_cell("y = x + 8")

        # Save session
        path = self.session_manager.save_session(kernel, name="test_session")
        assert path.exists()

        # Create new kernel and load session
        new_kernel = NotebookKernel()
        info = self.session_manager.load_session(new_kernel, path)

        assert "x" in info["restored_vars"]
        assert "y" in info["restored_vars"]
        assert new_kernel.get_variable("x") == 42
        assert new_kernel.get_variable("y") == 50

    def test_session_with_functions(self):
        """Test saving session with functions."""
        kernel = NotebookKernel()
        kernel.execute_cell("""
def add(a, b):
    return a + b
result = add(3, 4)
""")

        path = self.session_manager.save_session(kernel, name="func_session")

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        # Function should be restored
        add_func = new_kernel.get_variable("add")
        assert add_func is not None
        assert add_func(1, 2) == 3
        assert new_kernel.get_variable("result") == 7

    def test_session_with_imports(self):
        """Test saving session with imports."""
        kernel = NotebookKernel()
        kernel.execute_cell("import math")
        kernel.execute_cell("pi = math.pi")

        path = self.session_manager.save_session(kernel, name="import_session")

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        # math module should be in namespace
        math_module = new_kernel.get_variable("math")
        assert math_module is not None
        assert new_kernel.get_variable("pi") == 3.141592653589793

    def test_session_with_classes(self):
        """Test saving session with custom classes."""
        kernel = NotebookKernel()
        kernel.execute_cell("""
class Person:
    def __init__(self, name):
        self.name = name

p = Person("Alice")
""")

        path = self.session_manager.save_session(kernel, name="class_session")

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        Person = new_kernel.get_variable("Person")
        p = new_kernel.get_variable("p")

        assert Person is not None
        assert p is not None
        assert p.name == "Alice"

    def test_session_execution_count_restored(self):
        """Test that execution count is restored."""
        kernel = NotebookKernel()
        kernel.execute_cell("x = 1")
        kernel.execute_cell("y = 2")
        kernel.execute_cell("z = 3")

        path = self.session_manager.save_session(kernel)

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        assert new_kernel.execution_count == 3

    def test_session_history_restored(self):
        """Test that history is restored."""
        kernel = NotebookKernel()
        kernel.execute_cell("a = 1")
        kernel.execute_cell("b = 2")

        path = self.session_manager.save_session(kernel)

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        history = new_kernel.get_history()
        assert len(history) == 2
        assert history[0][1] == "a = 1"
        assert history[1][1] == "b = 2"

    def test_list_sessions(self):
        """Test listing sessions."""
        kernel = NotebookKernel()
        kernel.execute_cell("x = 1")

        self.session_manager.save_session(kernel, name="session1")
        self.session_manager.save_session(kernel, name="session2")

        sessions = self.session_manager.list_sessions()

        assert len(sessions) >= 2
        names = [s["name"] for s in sessions]
        assert "session1" in names
        assert "session2" in names

    def test_delete_session(self):
        """Test deleting a session."""
        kernel = NotebookKernel()
        path = self.session_manager.save_session(kernel, name="to_delete")

        assert path.exists()

        result = self.session_manager.delete_session(path)

        assert result is True
        assert not path.exists()

    def test_checkpoint_save_and_load(self):
        """Test checkpoint functionality."""
        kernel = NotebookKernel()
        kernel.execute_cell("x = 100")

        notebook_path = Path(self.temp_dir.name) / "test.nblr"
        checkpoint_path = self.session_manager.save_checkpoint(kernel, notebook_path)

        assert checkpoint_path.exists()

        new_kernel = NotebookKernel()
        info = self.session_manager.load_checkpoint(new_kernel, notebook_path)

        assert info is not None
        assert new_kernel.get_variable("x") == 100

    def test_checkpoint_not_found(self):
        """Test loading checkpoint when none exists."""
        kernel = NotebookKernel()
        notebook_path = Path(self.temp_dir.name) / "no_checkpoint.nblr"

        info = self.session_manager.load_checkpoint(kernel, notebook_path)

        assert info is None

    def test_session_with_complex_data(self):
        """Test saving session with complex data structures."""
        kernel = NotebookKernel()
        kernel.execute_cell("""
data = {
    "name": "test",
    "values": [1, 2, 3],
    "nested": {"a": 1, "b": 2}
}
""")

        path = self.session_manager.save_session(kernel, name="complex_session")

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        data = new_kernel.get_variable("data")
        assert data["name"] == "test"
        assert data["values"] == [1, 2, 3]
        assert data["nested"]["a"] == 1

    def test_session_with_lists(self):
        """Test saving session with lists."""
        kernel = NotebookKernel()
        kernel.execute_cell("items = [1, 2, 3, 4, 5]")
        kernel.execute_cell("doubled = [x * 2 for x in items]")

        path = self.session_manager.save_session(kernel)

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        assert new_kernel.get_variable("items") == [1, 2, 3, 4, 5]
        assert new_kernel.get_variable("doubled") == [2, 4, 6, 8, 10]

    def test_custom_session_path(self):
        """Test saving to a custom path."""
        kernel = NotebookKernel()
        kernel.execute_cell("x = 42")

        custom_path = Path(self.temp_dir.name) / "custom" / "my.session"
        path = self.session_manager.save_session(kernel, path=custom_path)

        assert path == custom_path
        assert path.exists()

        new_kernel = NotebookKernel()
        self.session_manager.load_session(new_kernel, path)

        assert new_kernel.get_variable("x") == 42
