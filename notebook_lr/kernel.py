"""
NotebookKernel: Persistent IPython kernel that maintains execution state.
"""

from typing import Any, Optional
from dataclasses import dataclass, field

from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output


def _build_mime_bundle(obj) -> dict:
    """
    Build a MIME bundle dictionary from an object.

    Checks for IPython rich display methods and builds a dict
    mapping MIME types to their representations. For display objects
    that have a primary content attribute (e.g. HTML.data), use that
    as the text/plain fallback instead of repr().
    """
    rich_content = None

    rich_entries = []
    for mime_type, method_name in [
        ("text/html", "_repr_html_"),
        ("text/markdown", "_repr_markdown_"),
        ("application/json", "_repr_json_"),
        ("text/latex", "_repr_latex_"),
        ("image/svg+xml", "_repr_svg_"),
        ("image/png", "_repr_png_"),
    ]:
        method = getattr(obj, method_name, None)
        if callable(method):
            value = method()
            if value is not None:
                rich_entries.append((mime_type, value))
                if rich_content is None:
                    rich_content = value

    # Use the primary rich content as text/plain if available,
    # otherwise fall back to repr(). This avoids "<IPython...object>" strings.
    plain = rich_content if rich_content is not None else repr(obj)
    data = {"text/plain": plain}
    for mime_type, value in rich_entries:
        data[mime_type] = value

    return data


@dataclass
class ExecutionResult:
    """Result of executing a code cell."""
    success: bool
    outputs: list[dict[str, Any]] = field(default_factory=list)
    execution_count: int = 0
    error: Optional[str] = None
    return_value: Any = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "outputs": self.outputs,
            "execution_count": self.execution_count,
            "error": self.error,
            "return_value": str(self.return_value) if self.return_value is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionResult":
        """Create from dictionary."""
        return cls(
            success=data["success"],
            outputs=data["outputs"],
            execution_count=data["execution_count"],
            error=data.get("error"),
            return_value=data.get("return_value"),
        )


class NotebookKernel:
    """
    Persistent IPython kernel that maintains execution state.

    This kernel wraps IPython's InteractiveShell to provide:
    - Persistent namespace across cell executions
    - Output capture (stdout, stderr, rich display)
    - Execution history
    """

    def __init__(self):
        """Initialize the kernel with a fresh IPython shell."""
        # Create a new InteractiveShell instance
        self.ip = InteractiveShell.instance()
        self.execution_count = 0
        self._history: list[tuple[int, str, ExecutionResult]] = []

        # Ensure clean state
        self._setup_namespace()

    def _setup_namespace(self):
        """Set up the initial namespace with useful imports."""
        # Add some convenience to the namespace
        self.ip.user_ns["__notebook__"] = True

    def execute_cell(self, code: str) -> ExecutionResult:
        """
        Execute code and return result with outputs.

        Args:
            code: Python code to execute

        Returns:
            ExecutionResult with outputs and status
        """
        self.execution_count += 1
        outputs = []
        error = None
        return_value = None

        try:
            with capture_output() as captured:
                result = self.ip.run_cell(code, silent=False)

            if captured.stdout:
                outputs.append({
                    "type": "stream",
                    "name": "stdout",
                    "text": captured.stdout,
                })

            if captured.stderr:
                outputs.append({
                    "type": "stream",
                    "name": "stderr",
                    "text": captured.stderr,
                })

            # display() 호출로 생성된 출력 처리
            for display_output in captured.outputs:
                data = {}
                if hasattr(display_output, 'data'):
                    data = display_output.data
                elif hasattr(display_output, '_repr_html_'):
                    data = _build_mime_bundle(display_output)
                outputs.append({
                    "type": "display_data",
                    "data": data,
                })

            if result.success:
                if result.result is not None:
                    return_value = result.result
                    data = _build_mime_bundle(result.result)
                    outputs.append({
                        "type": "execute_result",
                        "data": data,
                        "execution_count": self.execution_count,
                    })
            else:
                if result.error_in_exec:
                    error = str(result.error_in_exec)
                    outputs.append({
                        "type": "error",
                        "ename": type(result.error_in_exec).__name__,
                        "evalue": str(result.error_in_exec),
                        "traceback": [],
                    })

        except Exception as e:
            error = str(e)
            outputs.append({
                "type": "error",
                "ename": type(e).__name__,
                "evalue": str(e),
                "traceback": [],
            })

        exec_result = ExecutionResult(
            success=error is None,
            outputs=outputs,
            execution_count=self.execution_count,
            error=error,
            return_value=return_value,
        )

        self._history.append((self.execution_count, code, exec_result))

        return exec_result

    def get_namespace(self) -> dict:
        """
        Get current namespace for serialization.

        Returns a copy of the user namespace, filtering out
        non-serializable items and internal IPython objects.
        """
        ns = {}
        for key, value in self.ip.user_ns.items():
            # Skip private/internal variables
            if key.startswith("_"):
                continue
            # Skip modules and functions that can't be pickled easily
            try:
                ns[key] = value
            except Exception:
                pass
        return ns

    def restore_namespace(self, namespace: dict):
        """
        Restore namespace from previous session.

        Args:
            namespace: Dictionary of variables to restore
        """
        self.ip.user_ns.update(namespace)

    def get_history(self) -> list[tuple[int, str, ExecutionResult]]:
        """Get execution history."""
        return self._history.copy()

    def clear_history(self):
        """Clear execution history."""
        self._history.clear()

    def reset(self):
        """Reset the kernel to a clean state."""
        self.ip.reset()
        self.execution_count = 0
        self._history.clear()
        self._setup_namespace()

    def get_variable(self, name: str) -> Any:
        """Get a variable from the namespace."""
        return self.ip.user_ns.get(name)

    def set_variable(self, name: str, value: Any):
        """Set a variable in the namespace."""
        self.ip.user_ns[name] = value

    def del_variable(self, name: str):
        """Delete a variable from the namespace."""
        if name in self.ip.user_ns:
            del self.ip.user_ns[name]

    def get_defined_names(self) -> list[str]:
        """Get list of user-defined names in namespace."""
        return [k for k in self.ip.user_ns.keys() if not k.startswith("_")]
