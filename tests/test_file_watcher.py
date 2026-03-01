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
