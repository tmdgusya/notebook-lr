import tempfile
from pathlib import Path
from notebook_lr import Notebook
from notebook_lr.cli import NotebookEditor


def test_editor_has_file_watcher_attribute():
    """Test that NotebookEditor has file_watcher attribute."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, 'file_watcher')
