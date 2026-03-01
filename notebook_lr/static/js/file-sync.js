/**
 * File Sync - Polls for external file changes and handles conflicts
 */
window.NB = window.NB || {};

NB.fileSync = (function() {
  var POLL_INTERVAL = 4000; // 4 seconds
  var SAVE_COOLDOWN = 2000; // Skip polling for 2s after save

  var _timer = null;
  var _isPolling = false;
  var _dialogOpen = false;
  var _lastSaveTime = 0;

  /**
   * Start polling for external changes
   */
  function start() {
    if (_timer) return;
    _isPolling = true;
    _schedulePoll();
    _listenVisibility();
  }

  /**
   * Stop polling
   */
  function stop() {
    _isPolling = false;
    if (_timer) {
      clearTimeout(_timer);
      _timer = null;
    }
  }

  /**
   * Notify that a save just happened (to avoid false positives)
   */
  function notifySaved() {
    _lastSaveTime = Date.now();
  }

  /**
   * Schedule next poll
   */
  function _schedulePoll() {
    if (!_isPolling) return;
    _timer = setTimeout(function() {
      _timer = null;
      _poll();
    }, POLL_INTERVAL);
  }

  /**
   * Pause/resume polling based on page visibility
   */
  function _listenVisibility() {
    document.addEventListener('visibilitychange', function() {
      if (document.hidden) {
        if (_timer) {
          clearTimeout(_timer);
          _timer = null;
        }
      } else if (_isPolling && !_timer && !_dialogOpen) {
        _schedulePoll();
      }
    });
  }

  /**
   * Poll the server for changes
   */
  async function _poll() {
    if (_dialogOpen || document.hidden) {
      _schedulePoll();
      return;
    }

    // Skip if we just saved
    if (Date.now() - _lastSaveTime < SAVE_COOLDOWN) {
      _schedulePoll();
      return;
    }

    try {
      var res = await fetch('/api/notebook/check-updates');
      var data = await res.json();

      if (data.changed) {
        _log('FILE_CHANGE_DETECTED', { action: '외부 파일 변경 감지' });
        _handleChange();
      } else {
        _schedulePoll();
      }
    } catch (err) {
      console.error('File sync poll error:', err);
      _logError('FILE_POLL_ERROR', err);
      _schedulePoll();
    }
  }

  /**
   * Handle detected external change
   */
  function _handleChange() {
    var isDirty = NB.fileops && NB.fileops._isDirty;

    if (!isDirty) {
      // No local modifications — auto-reload
      _autoReload();
    } else {
      // Local modifications exist — show conflict dialog
      _showConflictDialog();
    }
  }

  /**
   * Auto-reload when no local changes
   */
  async function _autoReload() {
    try {
      var res = await fetch('/api/notebook/reload', { method: 'POST' });
      var data = await res.json();

      if (data.cells) {
        NB.cells.renderAll(data.cells);
        NB.toolbar.updateInfo();
      }

      _log('FILE_AUTO_RELOAD', { action: '자동 리로드 완료', cellCount: data.cells ? data.cells.length : 0 });
      _showToast('파일이 외부에서 변경되어 리로드되었습니다.');
      _schedulePoll();
    } catch (err) {
      console.error('Auto-reload failed:', err);
      _logError('FILE_POLL_ERROR', err);
      _showToast('자동 리로드 실패: ' + err.message, true);
      _schedulePoll();
    }
  }

  /**
   * Show conflict resolution dialog
   */
  function _showConflictDialog() {
    _dialogOpen = true;
    _log('FILE_CONFLICT', { action: '충돌 다이얼로그 표시', dirty: true });

    // Create modal
    var modal = document.createElement('div');
    modal.id = 'file-conflict-modal';
    modal.className = 'modal';

    modal.innerHTML =
      '<div class="modal-overlay modal-overlay-block"></div>' +
      '<div class="modal-content">' +
        '<div class="modal-header">' +
          '<h3>외부 파일 변경 감지</h3>' +
        '</div>' +
        '<div class="modal-body">' +
          '<p>파일이 외부에서 변경되었습니다. 현재 저장하지 않은 수정 사항이 있습니다.</p>' +
          '<div class="conflict-actions">' +
            '<button id="conflict-reload-btn" class="toolbar-btn toolbar-btn-primary">외부 변경 반영 (Reload)</button>' +
            '<button id="conflict-keep-btn" class="toolbar-btn">내 수정 유지 (Keep mine)</button>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.body.appendChild(modal);

    document.getElementById('conflict-reload-btn').addEventListener('click', function() {
      _resolveConflict('reload', modal);
    });
    document.getElementById('conflict-keep-btn').addEventListener('click', function() {
      _resolveConflict('keep', modal);
    });
  }

  /**
   * Resolve conflict based on user choice
   */
  async function _resolveConflict(choice, modal) {
    try {
      if (choice === 'reload') {
        var res = await fetch('/api/notebook/reload', { method: 'POST' });
        var data = await res.json();

        if (data.cells) {
          NB.cells.renderAll(data.cells);
          NB.toolbar.updateInfo();
          if (NB.fileops) {
            NB.fileops._isDirty = false;
            NB.fileops._updateIndicator('saved');
          }
        }
        _showToast('외부 변경이 반영되었습니다.');
      } else {
        // Keep mine — acknowledge the external change
        await fetch('/api/notebook/acknowledge', { method: 'POST' });
        _showToast('내 수정 사항을 유지합니다.');
      }
      _log('FILE_CONFLICT_RESOLVED', { action: choice === 'reload' ? '외부 변경 반영' : '내 수정 유지', choice: choice });
    } catch (err) {
      console.error('Conflict resolution failed:', err);
      _logError('FILE_POLL_ERROR', err);
      _showToast('처리 실패: ' + err.message, true);
    }

    // Close dialog and resume polling
    modal.remove();
    _dialogOpen = false;
    _schedulePoll();
  }

  /**
   * Show a toast notification
   */
  function _showToast(message, isError) {
    // Remove any existing toast
    var existing = document.getElementById('file-sync-toast');
    if (existing) existing.remove();

    var toast = document.createElement('div');
    toast.id = 'file-sync-toast';
    toast.className = 'file-sync-toast' + (isError ? ' toast-error' : '');
    toast.textContent = message;
    document.body.appendChild(toast);

    // Auto-dismiss after 4 seconds
    setTimeout(function() {
      if (toast.parentNode) {
        toast.classList.add('toast-fade');
        setTimeout(function() { toast.remove(); }, 300);
      }
    }, 4000);
  }

  /**
   * Log a file-sync event to agent-logger (guarded)
   */
  function _log(type, data) {
    if (NB.agentLogger && NB.agentLogger.EventType[type]) {
      var id = NB.agentLogger.logStart(NB.agentLogger.EventType[type], data);
      NB.agentLogger.logComplete(id, NB.agentLogger.EventStatus.SUCCESS);
    }
  }

  /**
   * Log a file-sync error to agent-logger (guarded)
   */
  function _logError(type, err) {
    if (NB.agentLogger && NB.agentLogger.EventType[type]) {
      var id = NB.agentLogger.logStart(NB.agentLogger.EventType[type], {});
      NB.agentLogger.logError(id, err);
    }
  }

  return {
    start: start,
    stop: stop,
    notifySaved: notifySaved,
  };
})();
