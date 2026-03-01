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
