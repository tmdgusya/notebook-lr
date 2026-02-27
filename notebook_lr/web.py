"""
Web interface for notebook-lr using Flask.
"""

import sys
import tempfile
from pathlib import Path
from typing import Optional

from notebook_lr import NotebookKernel, Notebook, Cell, CellType, Comment, SessionManager
from notebook_lr.utils import format_output


def launch_web(notebook: Optional[Notebook] = None, share: bool = False):
    """
    Launch the Flask web interface.

    Args:
        notebook: Optional notebook to load
        share: Whether to create a public share link (unused for Flask, kept for API compat)
    """
    from flask import Flask, render_template, request, jsonify

    kernel = NotebookKernel()
    session_manager = SessionManager()

    if notebook is None:
        notebook = Notebook.new()

    # Load session if available
    if notebook.metadata.get("path"):
        checkpoint_info = session_manager.load_checkpoint(
            kernel, Path(notebook.metadata["path"])
        )
        if checkpoint_info:
            print(
                f"Restored session with {len(checkpoint_info['restored_vars'])} variables"
            )

    tmpl_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    app = Flask(__name__, template_folder=str(tmpl_dir), static_folder=str(static_dir))

    # ------------------------------------------------------------------ #
    # Helper
    # ------------------------------------------------------------------ #

    def _cell_dict(cell: Cell, index: int) -> dict:
        return {
            "index": index,
            "id": cell.id,
            "type": cell.type.value,
            "source": cell.source,
            "outputs": cell.outputs,
            "execution_count": cell.execution_count,
            "comments": [c.model_dump() for c in cell.comments],
        }

    def _format_outputs(outputs: list) -> tuple[str, str]:
        """Return (output_text, error_text) for a list of output dicts."""
        output_text = ""
        error_text = ""
        for output in outputs:
            text = format_output(output)
            if output.get("type") == "error":
                error_text += text + "\n"
            else:
                output_text += text + "\n"
        return output_text.strip(), error_text.strip()

    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #

    @app.route("/")
    def index():
        return render_template("notebook.html")

    @app.route("/api/notebook", methods=["GET"])
    def api_notebook():
        cells = [_cell_dict(c, i) for i, c in enumerate(notebook.cells)]
        return jsonify({
            "version": notebook.version,
            "metadata": notebook.metadata,
            "cells": cells,
        })

    @app.route("/api/cell/add", methods=["POST"])
    def api_cell_add():
        data = request.get_json(force=True) or {}
        after_index = data.get("after_index")
        cell_type_str = data.get("type", "code")
        ct = CellType.CODE if cell_type_str == "code" else CellType.MARKDOWN
        cell = Cell(type=ct, source="")

        if after_index is not None:
            new_idx = int(after_index) + 1
        else:
            new_idx = len(notebook.cells)

        notebook.insert_cell(new_idx, cell)
        return jsonify({"cell": _cell_dict(cell, new_idx), "index": new_idx})

    @app.route("/api/cell/delete", methods=["POST"])
    def api_cell_delete():
        data = request.get_json(force=True) or {}
        index = int(data.get("index", -1))
        if 0 <= index < len(notebook.cells):
            notebook.remove_cell(index)
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "index out of range"}), 400

    @app.route("/api/cell/move", methods=["POST"])
    def api_cell_move():
        data = request.get_json(force=True) or {}
        index = int(data.get("index", -1))
        direction = data.get("direction", "up")

        if direction == "up":
            if 0 < index < len(notebook.cells):
                notebook.cells[index], notebook.cells[index - 1] = (
                    notebook.cells[index - 1],
                    notebook.cells[index],
                )
                new_index = index - 1
                return jsonify({"ok": True, "new_index": new_index})
        elif direction == "down":
            if 0 <= index < len(notebook.cells) - 1:
                notebook.cells[index], notebook.cells[index + 1] = (
                    notebook.cells[index + 1],
                    notebook.cells[index],
                )
                new_index = index + 1
                return jsonify({"ok": True, "new_index": new_index})

        return jsonify({"ok": False, "error": "cannot move cell in that direction"}), 400

    @app.route("/api/cell/update", methods=["POST"])
    def api_cell_update():
        data = request.get_json(force=True) or {}
        index = int(data.get("index", -1))
        source = data.get("source", "")
        if 0 <= index < len(notebook.cells):
            notebook.cells[index].source = source
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "index out of range"}), 400

    @app.route("/api/cell/execute", methods=["POST"])
    def api_cell_execute():
        data = request.get_json(force=True) or {}
        index = int(data.get("index", -1))
        source = data.get("source", None)

        if not (0 <= index < len(notebook.cells)):
            return jsonify({"error": "index out of range"}), 400

        cell = notebook.cells[index]
        if source is not None:
            cell.source = source

        if cell.type == CellType.MARKDOWN:
            return jsonify({
                "outputs": [],
                "execution_count": None,
                "success": True,
                "error": None,
            })

        result = kernel.execute_cell(cell.source)
        cell.outputs = result.outputs
        cell.execution_count = result.execution_count

        output_text, error_text = _format_outputs(result.outputs)
        return jsonify({
            "outputs": result.outputs,
            "execution_count": result.execution_count,
            "success": result.success,
            "error": result.error,
            "output_text": output_text,
            "error_text": error_text,
        })

    @app.route("/api/execute-all", methods=["POST"])
    def api_execute_all():
        results = []
        for i, cell in enumerate(notebook.cells):
            if cell.type == CellType.CODE and cell.source.strip():
                result = kernel.execute_cell(cell.source)
                cell.outputs = result.outputs
                cell.execution_count = result.execution_count

                output_text, error_text = _format_outputs(result.outputs)
                results.append({
                    "index": i,
                    "outputs": result.outputs,
                    "execution_count": result.execution_count,
                    "success": result.success,
                    "error": result.error,
                    "output_text": output_text,
                    "error_text": error_text,
                })
                if not result.success:
                    break

        return jsonify({"results": results})

    @app.route("/api/save", methods=["POST"])
    def api_save():
        data = request.get_json(force=True) or {}
        include_session = bool(data.get("include_session", False))
        path = notebook.metadata.get("path", "notebook.nblr")

        if include_session:
            session_data = {
                "user_ns": kernel.get_namespace(),
                "execution_count": kernel.execution_count,
            }
            notebook.save(
                Path(path), include_session=True, session_data=session_data
            )
            session_manager.save_checkpoint(kernel, Path(path))
        else:
            notebook.save(Path(path))

        return jsonify({
            "status": "saved" + (" (with session)" if include_session else ""),
            "path": path,
        })

    @app.route("/api/load", methods=["POST"])
    def api_load():
        nonlocal notebook
        if "file" not in request.files:
            return jsonify({"error": "no file provided"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "empty filename"}), 400

        suffix = Path(file.filename).suffix or ".nblr"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            tmp_path = Path(tmp.name)

        notebook = Notebook.load(tmp_path)
        notebook.metadata["path"] = file.filename
        tmp_path.unlink(missing_ok=True)

        cells = [_cell_dict(c, i) for i, c in enumerate(notebook.cells)]
        return jsonify({"cells": cells, "metadata": notebook.metadata})

    @app.route("/api/variables", methods=["GET"])
    def api_variables():
        names = kernel.get_defined_names()
        variables = []
        for name in sorted(names):
            value = kernel.get_variable(name)
            var_type = type(value).__name__
            val_repr = repr(value)
            if len(val_repr) > 200:
                val_repr = val_repr[:197] + "..."
            variables.append({"name": name, "type": var_type, "value": val_repr})
        return jsonify({"variables": variables})

    @app.route("/api/clear-variables", methods=["POST"])
    def api_clear_variables():
        kernel.reset()
        return jsonify({"ok": True})

    @app.route("/api/notebook-info", methods=["GET"])
    def api_notebook_info():
        name = notebook.metadata.get("name", "Untitled")
        cell_count = len(notebook.cells)
        code_count = sum(1 for c in notebook.cells if c.type == CellType.CODE)
        md_count = cell_count - code_count
        executed_count = sum(
            1 for c in notebook.cells if c.execution_count is not None
        )
        return jsonify({
            "name": name,
            "cell_count": cell_count,
            "code_count": code_count,
            "md_count": md_count,
            "executed_count": executed_count,
        })

    # ------------------------------------------------------------------ #
    # Comment helpers & routes
    # ------------------------------------------------------------------ #

    def _find_cell_by_id(cell_id: str) -> Optional[Cell]:
        for cell in notebook.cells:
            if cell.id == cell_id:
                return cell
        return None

    def _build_provider_env(provider: str) -> dict:
        """Build environment dict for subprocess based on provider."""
        import os
        env = os.environ.copy()

        if provider == "glm":
            token = os.environ.get("GT_GLM_AUTH_TOKEN")
            base_url = os.environ.get("GT_GLM_BASE_URL")
            if not token or not base_url:
                raise ValueError("GLM 환경변수(GT_GLM_AUTH_TOKEN, GT_GLM_BASE_URL)가 설정되지 않았습니다")
            env["ANTHROPIC_AUTH_TOKEN"] = token
            env["ANTHROPIC_BASE_URL"] = base_url
            env["ANTHROPIC_VERSION"] = "2023-06-01"
        elif provider == "kimi":
            token = os.environ.get("GT_KIMI_AUTH_TOKEN")
            base_url = os.environ.get("GT_KIMI_BASE_URL")
            model = os.environ.get("GT_KIMI_MODEL")
            if not token or not base_url:
                raise ValueError("Kimi 환경변수(GT_KIMI_AUTH_TOKEN, GT_KIMI_BASE_URL)가 설정되지 않았습니다")
            env["ANTHROPIC_AUTH_TOKEN"] = token
            env["ANTHROPIC_BASE_URL"] = base_url
            if model:
                env["ANTHROPIC_MODEL"] = model
        else:
            # claude: remove any overrides so native Anthropic is used
            env.pop("ANTHROPIC_AUTH_TOKEN", None)
            env.pop("ANTHROPIC_BASE_URL", None)
            env.pop("ANTHROPIC_MODEL", None)
            env.pop("ANTHROPIC_VERSION", None)

        return env

    def _call_ai(cell_source: str, selected_text: str, user_comment: str, provider: str = "claude") -> str:
        import subprocess

        prompt = f"""다음은 Python 노트북 셀의 전체 코드입니다:

```python
{cell_source}
```

사용자가 다음 부분을 선택했습니다:
```
{selected_text}
```

사용자의 질문: {user_comment}

선택된 코드에 대해 교육적인 답변을 한국어로 제공해주세요."""

        try:
            env = _build_provider_env(provider)
        except ValueError as e:
            return f"Error: {e}"

        try:
            result = subprocess.run(
                ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                capture_output=True, text=True, timeout=120, env=env
            )
            return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "Error: AI 응답 시간 초과"
        except FileNotFoundError:
            return "Error: claude CLI를 찾을 수 없습니다"

    @app.route("/api/cell/comment/add", methods=["POST"])
    def api_cell_comment_add():
        data = request.get_json(force=True) or {}
        cell_id = data.get("cell_id", "")
        cell = _find_cell_by_id(cell_id)
        if not cell:
            return jsonify({"ok": False, "error": "cell not found"}), 404

        provider = data.get("provider", "claude")
        if provider not in ("claude", "glm", "kimi"):
            provider = "claude"

        comment = Comment(
            from_line=int(data.get("from_line", 0)),
            from_ch=int(data.get("from_ch", 0)),
            to_line=int(data.get("to_line", 0)),
            to_ch=int(data.get("to_ch", 0)),
            selected_text=data.get("selected_text", ""),
            user_comment=data.get("user_comment", ""),
            provider=provider,
            status="loading",
        )

        ai_response = _call_ai(cell.source, comment.selected_text, comment.user_comment, provider)
        if ai_response.startswith("Error:"):
            comment.status = "error"
        else:
            comment.status = "resolved"
        comment.ai_response = ai_response

        cell.comments.append(comment)
        notebook._touch()

        return jsonify({"ok": True, "comment": comment.model_dump()})

    @app.route("/api/cell/comment/delete", methods=["POST"])
    def api_cell_comment_delete():
        data = request.get_json(force=True) or {}
        cell_id = data.get("cell_id", "")
        comment_id = data.get("comment_id", "")
        cell = _find_cell_by_id(cell_id)
        if not cell:
            return jsonify({"ok": False, "error": "cell not found"}), 404

        cell.comments = [c for c in cell.comments if c.id != comment_id]
        notebook._touch()

        return jsonify({"ok": True})

    # ------------------------------------------------------------------ #
    # Launch
    # ------------------------------------------------------------------ #

    # Temporarily clear sys.ps1 so Flask doesn't think we're in an
    # interactive REPL (IPython's InteractiveShell sets sys.ps1).
    _ps1 = getattr(sys, "ps1", None)
    _had_ps1 = hasattr(sys, "ps1")
    if _had_ps1:
        del sys.ps1
    try:
        app.run(host="0.0.0.0", port=7860, debug=False)
    finally:
        if _had_ps1:
            sys.ps1 = _ps1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        nb = Notebook.load(Path(sys.argv[1]))
        launch_web(nb)
    else:
        launch_web()
