"""
Utility functions for notebook-lr.
"""

import re
from typing import Any
from datetime import datetime

from rich.syntax import Syntax
from rich.text import Text


def format_output(output: dict[str, Any]) -> str:
    """
    Format an output dictionary for display (plain text).

    Args:
        output: Output dictionary from ExecutionResult

    Returns:
        Formatted string for display
    """
    output_type = output.get("type", "")

    if output_type == "stream":
        return output.get("text", "")

    elif output_type == "execute_result":
        data = output.get("data", {})
        # Prefer rich types over plain text
        if "text/html" in data:
            return data["text/html"]
        if "text/markdown" in data:
            return data["text/markdown"]
        if "application/json" in data:
            import json
            val = data["application/json"]
            return json.dumps(val, indent=2) if not isinstance(val, str) else val
        return data.get("text/plain", "")

    elif output_type == "error":
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        return f"{ename}: {evalue}"

    elif output_type == "display_data":
        data = output.get("data", {})
        # Prefer rich types over plain text
        if "text/html" in data:
            return data["text/html"]
        if "text/markdown" in data:
            return data["text/markdown"]
        if "application/json" in data:
            import json
            val = data["application/json"]
            return json.dumps(val, indent=2) if not isinstance(val, str) else val
        return data.get("text/plain", str(data))

    return str(output)


def format_rich_output(output: dict[str, Any]):
    """
    Format an output dictionary as a Rich renderable.

    Args:
        output: Output dictionary from ExecutionResult

    Returns:
        Rich renderable object for console display
    """
    output_type = output.get("type", "")

    if output_type == "stream":
        text = output.get("text", "")
        name = output.get("name", "stdout")
        if name == "stderr":
            return Text(text.rstrip("\n"), style="yellow")
        return Text(text.rstrip("\n"))

    elif output_type == "execute_result":
        data = output.get("data", {})
        # Prefer rich types over plain text
        if "text/html" in data:
            return Text(data["text/html"], style="cyan")
        if "text/markdown" in data:
            return Text(data["text/markdown"], style="cyan")
        if "application/json" in data:
            import json
            val = data["application/json"]
            text = json.dumps(val, indent=2) if not isinstance(val, str) else val
            try:
                return Syntax(text, "json", theme="monokai", line_numbers=False)
            except Exception:
                return Text(text, style="cyan")
        text = data.get("text/plain", "")
        try:
            return Syntax(text, "python", theme="monokai", line_numbers=False)
        except Exception:
            return Text(text, style="cyan")

    elif output_type == "error":
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        traceback_lines = output.get("traceback", [])

        error_text = Text()
        error_text.append(f"{ename}", style="bold red")
        error_text.append(f": {evalue}", style="red")
        if traceback_lines:
            for tb_line in traceback_lines:
                if isinstance(tb_line, str):
                    error_text.append(f"\n{tb_line}", style="dim red")
        return error_text

    elif output_type == "display_data":
        data = output.get("data", {})
        # Prefer rich types over plain text
        if "text/html" in data:
            return Text(data["text/html"], style="cyan")
        if "text/markdown" in data:
            return Text(data["text/markdown"], style="cyan")
        if "application/json" in data:
            import json
            val = data["application/json"]
            text = json.dumps(val, indent=2) if not isinstance(val, str) else val
            return Text(text, style="cyan")
        return Text(data.get("text/plain", str(data)), style="cyan")

    return Text(str(output), style="dim")


def get_cell_type_icon(cell_type) -> str:
    """Get a short label for the cell type."""
    if hasattr(cell_type, "value"):
        cell_type = cell_type.value
    return "py" if cell_type == "code" else "md"


def get_cell_status(cell) -> tuple[str, str]:
    """
    Get status indicator and style for a cell.

    Returns:
        Tuple of (indicator_string, rich_style)
    """
    if cell.outputs:
        has_error = any(o.get("type") == "error" for o in cell.outputs)
        if has_error:
            return ("err", "red")
        return ("ok", "green")
    elif cell.execution_count is not None:
        return ("ok", "green")
    return ("--", "dim")


def is_markdown(text: str) -> bool:
    """
    Check if text appears to be markdown.

    Args:
        text: Text to check

    Returns:
        True if text looks like markdown
    """
    markdown_patterns = [
        r"^#{1,6}\s+",  # Headers
        r"^\*\*.*\*\*",  # Bold
        r"^\*.*\*",  # Italic
        r"^\[.*\]\(.*\)",  # Links
        r"^```",  # Code blocks
        r"^-\s+",  # Lists
        r"^\d+\.\s+",  # Numbered lists
    ]

    for pattern in markdown_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True

    return False


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def get_timestamp() -> str:
    """Get current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sanitize_variable_name(name: str) -> str:
    """
    Sanitize a variable name to be valid Python.

    Args:
        name: Variable name to sanitize

    Returns:
        Sanitized variable name
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized

    return sanitized or "_var"


def estimate_cell_lines(source: str) -> int:
    """Estimate the number of lines needed to display a cell."""
    if not source:
        return 1
    lines = source.count("\n") + 1
    return max(1, lines)
