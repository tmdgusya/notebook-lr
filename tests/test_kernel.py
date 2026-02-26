"""
Tests for NotebookKernel.
"""

import pytest
from notebook_lr.kernel import NotebookKernel, ExecutionResult


class TestNotebookKernel:
    """Test cases for NotebookKernel."""

    def setup_method(self):
        """Set up a fresh kernel for each test."""
        self.kernel = NotebookKernel()

    def test_execute_simple_code(self):
        """Test executing simple code."""
        result = self.kernel.execute_cell("x = 42")

        assert result.success
        assert result.execution_count == 1

    def test_execute_and_retrieve_variable(self):
        """Test that variables persist across executions."""
        self.kernel.execute_cell("x = 42")
        self.kernel.execute_cell("y = x + 8")

        x = self.kernel.get_variable("x")
        y = self.kernel.get_variable("y")

        assert x == 42
        assert y == 50

    def test_execute_with_output(self):
        """Test capturing stdout."""
        result = self.kernel.execute_cell('print("Hello, World!")')

        assert result.success
        assert len(result.outputs) > 0

        # Check for stdout output
        stdout_outputs = [o for o in result.outputs if o.get("type") == "stream" and o.get("name") == "stdout"]
        assert len(stdout_outputs) > 0
        assert "Hello, World!" in stdout_outputs[0].get("text", "")

    def test_execute_with_error(self):
        """Test error handling."""
        result = self.kernel.execute_cell("1 / 0")

        assert not result.success
        assert result.error is not None
        # Error info is in outputs
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "ZeroDivisionError" in error_outputs[0].get("ename", "")

    def test_execute_return_value(self):
        """Test capturing return values."""
        result = self.kernel.execute_cell("2 + 2")

        assert result.success
        assert result.return_value == 4

    def test_import_persistence(self):
        """Test that imports persist across cells."""
        self.kernel.execute_cell("import math")
        result = self.kernel.execute_cell("math.sqrt(16)")

        assert result.success
        assert result.return_value == 4.0

    def test_get_namespace(self):
        """Test getting the namespace."""
        self.kernel.execute_cell("a = 1")
        self.kernel.execute_cell("b = 2")

        ns = self.kernel.get_namespace()

        assert "a" in ns
        assert "b" in ns
        assert ns["a"] == 1
        assert ns["b"] == 2

    def test_restore_namespace(self):
        """Test restoring namespace."""
        # Set up variables in one kernel
        self.kernel.execute_cell("x = 100")
        ns = self.kernel.get_namespace()

        # Create new kernel and restore
        new_kernel = NotebookKernel()
        new_kernel.restore_namespace(ns)

        assert new_kernel.get_variable("x") == 100

    def test_execution_count_increments(self):
        """Test that execution count increments correctly."""
        assert self.kernel.execution_count == 0

        self.kernel.execute_cell("x = 1")
        assert self.kernel.execution_count == 1

        self.kernel.execute_cell("y = 2")
        assert self.kernel.execution_count == 2

    def test_history_tracking(self):
        """Test that history is tracked."""
        self.kernel.execute_cell("a = 1")
        self.kernel.execute_cell("b = 2")

        history = self.kernel.get_history()

        assert len(history) == 2
        assert history[0][1] == "a = 1"
        assert history[1][1] == "b = 2"

    def test_reset_kernel(self):
        """Test resetting the kernel."""
        self.kernel.execute_cell("x = 42")
        self.kernel.reset()

        assert self.kernel.execution_count == 0
        assert self.kernel.get_variable("x") is None

    def test_set_and_get_variable(self):
        """Test setting and getting variables directly."""
        self.kernel.set_variable("test_var", 123)
        assert self.kernel.get_variable("test_var") == 123

    def test_delete_variable(self):
        """Test deleting variables."""
        self.kernel.execute_cell("x = 42")
        self.kernel.del_variable("x")

        assert self.kernel.get_variable("x") is None

    def test_defined_names(self):
        """Test getting defined names."""
        self.kernel.execute_cell("a = 1")
        self.kernel.execute_cell("b = 2")

        names = self.kernel.get_defined_names()

        assert "a" in names
        assert "b" in names

    def test_expression_output_after_assignment(self):
        """cell[1]에서 x=1 후 cell[2]에서 x를 평가하면 출력이 나와야 함."""
        self.kernel.execute_cell("x = 1")
        result = self.kernel.execute_cell("x")
        assert result.success
        assert result.return_value == 1
        # execute_result 출력이 존재해야 함
        exec_results = [o for o in result.outputs if o["type"] == "execute_result"]
        assert len(exec_results) > 0
        assert exec_results[0]["data"]["text/plain"] == "1"

    def test_multiline_code(self):
        """Test executing multiline code."""
        code = """
def greet(name):
    return f"Hello, {name}!"

message = greet("World")
"""
        result = self.kernel.execute_cell(code)

        assert result.success
        assert self.kernel.get_variable("message") == "Hello, World!"


class TestDisplayObjects:
    """Tests for IPython display object handling (HTML, Markdown, JSON, etc.).

    These tests document the expected behaviour: display objects should produce
    rich MIME-type data dicts rather than repr strings like
    '<IPython.core.display.HTML object>'.
    """

    def setup_method(self):
        """Set up a fresh kernel for each test."""
        self.kernel = NotebookKernel()
        self.kernel.reset()

    def _execute_result_outputs(self, result):
        return [o for o in result.outputs if o.get("type") == "execute_result"]

    def test_html_display_object_has_html_mime_type(self):
        """HTML() should produce a text/html key in the output data dict."""
        result = self.kernel.execute_cell(
            'from IPython.display import HTML\nHTML("<h1>Test</h1>")'
        )
        assert result.success
        exec_results = self._execute_result_outputs(result)
        assert len(exec_results) > 0, "Expected an execute_result output"
        data = exec_results[0]["data"]
        assert "text/html" in data, (
            f"Expected 'text/html' key in data dict, got keys: {list(data.keys())}"
        )
        assert "<h1>Test</h1>" in data["text/html"], (
            f"Expected actual HTML content in text/html, got: {data['text/html']!r}"
        )

    def test_html_display_object_not_repr_string(self):
        """Output text/plain must NOT be the IPython repr string."""
        result = self.kernel.execute_cell(
            'from IPython.display import HTML\nHTML("<h1>Test</h1>")'
        )
        assert result.success
        exec_results = self._execute_result_outputs(result)
        assert len(exec_results) > 0
        data = exec_results[0]["data"]
        plain = data.get("text/plain", "")
        assert "<IPython.core.display.HTML object>" not in plain, (
            "text/plain must not be the repr string of the display object"
        )

    def test_markdown_display_object(self):
        """Markdown() should produce a text/markdown key in the output data."""
        result = self.kernel.execute_cell(
            'from IPython.display import Markdown\nMarkdown("**bold**")'
        )
        assert result.success
        exec_results = self._execute_result_outputs(result)
        assert len(exec_results) > 0, "Expected an execute_result output"
        data = exec_results[0]["data"]
        assert "text/markdown" in data, (
            f"Expected 'text/markdown' key in data dict, got keys: {list(data.keys())}"
        )
        assert "**bold**" in data["text/markdown"]

    def test_json_display_object(self):
        """JSON() should produce an application/json key in the output data."""
        result = self.kernel.execute_cell(
            'from IPython.display import JSON\nJSON({"key": "value"})'
        )
        assert result.success
        exec_results = self._execute_result_outputs(result)
        assert len(exec_results) > 0, "Expected an execute_result output"
        data = exec_results[0]["data"]
        assert "application/json" in data, (
            f"Expected 'application/json' key in data dict, got keys: {list(data.keys())}"
        )

    def test_display_object_has_plain_fallback(self):
        """Display objects should also expose text/plain as a fallback."""
        result = self.kernel.execute_cell(
            'from IPython.display import HTML\nHTML("<b>hello</b>")'
        )
        assert result.success
        exec_results = self._execute_result_outputs(result)
        assert len(exec_results) > 0
        data = exec_results[0]["data"]
        # text/plain must exist and not be the ugly repr
        assert "text/plain" in data, "Expected text/plain fallback in data dict"
        assert "<IPython.core.display.HTML object>" not in data["text/plain"], (
            "text/plain fallback must not be the repr string"
        )


class TestExecutionResult:
    """Test cases for ExecutionResult."""

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ExecutionResult(
            success=True,
            outputs=[{"type": "stream", "text": "output"}],
            execution_count=1,
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["execution_count"] == 1
        assert len(d["outputs"]) == 1

    def test_from_dict(self):
        """Test creating result from dictionary."""
        d = {
            "success": True,
            "outputs": [{"type": "stream", "text": "output"}],
            "execution_count": 2,
            "error": None,
        }

        result = ExecutionResult.from_dict(d)

        assert result.success is True
        assert result.execution_count == 2
