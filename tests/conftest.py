"""
Pytest configuration for MCP tests.

This module provides fixtures that automatically reset the MCP server's
global state before each test to ensure test isolation.
"""

import pytest

from notebook_lr.mcp_server import _reset_notebook


@pytest.fixture(autouse=True)
def reset_mcp_state():
    """Reset the MCP server's global notebook state before each test."""
    _reset_notebook()
    yield
    # Reset again after test to be safe
    _reset_notebook()
