import tempfile
from pathlib import Path
from notebook_lr import Notebook
from notebook_lr.cli import NotebookEditor


def test_editor_has_file_watcher_attribute():
    """Test that NotebookEditor has file_watcher attribute."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, 'file_watcher')


def test_editor_starts_watcher_with_path():
    """Test that editor starts file watcher when notebook has path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.nblr', delete=False) as f:
        f.write('{"version": "1.0", "cells": [], "metadata": {"name": "test"}}')
        temp_path = f.name
    
    try:
        nb = Notebook.new()
        nb.metadata["path"] = temp_path
        
        editor = NotebookEditor(nb)
        editor._start_file_watcher()
        
        assert editor.file_watcher is not None
        assert editor.file_watcher.file_path == Path(temp_path)
        
        editor._stop_file_watcher()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_editor_no_watcher_without_path():
    """Test that editor doesn't create watcher without path."""
    nb = Notebook.new()
    # No path set
    
    editor = NotebookEditor(nb)
    editor._start_file_watcher()
    
    assert editor.file_watcher is None


def test_editor_has_reload_method():
    """Test that editor has reload method."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, '_reload_from_disk')


def test_editor_has_conflict_resolution_method():
    """Test that editor has conflict resolution method."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, '_resolve_conflict')


def test_editor_has_handle_external_changes_method():
    """Test that editor has external changes handler."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, '_handle_external_changes')
