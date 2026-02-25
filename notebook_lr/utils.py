"""
Utility functions for notebook-lr.
"""

import re
from typing import Any
from datetime import datetime


def format_output(output: dict[str, Any]) -> str:
    """
    Format an output dictionary for display.

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
        return data.get("text/plain", "")

    elif output_type == "error":
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        return f"{ename}: {evalue}"

    elif output_type == "display_data":
        data = output.get("data", {})
        return data.get("text/plain", str(data))

    return str(output)


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
    return text[:max_length - 3] + "..."


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
    # Replace invalid characters with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized

    return sanitized or "_var"


def estimate_cell_lines(source: str) -> int:
    """Estimate the number of lines needed to display a cell."""
    if not source:
        return 1
    lines = source.count("\n") + 1
    return max(1, lines)
