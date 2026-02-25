"""
SessionManager: Manages saving/loading of kernel state.
"""

import pickle
import dill
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from notebook_lr.kernel import NotebookKernel


class SessionManager:
    """
    Manages saving/loading of kernel state.

    Uses dill for serialization which can handle:
    - Functions and lambdas
    - Class instances
    - Most Python objects

    Falls back to pickle for basic types if dill fails.
    """

    def __init__(self, sessions_dir: Optional[Path] = None):
        """
        Initialize session manager.

        Args:
            sessions_dir: Directory to store session files
        """
        self.sessions_dir = sessions_dir or Path.home() / ".notebook_lr" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, kernel: NotebookKernel, path: Optional[Path] = None, name: Optional[str] = None) -> Path:
        """
        Save the kernel state to a file.

        Args:
            kernel: NotebookKernel instance to save
            path: Optional specific path to save to
            name: Optional name for the session

        Returns:
            Path to saved session file
        """
        # Prepare state for serialization
        namespace = kernel.get_namespace()

        # Filter namespace for picklable items
        filtered_ns = {}
        unpicklable = []

        for key, value in namespace.items():
            try:
                # Test if it's picklable with dill
                dill.dumps(value)
                filtered_ns[key] = value
            except Exception:
                unpicklable.append(key)

        state = {
            "user_ns": filtered_ns,
            "execution_count": kernel.execution_count,
            "history": [
                (count, code, result.to_dict())
                for count, code, result in kernel.get_history()
            ],
            "saved_at": datetime.now().isoformat(),
            "unpicklable_vars": unpicklable,
        }

        # Determine path
        if path is None:
            name = name or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            path = self.sessions_dir / f"{name}.session"

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save with dill
        with open(path, "wb") as f:
            dill.dump(state, f)

        return path

    def load_session(self, kernel: NotebookKernel, path: Path) -> dict[str, Any]:
        """
        Load kernel state from a file.

        Args:
            kernel: NotebookKernel instance to restore into
            path: Path to session file

        Returns:
            Dictionary with load information
        """
        path = Path(path)

        with open(path, "rb") as f:
            state = dill.load(f)

        # Restore namespace
        kernel.restore_namespace(state["user_ns"])
        kernel.execution_count = state["execution_count"]

        # Clear and restore history
        kernel.clear_history()
        from notebook_lr.kernel import ExecutionResult
        for count, code, result_dict in state.get("history", []):
            result = ExecutionResult.from_dict(result_dict)
            kernel._history.append((count, code, result))

        return {
            "restored_vars": list(state["user_ns"].keys()),
            "unpicklable_vars": state.get("unpicklable_vars", []),
            "saved_at": state.get("saved_at"),
        }

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List available saved sessions.

        Returns:
            List of session info dictionaries
        """
        sessions = []
        for path in self.sessions_dir.glob("*.session"):
            try:
                with open(path, "rb") as f:
                    state = dill.load(f)
                sessions.append({
                    "path": str(path),
                    "name": path.stem,
                    "saved_at": state.get("saved_at"),
                    "var_count": len(state.get("user_ns", {})),
                })
            except Exception as e:
                sessions.append({
                    "path": str(path),
                    "name": path.stem,
                    "error": str(e),
                })
        return sorted(sessions, key=lambda x: x.get("saved_at", ""), reverse=True)

    def delete_session(self, path: Path) -> bool:
        """Delete a session file."""
        path = Path(path)
        if path.exists():
            path.unlink()
            return True
        return False

    def get_checkpoint_path(self, notebook_path: Path) -> Path:
        """Get the checkpoint path for a notebook."""
        notebook_path = Path(notebook_path)
        return self.sessions_dir / "checkpoints" / f"{notebook_path.stem}.checkpoint"

    def save_checkpoint(self, kernel: NotebookKernel, notebook_path: Path) -> Path:
        """
        Save a checkpoint for a notebook.

        Args:
            kernel: Kernel to save state from
            notebook_path: Path to the notebook

        Returns:
            Path to checkpoint file
        """
        checkpoint_path = self.get_checkpoint_path(notebook_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        return self.save_session(kernel, path=checkpoint_path)

    def load_checkpoint(self, kernel: NotebookKernel, notebook_path: Path) -> Optional[dict]:
        """
        Load checkpoint for a notebook.

        Args:
            kernel: Kernel to restore into
            notebook_path: Path to the notebook

        Returns:
            Load info or None if no checkpoint exists
        """
        checkpoint_path = self.get_checkpoint_path(notebook_path)
        if checkpoint_path.exists():
            return self.load_session(kernel, checkpoint_path)
        return None
