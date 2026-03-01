"""
Web interface for notebook-lr using Flask.
"""

import os
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

    # Track file mtime for external change detection
    _last_file_mtime = 0.0
    if notebook.metadata.get("path") and os.path.isfile(notebook.metadata["path"]):
        _last_file_mtime = os.path.getmtime(notebook.metadata["path"])

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

    def _auto_save_if_path():
        nonlocal _last_file_mtime
        path = notebook.metadata.get("path")
        if path:
            notebook.save(Path(path))
            _last_file_mtime = os.path.getmtime(path)

    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #

    debug_panel_enabled = os.environ.get("DEBUG_PANEL_ENABLED", "0") == "1"

    @app.route("/")
    def index():
        return render_template("notebook.html", debug_panel_enabled=debug_panel_enabled)

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
        _auto_save_if_path()
        return jsonify({"cell": _cell_dict(cell, new_idx), "index": new_idx})

    @app.route("/api/cell/delete", methods=["POST"])
    def api_cell_delete():
        data = request.get_json(force=True) or {}
        index = int(data.get("index", -1))
        if 0 <= index < len(notebook.cells):
            notebook.remove_cell(index)
            _auto_save_if_path()
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
                _auto_save_if_path()
                return jsonify({"ok": True, "new_index": new_index})
        elif direction == "down":
            if 0 <= index < len(notebook.cells) - 1:
                notebook.cells[index], notebook.cells[index + 1] = (
                    notebook.cells[index + 1],
                    notebook.cells[index],
                )
                new_index = index + 1
                _auto_save_if_path()
                return jsonify({"ok": True, "new_index": new_index})

        return jsonify({"ok": False, "error": "cannot move cell in that direction"}), 400

    @app.route("/api/cell/update", methods=["POST"])
    def api_cell_update():
        data = request.get_json(force=True) or {}
        index = int(data.get("index", -1))
        source = data.get("source", "")
        if 0 <= index < len(notebook.cells):
            notebook.cells[index].source = source
            _auto_save_if_path()
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
        _auto_save_if_path()

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
        nonlocal _last_file_mtime
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

        _last_file_mtime = os.path.getmtime(path)
        return jsonify({
            "status": "saved" + (" (with session)" if include_session else ""),
            "path": path,
            "mtime": _last_file_mtime,
        })

    @app.route("/api/load", methods=["POST"])
    def api_load():
        nonlocal notebook, _last_file_mtime
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
        _last_file_mtime = 0.0

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

    @app.route("/api/notebook/check-updates", methods=["GET"])
    def api_check_updates():
        nonlocal _last_file_mtime
        path = notebook.metadata.get("path")
        if not path or not os.path.isfile(path):
            return jsonify({"changed": False})

        current_mtime = os.path.getmtime(path)
        if current_mtime == _last_file_mtime:
            return jsonify({"changed": False})

        # File changed externally - report only, do NOT reload
        return jsonify({"changed": True})

    @app.route("/api/notebook/reload", methods=["POST"])
    def api_reload():
        """Explicitly reload notebook from disk (used after user confirms reload)."""
        nonlocal notebook, _last_file_mtime
        path = notebook.metadata.get("path")
        if not path or not os.path.isfile(path):
            return jsonify({"error": "no file path available"}), 400

        _last_file_mtime = os.path.getmtime(path)
        notebook = Notebook.load(Path(path))
        notebook.metadata["path"] = path
        cells = [_cell_dict(c, i) for i, c in enumerate(notebook.cells)]
        return jsonify({"cells": cells, "metadata": notebook.metadata, "mtime": _last_file_mtime})

    @app.route("/api/notebook/acknowledge", methods=["POST"])
    def api_acknowledge():
        """Acknowledge external change without reloading (user chose 'Keep mine')."""
        nonlocal _last_file_mtime
        path = notebook.metadata.get("path")
        if not path or not os.path.isfile(path):
            return jsonify({"error": "no file path available"}), 400

        _last_file_mtime = os.path.getmtime(path)
        return jsonify({"acknowledged": True, "mtime": _last_file_mtime})

    # ------------------------------------------------------------------ #
    # Comment helpers & routes
    # ------------------------------------------------------------------ #
    import logging
    logger = logging.getLogger(__name__)

    def _find_cell_by_id(cell_id: str) -> Optional[Cell]:
        for cell in notebook.cells:
            if cell.id == cell_id:
                return cell
        return None

    def _load_gt_env(provider_cmd: str) -> dict:
        """Source ~/gl-switcher/gt.sh, run 'gt <cmd>', return ANTHROPIC_*/API_TIMEOUT_* vars."""
        import subprocess, os
        gt_path = os.path.expanduser("~/gl-switcher/gt.sh")
        if not os.path.isfile(gt_path):
            raise ValueError(f"gt.sh를 찾을 수 없습니다: {gt_path}")

        script = f'source "{gt_path}" && gt {provider_cmd} >/dev/null 2>&1 && env'
        user_shell = os.environ.get('SHELL', '/bin/bash')
        result = subprocess.run(
            [user_shell, '-ic', script],
            capture_output=True, text=True,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            raise ValueError(f"gt {provider_cmd} 실행 실패: {result.stderr.strip()}")

        env = {}
        for line in result.stdout.splitlines():
            key, _, value = line.partition('=')
            if key.startswith("ANTHROPIC_") or key.startswith("API_TIMEOUT"):
                env[key] = value
        return env

    _PLACEHOLDER_TOKENS = {"your-z-ai-token-here", "your-kimi-token-here"}

    def _build_provider_env(provider: str) -> dict:
        """Build environment dict for subprocess based on provider."""
        import os
        env = os.environ.copy()

        if provider == "claude":
            # claude uses default env; clean up any overrides that leaked
            # from the parent process environment
            for k in ["ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                       "ANTHROPIC_MODEL", "ANTHROPIC_VERSION"]:
                env.pop(k, None)
            return env

        # Non-claude providers need gt.sh for token switching
        cmd_map = {"glm": "g", "kimi": "k"}
        cmd = cmd_map.get(provider, "c")
        gt_vars = _load_gt_env(cmd)
        env.update(gt_vars)

        # Validate that the token is not a gt.sh placeholder
        token = env.get("ANTHROPIC_AUTH_TOKEN", "")
        if token in _PLACEHOLDER_TOKENS:
            raise ValueError(f"{provider} API 토큰이 설정되지 않았습니다. ANTHROPIC_AUTH_TOKEN을 확인해주세요.")

        return env

    def _build_comment_context(nb, cell: Cell, cell_id: str) -> str:
        """Build rich context string about the cell and its surroundings."""
        # Find cell index
        index = None
        for i, c in enumerate(nb.cells):
            if c.id == cell_id:
                index = i
                break
        total = len(nb.cells)

        lines = []
        if index is not None:
            lines.append(f"이 코멘트는 셀 #{index + 1} (총 {total}개 중)에서 작성되었습니다.")
        lines.append(f"셀 유형: {cell.type.value}")

        # Neighboring cells summary
        def cell_summary(c: Cell, label: str) -> str:
            src_lines = c.source.splitlines()[:3]
            preview = "\n".join(src_lines)
            return f"{label} (유형: {c.type.value}):\n{preview}"

        if index is not None and index > 0:
            prev_cell = nb.cells[index - 1]
            lines.append(cell_summary(prev_cell, "이전 셀"))
        if index is not None and index < total - 1:
            next_cell = nb.cells[index + 1]
            lines.append(cell_summary(next_cell, "다음 셀"))

        # Cell outputs
        if cell.outputs:
            outputs_repr = repr(cell.outputs)
            if len(outputs_repr) > 500:
                outputs_repr = outputs_repr[:500] + "..."
            lines.append(f"셀 출력:\n{outputs_repr}")

        # Other comments on same cell
        other_comments = [c for c in cell.comments]
        if other_comments:
            lines.append("이 셀의 기존 코멘트:")
            for cm in other_comments:
                lines.append(f"  - [{cm.status}] 사용자: {cm.user_comment}")

        return "\n\n".join(lines)

    def _call_ai(cell_source: str, selected_text: str, user_comment: str, provider: str = "claude", context: str = "") -> str:
        import subprocess

        context_section = f"\n\n## 노트북 컨텍스트\n{context}" if context else ""

        prompt = f"""다음은 Python 노트북 셀의 전체 코드입니다:

```python
{cell_source}
```

사용자가 다음 부분을 선택했습니다:
```
{selected_text}
```

사용자의 질문: {user_comment}{context_section}

## 중요 안내

당신은 노트북을 직접 수정할 수 없습니다. MCP 도구에 접근할 수 없습니다.
절대로 "수정했습니다", "분할했습니다", "변경을 적용했습니다" 등 직접 수정한 것처럼 답변하지 마세요.

대신 다음과 같이 답변해주세요:
- 코드에 대한 설명, 분석, 개선 제안
- 수정이 필요한 경우: 수정된 코드를 코드 블록으로 제시하고, 사용자가 직접 적용하도록 안내
- 셀 분할이 필요한 경우: 각 셀의 코드를 별도 코드 블록으로 제시

선택된 코드에 대해 교육적인 답변을 한국어로 제공해주세요."""

        try:
            env = _build_provider_env(provider)
        except ValueError as e:
            return f"Error: {e}"

        logger.info("AI call started: provider=%s", provider)
        try:
            result = subprocess.run(
                ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                capture_output=True, text=True, timeout=120, env=env
            )
            if result.returncode == 0:
                logger.info("AI call completed: provider=%s, response_length=%d", provider, len(result.stdout))
                return result.stdout.strip()
            else:
                logger.error("AI call failed: provider=%s, error=%s", provider, result.stderr.strip())
                return f"Error: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            logger.error("AI call timeout: provider=%s", provider)
            return "Error: AI 응답 시간 초과"
        except FileNotFoundError:
            return "Error: claude CLI를 찾을 수 없습니다. 'npm install -g @anthropic-ai/claude-code'로 설치해주세요."

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

        # Validate provider env vars before creating a comment
        try:
            _build_provider_env(provider)
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

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

        ctx = _build_comment_context(notebook, cell, cell_id)
        ai_response = _call_ai(cell.source, comment.selected_text, comment.user_comment, provider, context=ctx)
        if ai_response.startswith("Error:"):
            comment.status = "error"
        else:
            comment.status = "resolved"
        comment.ai_response = ai_response

        cell.comments.append(comment)
        notebook._touch()
        _auto_save_if_path()

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
        _auto_save_if_path()

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
