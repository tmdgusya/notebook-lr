window.NB = window.NB || {};

NB.comments = (function () {
  // ── Internal State ──────────────────────────────────────────────
  var commentMarkers = {};   // { cellId: { commentId: { marker, widget } } }
  var floatingBtn = null;    // singleton floating button
  var currentSelection = null; // { cm, cellId, from, to, text }

  // ── Markdown Renderer (lightweight) ─────────────────────────────
  function renderMarkdown(text) {
    if (!text) return '';
    var html = text;

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (m, lang, code) {
      return '<pre class="comment-code-block"><code>' + escapeHtml(code.trim()) + '</code></pre>';
    });

    // Inline code (` ... `)
    html = html.replace(/`([^`]+)`/g, function (m, code) {
      return '<code class="comment-inline-code">' + escapeHtml(code) + '</code>';
    });

    // Bold (**...**)
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    return html;
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // ── Floating Button ─────────────────────────────────────────────
  function init() {
    if (floatingBtn) return;

    floatingBtn = document.createElement('button');
    floatingBtn.className = 'comment-float-btn';
    floatingBtn.textContent = 'Comment';
    floatingBtn.style.display = 'none';
    floatingBtn.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
      onCommentButtonClick();
    });
    document.body.appendChild(floatingBtn);

    // Hide floating button when clicking elsewhere
    document.addEventListener('mousedown', function (e) {
      if (floatingBtn && !floatingBtn.contains(e.target)) {
        floatingBtn.style.display = 'none';
      }
    });
  }

  function showFloatingBtn(cm, coords) {
    if (!floatingBtn) return;
    floatingBtn.style.display = 'block';
    floatingBtn.style.left = coords.left + 'px';
    floatingBtn.style.top = (coords.bottom + 4) + 'px';
  }

  function hideFloatingBtn() {
    if (floatingBtn) floatingBtn.style.display = 'none';
  }

  // ── Attach to Editor ───────────────────────────────────────────
  function attachToEditor(cm, cell) {
    var cellId = cell.id || cell.cell_id || '';

    // Listen for text selection
    cm.on('cursorActivity', function () {
      if (cm.somethingSelected()) {
        var sel = cm.getSelection();
        if (sel.trim().length > 0) {
          var from = cm.getCursor('from');
          var to = cm.getCursor('to');
          // Determine the end of selection in document order (visually bottom)
          // When dragging bottom-to-top, 'to' is at the top, so we need to use 'from'
          var endPos = (to.line > from.line || (to.line === from.line && to.ch > from.ch)) ? to : from;
          var coords = cm.charCoords(endPos, 'window');
          currentSelection = {
            cm: cm,
            cellId: cellId,
            from: { line: from.line, ch: from.ch },
            to: { line: to.line, ch: to.ch },
            text: sel
          };
          showFloatingBtn(cm, coords);
          return;
        }
      }
      // No selection — hide
      currentSelection = null;
      hideFloatingBtn();
    });

    // Restore existing comments
    restoreComments(cm, cell);
  }

  // ── Comment Button Click ───────────────────────────────────────
  function onCommentButtonClick() {
    if (!currentSelection) return;
    hideFloatingBtn();

    var sel = currentSelection;
    var cm = sel.cm;
    var cellId = sel.cellId;
    var from = sel.from;
    var to = sel.to;
    var text = sel.text;

    // Highlight selected text
    var marker = cm.markText(from, to, { className: 'cm-comment-highlight' });

    // Create inline form widget
    var formNode = createCommentForm(cm, cellId, from, to, text, marker);

    var widget = cm.addLineWidget(to.line, formNode, {
      coverGutter: false,
      noHScroll: true
    });

    // Store reference
    if (!commentMarkers[cellId]) commentMarkers[cellId] = {};
    var tempId = 'tmp_' + Date.now();
    commentMarkers[cellId][tempId] = { marker: marker, widget: widget };

    // Focus the textarea
    var textarea = formNode.querySelector('.comment-input');
    if (textarea) setTimeout(function () { textarea.focus(); }, 50);

    currentSelection = null;
  }

  // ── Comment Form ───────────────────────────────────────────────
  function createCommentForm(cm, cellId, from, to, selectedText, marker) {
    var node = document.createElement('div');
    node.className = 'inline-comment-form';

    var selectedPreview = document.createElement('div');
    selectedPreview.className = 'comment-selected-preview';
    selectedPreview.textContent = selectedText.length > 80
      ? selectedText.substring(0, 80) + '...'
      : selectedText;

    var textarea = document.createElement('textarea');
    textarea.className = 'comment-input';
    textarea.placeholder = '질문이나 코멘트를 입력하세요...';
    textarea.rows = 2;

    // Provider selection
    var selectedProvider = 'claude';
    var providerRow = document.createElement('div');
    providerRow.className = 'comment-provider-row';

    var providers = [
      { id: 'claude', label: 'Claude', color: '#1a73e8' },
      { id: 'glm',   label: 'GLM',    color: '#34a853' },
      { id: 'kimi',  label: 'Kimi',   color: '#9334e6' }
    ];

    var providerBtns = [];
    providers.forEach(function (p) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'comment-provider-btn' + (p.id === selectedProvider ? ' active' : '');
      btn.textContent = p.label;
      if (p.id === selectedProvider) {
        btn.style.borderColor = p.color;
        btn.style.color = p.color;
        btn.style.background = p.color + '12';
      }
      btn.addEventListener('mousedown', function (e) { e.preventDefault(); });
      btn.addEventListener('click', function () {
        selectedProvider = p.id;
        providerBtns.forEach(function (b) {
          b.classList.remove('active');
          b.style.borderColor = '';
          b.style.color = '';
          b.style.background = '';
        });
        btn.classList.add('active');
        btn.style.borderColor = p.color;
        btn.style.color = p.color;
        btn.style.background = p.color + '12';
        setTimeout(function () { textarea.focus(); }, 0);
      });
      providerBtns.push(btn);
      providerRow.appendChild(btn);
    });

    var btnRow = document.createElement('div');
    btnRow.className = 'comment-btn-row';

    var askBtn = document.createElement('button');
    askBtn.className = 'comment-ask-btn';
    askBtn.textContent = 'Ask AI';

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'comment-cancel-btn';
    cancelBtn.textContent = 'Cancel';

    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(askBtn);

    node.appendChild(selectedPreview);
    node.appendChild(textarea);
    node.appendChild(providerRow);
    node.appendChild(btnRow);

    // Cancel handler
    cancelBtn.addEventListener('click', function () {
      marker.clear();
      // Find and remove widget
      removeWidgetForNode(cm, cellId, node);
    });

    // Ask AI handler
    askBtn.addEventListener('click', function () {
      var userComment = textarea.value.trim();
      if (!userComment) {
        textarea.focus();
        return;
      }

      // Disable form, show spinner
      textarea.disabled = true;
      askBtn.disabled = true;
      cancelBtn.disabled = true;
      askBtn.innerHTML = '<span class="comment-spinner"></span> Asking...';

      // Log the AI call start
      var parentEventId = null;
      var aiEventId = null;
      if (NB.agentLogger) {
        parentEventId = NB.agentLogger.logStart('comment_add', {
          cellId: cellId,
          provider: selectedProvider
        });
        // Create child event for AI call
        aiEventId = NB.agentLogger.logStart('ai_call', {
          cellId: cellId,
          provider: selectedProvider,
          userComment: userComment.substring(0, 100)
        }, parentEventId);
      }

      NB.api.addComment(cellId, {
        from_line: from.line,
        from_ch: from.ch,
        to_line: to.line,
        to_ch: to.ch,
        selected_text: selectedText,
        user_comment: userComment,
        provider: selectedProvider
      }).then(function (res) {
        // Complete AI call event
        if (NB.agentLogger && aiEventId) {
          NB.agentLogger.logComplete(aiEventId, res.comment && res.comment.status === 'error' ? 'error' : 'success', {
            commentId: res.comment ? res.comment.id : null
          });
        }

        // Complete parent event
        if (NB.agentLogger && parentEventId) {
          NB.agentLogger.logComplete(parentEventId, res.comment && res.comment.status === 'error' ? 'error' : 'success');
        }

        if (res.ok && res.comment) {
          replaceFormWithResult(cm, cellId, node, marker, res.comment);
        } else {
          askBtn.textContent = 'Ask AI';
          askBtn.disabled = false;
          textarea.disabled = false;
          cancelBtn.disabled = false;
        }
      }).catch(function (err) {
        console.error('Comment error:', err);

        // Check for timeout
        var isTimeout = err.message && (
          err.message.includes('timeout') ||
          err.message.includes('시간 초과') ||
          err.message.includes('시간초과') ||
          err.message.includes('time out')
        );

        if (NB.agentLogger && aiEventId) {
          if (isTimeout) {
            NB.agentLogger.logTimeout(aiEventId, 120000); // 2 min default timeout
          } else {
            NB.agentLogger.logError(aiEventId, err);
          }
        }

        if (NB.agentLogger && parentEventId) {
          NB.agentLogger.logError(parentEventId, err);
        }

        askBtn.textContent = 'Ask AI';
        askBtn.disabled = false;
        textarea.disabled = false;
        cancelBtn.disabled = false;
      });
    });

    // Allow Ctrl/Cmd+Enter to submit
    textarea.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        askBtn.click();
      }
    });

    return node;
  }

  // ── Result Widget ──────────────────────────────────────────────
  function createResultWidget(cm, cellId, comment) {
    var node = document.createElement('div');
    node.className = 'inline-comment-widget';
    node.dataset.commentId = comment.id;

    // Header: user question + provider badge
    var header = document.createElement('div');
    header.className = 'comment-header';

    var userQ = document.createElement('div');
    userQ.className = 'comment-user-question';
    userQ.textContent = comment.user_comment;

    // Provider badge
    var providerColors = { claude: '#1a73e8', glm: '#34a853', kimi: '#9334e6' };
    var providerLabels = { claude: 'Claude', glm: 'GLM', kimi: 'Kimi' };
    var prov = comment.provider || 'claude';
    var badge = document.createElement('span');
    badge.className = 'comment-provider-badge';
    badge.textContent = providerLabels[prov] || prov;
    badge.style.borderColor = providerColors[prov] || '#5f6368';
    badge.style.color = providerColors[prov] || '#5f6368';

    var deleteBtn = document.createElement('button');
    deleteBtn.className = 'comment-delete-btn';
    deleteBtn.title = 'Delete comment';
    deleteBtn.innerHTML = '&times;';
    deleteBtn.addEventListener('click', function () {
      removeComment(cellId, comment.id);
    });

    header.appendChild(userQ);
    header.appendChild(badge);
    header.appendChild(deleteBtn);

    // Response body
    var response = document.createElement('div');
    response.className = 'comment-response';

    if (comment.status === 'error') {
      response.classList.add('comment-error');
      response.textContent = comment.ai_response;
    } else {
      response.innerHTML = renderMarkdown(comment.ai_response);
    }

    node.appendChild(header);
    node.appendChild(response);

    return node;
  }

  function replaceFormWithResult(cm, cellId, formNode, marker, comment) {
    // Remove old widget that contains formNode
    var oldWidgetInfo = findWidgetByNode(cellId, formNode);

    var resultNode = createResultWidget(cm, cellId, comment);

    // Add new widget at the same line
    var markerPos = marker.find();
    var line = markerPos ? markerPos.to.line : 0;
    var newWidget = cm.addLineWidget(line, resultNode, {
      coverGutter: false,
      noHScroll: true
    });

    // Clean up old temp entry, add real one
    if (oldWidgetInfo) {
      oldWidgetInfo.widget.clear();
      delete commentMarkers[cellId][oldWidgetInfo.tempId];
    }

    if (!commentMarkers[cellId]) commentMarkers[cellId] = {};
    commentMarkers[cellId][comment.id] = { marker: marker, widget: newWidget };
  }

  // ── Restore Comments ───────────────────────────────────────────
  function restoreComments(cm, cell) {
    var cellId = cell.id || cell.cell_id || '';
    var comments = cell.comments || [];
    if (comments.length === 0) return;

    if (!commentMarkers[cellId]) commentMarkers[cellId] = {};

    comments.forEach(function (comment) {
      var from = { line: comment.from_line, ch: comment.from_ch };
      var to = { line: comment.to_line, ch: comment.to_ch };

      // Validate coordinates are within editor bounds
      var lastLine = cm.lastLine();
      if (from.line > lastLine || to.line > lastLine) return;

      // Check text still matches
      var currentText = cm.getRange(from, to);
      var isStale = currentText !== comment.selected_text;

      // Create highlight marker
      var markerClass = isStale ? 'cm-comment-highlight cm-comment-stale' : 'cm-comment-highlight';
      var marker = cm.markText(from, to, { className: markerClass });

      // Create result widget
      var resultNode = createResultWidget(cm, cellId, comment);
      if (isStale) {
        var staleWarning = document.createElement('div');
        staleWarning.className = 'comment-stale-warning';
        staleWarning.textContent = '⚠ Code has changed since this comment was added';
        resultNode.insertBefore(staleWarning, resultNode.firstChild);
      }

      var widget = cm.addLineWidget(to.line, resultNode, {
        coverGutter: false,
        noHScroll: true
      });

      commentMarkers[cellId][comment.id] = { marker: marker, widget: widget };
    });
  }

  // ── Remove Comment ─────────────────────────────────────────────
  function removeComment(cellId, commentId) {
    // Remove from backend
    NB.api.deleteComment(cellId, commentId).catch(function (err) {
      console.error('Failed to delete comment:', err);
    });

    // Remove marker and widget
    if (commentMarkers[cellId] && commentMarkers[cellId][commentId]) {
      var entry = commentMarkers[cellId][commentId];
      if (entry.marker) entry.marker.clear();
      if (entry.widget) entry.widget.clear();
      delete commentMarkers[cellId][commentId];
    }
  }

  // ── Clear All ──────────────────────────────────────────────────
  function clearAll() {
    Object.keys(commentMarkers).forEach(function (cellId) {
      Object.keys(commentMarkers[cellId]).forEach(function (commentId) {
        var entry = commentMarkers[cellId][commentId];
        if (entry.marker) entry.marker.clear();
        if (entry.widget) entry.widget.clear();
      });
    });
    commentMarkers = {};
  }

  // ── Helpers ────────────────────────────────────────────────────
  function removeWidgetForNode(cm, cellId, node) {
    if (!commentMarkers[cellId]) return;
    var keys = Object.keys(commentMarkers[cellId]);
    for (var i = 0; i < keys.length; i++) {
      var entry = commentMarkers[cellId][keys[i]];
      if (entry.widget) {
        entry.widget.clear();
        if (entry.marker) entry.marker.clear();
        delete commentMarkers[cellId][keys[i]];
        return;
      }
    }
  }

  function findWidgetByNode(cellId, node) {
    if (!commentMarkers[cellId]) return null;
    var keys = Object.keys(commentMarkers[cellId]);
    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];
      if (key.indexOf('tmp_') === 0) {
        return { tempId: key, widget: commentMarkers[cellId][key].widget };
      }
    }
    return null;
  }

  // ── Public API ─────────────────────────────────────────────────
  return {
    init: init,
    attachToEditor: attachToEditor,
    restoreComments: restoreComments,
    removeComment: removeComment,
    clearAll: clearAll
  };
})();
