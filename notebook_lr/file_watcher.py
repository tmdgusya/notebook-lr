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
