"""Integration tests for file sync between CLI TUI and MCP server."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from notebook_lr import Notebook, CellType
from notebook_lr.file_watcher import FileWatcher


class TestFileWatcherIntegration:
    """Test FileWatcher with real notebook files."""
    
    def test_watcher_detects_notebook_modification(self):
        """Test that FileWatcher detects notebook file changes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nblr', delete=False) as f:
            nb = Notebook.new("Test")
            nb.add_cell(type=CellType.CODE, source="x = 1")
            json.dump(nb.to_dict(), f)
            temp_path = f.name
        
        try:
            watcher = FileWatcher(temp_path, poll_interval=0.1)
            watcher.start()
            
            # Simulate external modification (like MCP server)
            time.sleep(0.15)
            nb2 = Notebook.load(Path(temp_path))
            nb2.add_cell(type=CellType.CODE, source="y = 2")
            nb2.save(Path(temp_path))
            
            time.sleep(0.15)
            
            assert watcher.has_changes()
            
            watcher.stop()
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_watcher_no_false_positives_on_same_content(self):
        """Test that touching file without content change doesn't trigger."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nblr', delete=False) as f:
            nb = Notebook.new("Test")
            json.dump(nb.to_dict(), f)
            temp_path = f.name
        
        try:
            watcher = FileWatcher(temp_path, poll_interval=0.1)
            watcher.start()
            
            # Just touch the file
            time.sleep(0.15)
            Path(temp_path).touch()
            
            time.sleep(0.15)
            
            # Should not detect as changed
            assert not watcher.has_changes()
            
            watcher.stop()
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestEditorFileSyncIntegration:
    """Test NotebookEditor file sync behavior."""
    
    def test_editor_detects_external_changes(self):
        """Test that editor can detect external changes to notebook."""
        from notebook_lr.cli import NotebookEditor
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nblr', delete=False) as f:
            nb = Notebook.new("Test")
            nb.add_cell(type=CellType.CODE, source="x = 1")
            json.dump(nb.to_dict(), f)
            temp_path = f.name
        
        try:
            # Load notebook into editor
            nb_loaded = Notebook.load(Path(temp_path))
            nb_loaded.metadata["path"] = temp_path
            
            editor = NotebookEditor(nb_loaded)
            # Set a shorter poll interval for testing
            editor.file_watcher = FileWatcher(temp_path, poll_interval=0.1)
            editor.file_watcher.start()
            
            # Wait for watcher to initialize
            time.sleep(0.15)
            
            # Simulate external modification
            time.sleep(0.1)
            nb2 = Notebook.load(Path(temp_path))
            nb2.add_cell(type=CellType.CODE, source="y = 2")
            nb2.save(Path(temp_path))
            
            time.sleep(0.15)
            
            # Editor should detect changes
            assert editor._check_external_changes()
            
            editor._stop_file_watcher()
        finally:
            Path(temp_path).unlink(missing_ok=True)
