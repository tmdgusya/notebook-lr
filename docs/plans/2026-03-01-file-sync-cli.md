# CLI TUI File Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add automatic file watching to CLI TUI so it detects changes made by MCP server and reloads notebook content, with conflict detection when both have unsaved changes.

**Architecture:** Add a `FileWatcher` daemon thread that polls file mtime every 1 second. When changes are detected, signal the main TUI loop via a thread-safe queue. The main loop checks for signals on each refresh and either auto-reloads (if no local changes) or shows a conflict dialog (if TUI has unsaved modifications).

**Tech Stack:** Python threading, queue.Queue for thread communication, hashlib for content verification

---

### Task 1: Create FileWatcher Class

**Files:**
- Create: `notebook_lr/file_watcher.py`
- Test: `tests/test_file_watcher.py`

**Step 1: Write the failing test**

```python
import tempfile
import time
from pathlib import Path
from notebook_lr.file_watcher import FileWatcher

def test_file_watcher_detects_changes():
    """Test that FileWatcher detects file changes."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("initial content")
        temp_path = f.name
    
    try:
        watcher = FileWatcher(temp_path, poll_interval=0.1)
        watcher.start()
        
        # Wait a bit then modify the file
        time.sleep(0.15)
        Path(temp_path).write_text("modified content")
        
        # Wait for detection
        time.sleep(0.15)
        
        assert watcher.has_changes()
        
        # Acknowledge changes
        watcher.acknowledge_changes()
        assert not watcher.has_changes()
        
        watcher.stop()
    finally:
        Path(temp_path).unlink(missing_ok=True)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_file_watcher.py::test_file_watcher_detects_changes -v`
Expected: FAIL with "FileWatcher not found" or "module not found"

**Step 3: Write minimal implementation**

```python
"""File watcher for detecting external changes to notebook files."""

import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Optional


class FileWatcher:
    """Watch a file for external changes using polling.
    
    Uses a background thread to check file mtime periodically.
    Thread-safe for use with TUI main loop.
    """
    
    def __init__(self, file_path: str | Path, poll_interval: float = 1.0):
        """Initialize file watcher.
        
        Args:
            file_path: Path to the file to watch
            poll_interval: Seconds between checks (default: 1.0)
        """
        self.file_path = Path(file_path)
        self.poll_interval = poll_interval
        self._last_mtime: float = 0.0
        self._last_hash: Optional[str] = None
        self._has_changes: bool = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # Initialize with current state
        self._update_state()
    
    def _get_file_hash(self) -> Optional[str]:
        """Get SHA256 hash of file contents."""
        try:
            content = self.file_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except (OSError, IOError):
            return None
    
    def _update_state(self) -> None:
        """Update internal state from current file."""
        try:
            self._last_mtime = os.path.getmtime(self.file_path)
            self._last_hash = self._get_file_hash()
        except (OSError, IOError):
            self._last_mtime = 0.0
            self._last_hash = None
    
    def _check_file(self) -> bool:
        """Check if file has changed. Returns True if changed."""
        try:
            current_mtime = os.path.getmtime(self.file_path)
            if current_mtime != self._last_mtime:
                current_hash = self._get_file_hash()
                if current_hash != self._last_hash:
                    return True
                # mtime changed but content same - update mtime only
                self._last_mtime = current_mtime
        except (OSError, IOError):
            pass
        return False
    
    def _watch_loop(self) -> None:
        """Main watch loop running in background thread."""
        while not self._stop_event.is_set():
            if self._check_file():
                with self._lock:
                    self._has_changes = True
            time.sleep(self.poll_interval)
    
    def start(self) -> None:
        """Start the file watcher thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the file watcher thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval + 0.5)
            self._thread = None
    
    def has_changes(self) -> bool:
        """Check if file has changed since last acknowledge."""
        with self._lock:
            return self._has_changes
    
    def acknowledge_changes(self) -> None:
        """Acknowledge and reset change flag."""
        with self._lock:
            self._has_changes = False
            self._update_state()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_file_watcher.py::test_file_watcher_detects_changes -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_file_watcher.py notebook_lr/file_watcher.py
git commit -m "feat: add FileWatcher class for detecting external file changes"
```

---

### Task 2: Add Conflict Detection Tests

**Files:**
- Modify: `tests/test_file_watcher.py`

**Step 1: Write the failing test**

```python
def test_file_watcher_content_hash():
    """Test that FileWatcher uses content hash, not just mtime."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("content")
        temp_path = f.name
    
    try:
        watcher = FileWatcher(temp_path, poll_interval=0.1)
        watcher.start()
        
        # Touch file without changing content
        time.sleep(0.15)
        Path(temp_path).touch()
        
        time.sleep(0.15)
        
        # Should NOT detect as changed
        assert not watcher.has_changes()
        
        watcher.stop()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_file_watcher_no_file():
    """Test FileWatcher handles missing file gracefully."""
    nonexistent_path = "/tmp/nonexistent_file_12345.nblr"
    
    watcher = FileWatcher(nonexistent_path, poll_interval=0.1)
    watcher.start()
    
    time.sleep(0.15)
    
    # Should not crash
    assert not watcher.has_changes()
    
    watcher.stop()
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_file_watcher.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_file_watcher.py
git commit -m "test: add FileWatcher edge case tests"
```

---

### Task 3: Integrate FileWatcher into NotebookEditor

**Files:**
- Modify: `notebook_lr/cli.py`
- Test: `tests/test_cli_file_sync.py` (create new)

**Step 1: Write the failing test**

```python
import tempfile
from pathlib import Path
from notebook_lr import Notebook
from notebook_lr.cli import NotebookEditor


def test_editor_has_file_watcher_attribute():
    """Test that NotebookEditor has file_watcher attribute."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, 'file_watcher')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_file_watcher_attribute -v`
Expected: FAIL with "AttributeError: 'NotebookEditor' object has no attribute 'file_watcher'"

**Step 3: Write minimal implementation**

In `notebook_lr/cli.py`, add import and modify NotebookEditor.__init__:

```python
# Add to imports at top
from notebook_lr.file_watcher import FileWatcher

# In NotebookEditor.__init__, add after line 38:
        self.file_watcher: Optional[FileWatcher] = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_file_watcher_attribute -v`
Expected: PASS

**Step 5: Commit**

```bash
git add notebook_lr/cli.py tests/test_cli_file_sync.py
git commit -m "feat: add file_watcher attribute to NotebookEditor"
```

---

### Task 4: Add File Watcher Lifecycle Management

**Files:**
- Modify: `notebook_lr/cli.py` (NotebookEditor class)

**Step 1: Write the failing test**

```python
import tempfile
from pathlib import Path
from notebook_lr import Notebook
from notebook_lr.cli import NotebookEditor


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_file_sync.py::test_editor_starts_watcher_with_path tests/test_cli_file_sync.py::test_editor_no_watcher_without_path -v`
Expected: FAIL with "AttributeError: 'NotebookEditor' object has no attribute '_start_file_watcher'"

**Step 3: Write minimal implementation**

In `notebook_lr/cli.py`, add to NotebookEditor class:

```python
    def _start_file_watcher(self) -> None:
        """Start watching the notebook file for external changes."""
        path = self.notebook.metadata.get("path")
        if path is None:
            return
        
        path_obj = Path(path)
        if not path_obj.exists():
            return
        
        self.file_watcher = FileWatcher(path_obj, poll_interval=1.0)
        self.file_watcher.start()
    
    def _stop_file_watcher(self) -> None:
        """Stop the file watcher."""
        if self.file_watcher is not None:
            self.file_watcher.stop()
            self.file_watcher = None
    
    def _check_external_changes(self) -> bool:
        """Check if file has been modified externally.
        
        Returns:
            True if external changes detected
        """
        if self.file_watcher is None:
            return False
        return self.file_watcher.has_changes()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_file_sync.py::test_editor_starts_watcher_with_path tests/test_cli_file_sync.py::test_editor_no_watcher_without_path -v`
Expected: PASS

**Step 5: Commit**

```bash
git add notebook_lr/cli.py tests/test_cli_file_sync.py
git commit -m "feat: add file watcher lifecycle methods to NotebookEditor"
```

---

### Task 5: Implement Conflict Dialog

**Files:**
- Modify: `notebook_lr/cli.py` (NotebookEditor class)
- Test: `tests/test_cli_file_sync.py`

**Step 1: Write the failing test**

```python
def test_editor_has_conflict_resolution_method():
    """Test that editor has conflict resolution method."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, '_resolve_conflict')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_conflict_resolution_method -v`
Expected: FAIL with "AttributeError: 'NotebookEditor' object has no attribute '_resolve_conflict'"

**Step 3: Write minimal implementation**

In `notebook_lr/cli.py`, add to NotebookEditor class:

```python
    def _resolve_conflict(self) -> str:
        """Show conflict dialog and return user choice.
        
        Returns:
            'reload' to load external changes
            'keep' to keep local changes
            'cancel' to do nothing
        """
        console.print()
        console.print(Panel(
            "[bold yellow]External changes detected![/bold yellow]\n\n"
            "The notebook file has been modified by another process (e.g., MCP server).\n"
            "You also have unsaved changes in this editor.\n\n"
            "[cyan]r[/cyan] - Reload file (discard your changes)\n"
            "[cyan]k[/cyan] - Keep your changes (overwrite file on save)\n"
            "[cyan]c[/cyan] - Cancel (do nothing for now)",
            title="[bold red]Conflict Detected[/bold red]",
            border_style="red",
        ))
        
        while True:
            choice = console.input("[bold cyan]Choice [r/k/c]: [/bold cyan]").strip().lower()
            if choice in ('r', 'reload'):
                return 'reload'
            elif choice in ('k', 'keep'):
                return 'keep'
            elif choice in ('c', 'cancel'):
                return 'cancel'
            console.print("[dim]Invalid choice. Use r, k, or c.[/dim]")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_conflict_resolution_method -v`
Expected: PASS

**Step 5: Commit**

```bash
git add notebook_lr/cli.py tests/test_cli_file_sync.py
git commit -m "feat: add conflict resolution dialog to NotebookEditor"
```

---

### Task 6: Implement Auto-Reload Logic

**Files:**
- Modify: `notebook_lr/cli.py` (NotebookEditor class)

**Step 1: Write the failing test**

```python
def test_editor_has_reload_method():
    """Test that editor has reload method."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, '_reload_from_disk')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_reload_method -v`
Expected: FAIL with "AttributeError: 'NotebookEditor' object has no attribute '_reload_from_disk'"

**Step 3: Write minimal implementation**

In `notebook_lr/cli.py`, add to NotebookEditor class:

```python
    def _reload_from_disk(self) -> None:
        """Reload notebook from disk and update display."""
        path = self.notebook.metadata.get("path")
        if path is None:
            return
        
        try:
            from notebook_lr import Notebook
            new_notebook = Notebook.load(Path(path))
            
            # Preserve path metadata
            new_notebook.metadata["path"] = path
            
            # Update editor state
            self.notebook = new_notebook
            
            # Adjust current cell index if needed
            if self.current_cell_index >= len(self.notebook.cells):
                self.current_cell_index = max(0, len(self.notebook.cells) - 1)
            
            # Mark as not modified (we just loaded fresh content)
            self.modified = False
            
            # Acknowledge the change in watcher
            if self.file_watcher:
                self.file_watcher.acknowledge_changes()
            
            self._set_message("[green]Notebook reloaded from disk[/green]")
            
        except Exception as e:
            self._set_message(f"[red]Error reloading: {e}[/red]")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_reload_method -v`
Expected: PASS

**Step 5: Commit**

```bash
git add notebook_lr/cli.py tests/test_cli_file_sync.py
git commit -m "feat: add _reload_from_disk method to NotebookEditor"
```

---

### Task 7: Wire Up Change Detection in Main Loop

**Files:**
- Modify: `notebook_lr/cli.py` (NotebookEditor.run method)

**Step 1: Write the failing test**

This is an integration test - we'll verify by checking the method exists:

```python
def test_editor_has_handle_external_changes_method():
    """Test that editor has external changes handler."""
    nb = Notebook.new()
    editor = NotebookEditor(nb)
    
    assert hasattr(editor, '_handle_external_changes')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_handle_external_changes_method -v`
Expected: FAIL

**Step 3: Write minimal implementation**

In `notebook_lr/cli.py`, add to NotebookEditor class:

```python
    def _handle_external_changes(self) -> bool:
        """Handle external file changes.
        
        Returns:
            True if changes were handled (reload or keep)
            False if no changes detected
        """
        if not self._check_external_changes():
            return False
        
        if self.modified:
            # Conflict: both external and local changes
            choice = self._resolve_conflict()
            
            if choice == 'reload':
                self._reload_from_disk()
            elif choice == 'keep':
                # Mark external changes as acknowledged, keep local
                if self.file_watcher:
                    self.file_watcher.acknowledge_changes()
                self._set_message("[yellow]Keeping your changes. Save to overwrite.[/yellow]")
            # 'cancel' - do nothing, will prompt again next cycle
        else:
            # No local changes - auto-reload
            self._reload_from_disk()
        
        return True
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_file_sync.py::test_editor_has_handle_external_changes_method -v`
Expected: PASS

**Step 5: Commit**

```bash
git add notebook_lr/cli.py tests/test_cli_file_sync.py
git commit -m "feat: add external changes handler method"
```

---

### Task 8: Integrate into Main Loop

**Files:**
- Modify: `notebook_lr/cli.py` (NotebookEditor.run method around line 686)

**Step 1: Understand current run() method**

Read the current run() method to understand where to insert the watcher start/stop and check calls.

**Step 2: Modify run() method**

In `notebook_lr/cli.py`, modify the `run()` method:

```python
    def run(self):
        """Run the interactive editor."""
        # Check for saved session
        notebook_path = self.notebook.metadata.get("path")
        if notebook_path and Path(notebook_path).exists():
            checkpoint_info = self.session_manager.load_checkpoint(
                self.kernel, Path(notebook_path)
            )
            if checkpoint_info:
                self._set_message(
                    f"[green]Restored session with "
                    f"{len(checkpoint_info['restored_vars'])} variables[/green]"
                )
        
        # Start file watcher
        self._start_file_watcher()
        
        try:
            while self.running:
                # Check for external changes before display
                self._handle_external_changes()
                
                self.display_cells()
                self.display_command_bar()
                
                # ... rest of the existing loop ...
                
        finally:
            # Stop file watcher on exit
            self._stop_file_watcher()
```

The key changes are:
1. Add `self._start_file_watcher()` after session restore
2. Add `self._handle_external_changes()` at the start of each loop iteration  
3. Wrap the loop in try/finally and add `self._stop_file_watcher()` in finally

**Step 3: Run existing CLI tests to verify no regression**

Run: `pytest tests/test_e2e_cli.py -v -k "test_edit" --tb=short`
Expected: All tests PASS (or skip if they require interactive input)

Run: `pytest tests/test_editor_cells.py -v --tb=short`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add notebook_lr/cli.py
git commit -m "feat: integrate file watcher into main editor loop"
```

---

### Task 9: Add Integration Tests

**Files:**
- Create: `tests/test_file_sync_integration.py`

**Step 1: Write integration tests**

```python
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
            editor._start_file_watcher()
            
            # Simulate external modification
            time.sleep(0.15)
            nb2 = Notebook.load(Path(temp_path))
            nb2.add_cell(type=CellType.CODE, source="y = 2")
            nb2.save(Path(temp_path))
            
            time.sleep(0.15)
            
            # Editor should detect changes
            assert editor._check_external_changes()
            
            editor._stop_file_watcher()
        finally:
            Path(temp_path).unlink(missing_ok=True)
```

**Step 2: Run integration tests**

Run: `pytest tests/test_file_sync_integration.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_file_sync_integration.py
git commit -m "test: add file sync integration tests"
```

---

### Task 10: Final Verification

**Files:**
- All modified files

**Step 1: Run full test suite**

Run: `pytest tests/test_file_watcher.py tests/test_cli_file_sync.py tests/test_file_sync_integration.py -v`
Expected: All tests PASS

**Step 2: Run existing tests to ensure no regression**

Run: `pytest tests/ -v --tb=short -x -q`
Expected: All existing tests still PASS

**Step 3: Verify imports work**

Run: `python -c "from notebook_lr.file_watcher import FileWatcher; from notebook_lr.cli import NotebookEditor; print('Imports OK')"`
Expected: "Imports OK"

**Step 4: Commit any final changes**

```bash
git add -A
git commit -m "feat: complete file sync implementation for CLI TUI"
```

---

## Summary

This implementation adds:

1. **FileWatcher class** (`notebook_lr/file_watcher.py`) - Thread-based file polling with content hash verification
2. **Conflict detection** - Detects when both TUI and external source have made changes
3. **Conflict resolution dialog** - Prompts user to reload, keep, or cancel
4. **Auto-reload** - Silently reloads when no local changes exist
5. **Integration** - Watcher starts/stops with editor lifecycle, checks on each loop iteration

The solution ensures the CLI TUI stays in sync with changes made by the MCP server while handling the conflict scenario gracefully.
