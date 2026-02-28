"""
Tests for error handling in NotebookKernel.execute_cell().
"""

import pytest
from notebook_lr.kernel import NotebookKernel


class TestExecuteCellErrorPaths:
    """Test error handling paths in NotebookKernel.execute_cell()."""

    def setup_method(self):
        self.kernel = NotebookKernel()

    def test_syntax_error(self):
        """SyntaxError in code: IPython prints error to stdout but run_cell reports success.
        The SyntaxError message appears in stdout stream output."""
        result = self.kernel.execute_cell("x = @invalid")
        # IPython handles SyntaxError by printing to stdout; error_in_exec is not set
        # So success=True but the error text appears in stream output
        stdout_outputs = [o for o in result.outputs if o.get("type") == "stream" and o.get("name") == "stdout"]
        assert len(stdout_outputs) > 0
        assert "SyntaxError" in stdout_outputs[0].get("text", "")

    def test_name_error(self):
        """NameError for undefined variable results in failed execution."""
        result = self.kernel.execute_cell("undefined_variable_xyz")
        assert not result.success
        assert result.error is not None
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "NameError" in error_outputs[0].get("ename", "")

    def test_type_error(self):
        """TypeError results in failed execution."""
        result = self.kernel.execute_cell("1 + 'string'")
        assert not result.success
        assert result.error is not None
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "TypeError" in error_outputs[0].get("ename", "")

    def test_zero_division_error(self):
        """ZeroDivisionError results in failed execution."""
        result = self.kernel.execute_cell("1 / 0")
        assert not result.success
        assert result.error is not None
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "ZeroDivisionError" in error_outputs[0].get("ename", "")

    def test_import_error(self):
        """ImportError for nonexistent module results in failed execution."""
        result = self.kernel.execute_cell("import nonexistent_module_xyz_abc")
        assert not result.success
        assert result.error is not None
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "Error" in error_outputs[0].get("ename", "")

    def test_value_error(self):
        """ValueError results in failed execution."""
        result = self.kernel.execute_cell("int('abc')")
        assert not result.success
        assert result.error is not None
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "ValueError" in error_outputs[0].get("ename", "")

    def test_custom_exception(self):
        """Custom exception class results in failed execution."""
        code = "class MyError(Exception):\n    pass\nraise MyError('custom error')"
        result = self.kernel.execute_cell(code)
        assert not result.success
        assert result.error is not None
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "MyError" in error_outputs[0].get("ename", "")

    def test_stdout_output_before_error(self):
        """Code that prints then raises captures stdout AND records error."""
        code = 'print("before error")\nraise ValueError("oops")'
        result = self.kernel.execute_cell(code)
        assert not result.success
        assert result.error is not None
        stdout_outputs = [o for o in result.outputs if o.get("type") == "stream" and o.get("name") == "stdout"]
        assert len(stdout_outputs) > 0
        assert "before error" in stdout_outputs[0].get("text", "")
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0

    def test_stderr_output(self):
        """Code that emits a warning does not crash and returns a result."""
        code = "import warnings\nwarnings.warn('test warning')"
        result = self.kernel.execute_cell(code)
        assert result is not None
        assert result.execution_count >= 1

    def test_empty_string_execution(self):
        """Executing empty string succeeds with no error."""
        result = self.kernel.execute_cell("")
        assert result.success
        assert result.error is None

    def test_whitespace_only_execution(self):
        """Executing whitespace-only code succeeds with no error."""
        result = self.kernel.execute_cell("   \n\t  \n  ")
        assert result.success
        assert result.error is None

    def test_display_call_from_ipython(self):
        """Code that calls display() from IPython captures display_data output."""
        code = "from IPython.display import display\ndisplay('hello display')"
        result = self.kernel.execute_cell(code)
        assert result.success
        display_outputs = [o for o in result.outputs if o.get("type") == "display_data"]
        assert len(display_outputs) > 0

    def test_multiple_sequential_errors_kernel_survives(self):
        """Kernel remains functional after multiple sequential errors."""
        self.kernel.execute_cell("1 / 0")
        self.kernel.execute_cell("undefined_var")
        self.kernel.execute_cell("int('bad')")
        result = self.kernel.execute_cell("x = 42")
        assert result.success
        assert self.kernel.get_variable("x") == 42

    def test_execution_count_increments_on_error(self):
        """execution_count increments even when execution fails."""
        initial = self.kernel.execution_count
        result = self.kernel.execute_cell("1 / 0")
        assert not result.success
        assert self.kernel.execution_count == initial + 1
        assert result.execution_count == initial + 1

    def test_error_field_set_on_failure(self):
        """error field is non-None on failed execution."""
        result = self.kernel.execute_cell("raise RuntimeError('fail')")
        assert not result.success
        assert result.error is not None

    def test_error_field_none_on_success(self):
        """error field is None on successful execution."""
        result = self.kernel.execute_cell("x = 1 + 1")
        assert result.success
        assert result.error is None

    def test_error_output_has_ename_and_evalue(self):
        """Error output dict contains ename and evalue fields."""
        result = self.kernel.execute_cell("raise ValueError('test msg')")
        assert not result.success
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        err = error_outputs[0]
        assert "ename" in err
        assert "evalue" in err
        assert "ValueError" in err["ename"]

    def test_error_output_has_traceback_field(self):
        """Error output dict contains a traceback field (list)."""
        result = self.kernel.execute_cell("raise KeyError('missing')")
        assert not result.success
        error_outputs = [o for o in result.outputs if o.get("type") == "error"]
        assert len(error_outputs) > 0
        assert "traceback" in error_outputs[0]
        assert isinstance(error_outputs[0]["traceback"], list)

    def test_namespace_preserved_after_error(self):
        """Variables defined before an error remain in namespace."""
        self.kernel.execute_cell("good_var = 100")
        self.kernel.execute_cell("raise RuntimeError('oops')")
        assert self.kernel.get_variable("good_var") == 100

    def test_history_records_failed_execution(self):
        """Failed executions are recorded in history."""
        self.kernel.execute_cell("1 / 0")
        history = self.kernel.get_history()
        assert len(history) == 1
        count, code, exec_result = history[0]
        assert code == "1 / 0"
        assert not exec_result.success
