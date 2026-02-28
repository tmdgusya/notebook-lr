"""
Comprehensive tests for ExecutionResult in notebook_lr/kernel.py.
"""

import pytest
from notebook_lr.kernel import ExecutionResult


class TestExecutionResultToDict:
    """Tests for ExecutionResult.to_dict()."""

    def test_to_dict_all_fields_populated(self):
        """to_dict() with all fields populated (success=True)."""
        outputs = [
            {"type": "stream", "name": "stdout", "text": "hello\n"},
            {"type": "execute_result", "data": {"text/plain": "42"}, "execution_count": 1},
        ]
        result = ExecutionResult(
            success=True,
            outputs=outputs,
            execution_count=1,
            return_value=42,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["outputs"] == outputs
        assert d["execution_count"] == 1
        assert d["return_value"] == "42"
        assert d["error"] is None

    def test_to_dict_with_error(self):
        """to_dict() with error (success=False, error string)."""
        outputs = [
            {"type": "error", "ename": "ZeroDivisionError", "evalue": "division by zero", "traceback": []}
        ]
        result = ExecutionResult(
            success=False,
            outputs=outputs,
            execution_count=2,
            error="ZeroDivisionError: division by zero",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "ZeroDivisionError: division by zero"
        assert d["return_value"] is None
        assert len(d["outputs"]) == 1

    def test_to_dict_return_value_none_serializes_as_none(self):
        """to_dict() with return_value=None should serialize as None."""
        result = ExecutionResult(success=True, outputs=[], execution_count=1, return_value=None)
        d = result.to_dict()
        assert d["return_value"] is None

    def test_to_dict_complex_return_value_becomes_str(self):
        """to_dict() with complex return_value should be str()."""
        result = ExecutionResult(
            success=True, outputs=[], execution_count=1, return_value={"key": [1, 2, 3]}
        )
        d = result.to_dict()
        assert isinstance(d["return_value"], str)
        assert d["return_value"] == str({"key": [1, 2, 3]})

    def test_to_dict_list_return_value(self):
        result = ExecutionResult(success=True, outputs=[], execution_count=1, return_value=[1, 2, 3])
        d = result.to_dict()
        assert d["return_value"] == "[1, 2, 3]"

    def test_to_dict_float_return_value(self):
        result = ExecutionResult(success=True, outputs=[], execution_count=1, return_value=3.14)
        d = result.to_dict()
        assert d["return_value"] == "3.14"

    def test_to_dict_contains_all_required_keys(self):
        result = ExecutionResult(success=True, outputs=[], execution_count=0)
        d = result.to_dict()
        assert set(d.keys()) == {"success", "outputs", "execution_count", "error", "return_value"}

    def test_to_dict_with_stream_output(self):
        outputs = [{"type": "stream", "name": "stdout", "text": "output\n"}]
        result = ExecutionResult(success=True, outputs=outputs, execution_count=1)
        d = result.to_dict()
        assert d["outputs"][0]["type"] == "stream"
        assert d["outputs"][0]["text"] == "output\n"

    def test_to_dict_with_display_data_output(self):
        outputs = [{"type": "display_data", "data": {"text/html": "<b>hi</b>", "text/plain": "<b>hi</b>"}}]
        result = ExecutionResult(success=True, outputs=outputs, execution_count=1)
        d = result.to_dict()
        assert d["outputs"][0]["type"] == "display_data"
        assert "text/html" in d["outputs"][0]["data"]


class TestExecutionResultFromDict:
    """Tests for ExecutionResult.from_dict()."""

    def test_from_dict_round_trip(self):
        """Round-trip: create result, to_dict, from_dict, verify equality."""
        original = ExecutionResult(
            success=True,
            outputs=[{"type": "stream", "name": "stdout", "text": "hi\n"}],
            execution_count=3,
            error=None,
            return_value=None,
        )
        d = original.to_dict()
        restored = ExecutionResult.from_dict(d)

        assert restored.success == original.success
        assert restored.outputs == original.outputs
        assert restored.execution_count == original.execution_count
        assert restored.error == original.error
        assert restored.return_value == original.return_value

    def test_from_dict_missing_optional_error_defaults_to_none(self):
        """from_dict() with missing optional field 'error' defaults to None."""
        d = {"success": True, "outputs": [], "execution_count": 1}
        result = ExecutionResult.from_dict(d)
        assert result.error is None

    def test_from_dict_missing_optional_return_value_defaults_to_none(self):
        """from_dict() with missing optional field 'return_value' defaults to None."""
        d = {"success": True, "outputs": [], "execution_count": 1}
        result = ExecutionResult.from_dict(d)
        assert result.return_value is None

    def test_from_dict_empty_outputs_list(self):
        """from_dict() with empty outputs list."""
        d = {"success": True, "outputs": [], "execution_count": 0, "error": None}
        result = ExecutionResult.from_dict(d)
        assert result.outputs == []

    def test_from_dict_multiple_output_types(self):
        """from_dict() with multiple output types in outputs list."""
        outputs = [
            {"type": "stream", "name": "stdout", "text": "line1\n"},
            {"type": "stream", "name": "stderr", "text": "warn\n"},
            {"type": "execute_result", "data": {"text/plain": "5"}, "execution_count": 1},
            {"type": "error", "ename": "ValueError", "evalue": "bad", "traceback": []},
            {"type": "display_data", "data": {"text/html": "<b>x</b>"}},
        ]
        d = {
            "success": False,
            "outputs": outputs,
            "execution_count": 1,
            "error": "ValueError: bad",
        }
        result = ExecutionResult.from_dict(d)
        assert len(result.outputs) == 5
        assert result.outputs[0]["type"] == "stream"
        assert result.outputs[2]["type"] == "execute_result"
        assert result.outputs[3]["type"] == "error"
        assert result.outputs[4]["type"] == "display_data"

    def test_from_dict_returns_execution_result_instance(self):
        d = {"success": True, "outputs": [], "execution_count": 1, "error": None}
        result = ExecutionResult.from_dict(d)
        assert isinstance(result, ExecutionResult)

    def test_from_dict_success_false_with_error(self):
        d = {
            "success": False,
            "outputs": [{"type": "error", "ename": "NameError", "evalue": "name 'x' is not defined", "traceback": []}],
            "execution_count": 2,
            "error": "NameError: name 'x' is not defined",
        }
        result = ExecutionResult.from_dict(d)
        assert result.success is False
        assert result.error == "NameError: name 'x' is not defined"

    def test_from_dict_return_value_explicit_none(self):
        d = {"success": True, "outputs": [], "execution_count": 1, "error": None, "return_value": None}
        result = ExecutionResult.from_dict(d)
        assert result.return_value is None

    def test_from_dict_return_value_string(self):
        d = {"success": True, "outputs": [], "execution_count": 1, "error": None, "return_value": "42"}
        result = ExecutionResult.from_dict(d)
        assert result.return_value == "42"


class TestExecutionResultDefaultFieldValues:
    """Tests for ExecutionResult default field values."""

    def test_default_outputs_is_empty_list(self):
        result = ExecutionResult(success=True)
        assert result.outputs == []

    def test_default_execution_count_is_zero(self):
        result = ExecutionResult(success=True)
        assert result.execution_count == 0

    def test_default_error_is_none(self):
        result = ExecutionResult(success=True)
        assert result.error is None

    def test_default_return_value_is_none(self):
        result = ExecutionResult(success=True)
        assert result.return_value is None

    def test_default_outputs_not_shared_between_instances(self):
        """Each instance must get its own default list (field default_factory)."""
        r1 = ExecutionResult(success=True)
        r2 = ExecutionResult(success=True)
        r1.outputs.append({"type": "stream"})
        assert r2.outputs == [], "Mutable default must not be shared between instances"

    def test_success_false_defaults(self):
        result = ExecutionResult(success=False)
        assert result.outputs == []
        assert result.execution_count == 0
        assert result.error is None
        assert result.return_value is None


class TestExecutionResultWithVariousOutputTypes:
    """Tests for various output dict types stored in ExecutionResult."""

    def test_stream_stdout_output(self):
        output = {"type": "stream", "name": "stdout", "text": "Hello\n"}
        result = ExecutionResult(success=True, outputs=[output], execution_count=1)
        assert result.outputs[0]["name"] == "stdout"
        assert result.outputs[0]["text"] == "Hello\n"

    def test_stream_stderr_output(self):
        output = {"type": "stream", "name": "stderr", "text": "Warning\n"}
        result = ExecutionResult(success=True, outputs=[output], execution_count=1)
        assert result.outputs[0]["name"] == "stderr"

    def test_execute_result_output(self):
        output = {
            "type": "execute_result",
            "data": {"text/plain": "42", "text/html": "<pre>42</pre>"},
            "execution_count": 1,
        }
        result = ExecutionResult(success=True, outputs=[output], execution_count=1)
        assert result.outputs[0]["data"]["text/plain"] == "42"

    def test_error_output(self):
        output = {
            "type": "error",
            "ename": "TypeError",
            "evalue": "unsupported operand",
            "traceback": ["line1", "line2"],
        }
        result = ExecutionResult(
            success=False, outputs=[output], execution_count=1, error="TypeError: unsupported operand"
        )
        assert result.outputs[0]["ename"] == "TypeError"
        assert result.outputs[0]["traceback"] == ["line1", "line2"]

    def test_display_data_output(self):
        output = {
            "type": "display_data",
            "data": {"text/html": "<b>bold</b>", "text/plain": "<b>bold</b>"},
        }
        result = ExecutionResult(success=True, outputs=[output], execution_count=1)
        assert result.outputs[0]["data"]["text/html"] == "<b>bold</b>"

    def test_multiple_mixed_outputs_preserved(self):
        outputs = [
            {"type": "stream", "name": "stdout", "text": "before\n"},
            {"type": "display_data", "data": {"text/plain": "fig"}},
            {"type": "execute_result", "data": {"text/plain": "result"}, "execution_count": 1},
        ]
        result = ExecutionResult(success=True, outputs=outputs, execution_count=1)
        d = result.to_dict()
        assert len(d["outputs"]) == 3
        assert d["outputs"][0]["type"] == "stream"
        assert d["outputs"][1]["type"] == "display_data"
        assert d["outputs"][2]["type"] == "execute_result"
