window.NB = window.NB || {};

NB.api = (function() {
  async function _handleResponse(res, operation, eventId) {
    // Log response
    if (eventId && NB.agentLogger) {
      NB.agentLogger.logComplete(eventId, 'success', { status: res.status });
    }

    if (!res.ok) {
      let errorMsg;
      try {
        const errorData = await res.json();
        errorMsg = errorData.error || errorData.message || res.statusText;
      } catch (e) {
        errorMsg = await res.text() || res.statusText || 'Unknown error';
      }

      // Log error
      if (eventId && NB.agentLogger) {
        NB.agentLogger.logError(eventId, new Error(errorMsg), { status: res.status });
      }

      console.error('API Error (' + operation + '):', errorMsg);
      throw new Error(errorMsg);
    }
    return res.json();
  }

  async function _get(url) {
    // Log API call start
    let eventId = null;
    if (NB.agentLogger) {
      eventId = NB.agentLogger.logStart('api_call', { method: 'GET', url: url });
    }

    try {
      const res = await fetch(url);
      return await _handleResponse(res, 'GET ' + url, eventId);
    } catch (err) {
      if (eventId && NB.agentLogger) {
        NB.agentLogger.logError(eventId, err);
      }

      if (err.name === 'TypeError' || err.message.includes('fetch')) {
        throw new Error('Network error - please check your connection');
      }
      throw err;
    }
  }

  async function _post(url, data) {
    // Log API call start
    let eventId = null;
    if (NB.agentLogger) {
      eventId = NB.agentLogger.logStart('api_call', { method: 'POST', url: url, body: data });
    }

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      return await _handleResponse(res, 'POST ' + url, eventId);
    } catch (err) {
      if (eventId && NB.agentLogger) {
        NB.agentLogger.logError(eventId, err);
      }

      if (err.name === 'TypeError' || err.message.includes('fetch')) {
        throw new Error('Network error - please check your connection');
      }
      throw err;
    }
  }

  return {
    getNotebook() { return _get('/api/notebook'); },
    addCell(afterIndex, type) { return _post('/api/cell/add', { after_index: afterIndex, type: type }); },
    deleteCell(index) { return _post('/api/cell/delete', { index: index }); },
    moveCell(index, direction) { return _post('/api/cell/move', { index: index, direction: direction }); },
    updateCell(index, source) { return _post('/api/cell/update', { index: index, source: source }); },
    executeCell(index, source) { return _post('/api/cell/execute', { index: index, source: source }); },
    executeAll() { return _post('/api/execute-all', {}); },
    save(includeSession) { return _post('/api/save', { include_session: includeSession }); },
    async load(file) {
      let eventId = null;
      if (NB.agentLogger) {
        eventId = NB.agentLogger.logStart('api_call', { method: 'POST', url: '/api/load', filename: file.name });
      }

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch('/api/load', { method: 'POST', body: formData });
        const result = await _handleResponse(res, 'POST /api/load', eventId);
        return result;
      } catch (err) {
        if (eventId && NB.agentLogger) {
          NB.agentLogger.logError(eventId, err);
        }
        throw err;
      }
    },
    getVariables() { return _get('/api/variables'); },
    clearVariables() { return _post('/api/clear-variables', {}); },
    getNotebookInfo() { return _get('/api/notebook-info'); },
    addComment(cellId, data) {
      return _post('/api/cell/comment/add', Object.assign({ cell_id: cellId }, data));
    },
    deleteComment(cellId, commentId) {
      return _post('/api/cell/comment/delete', { cell_id: cellId, comment_id: commentId });
    }
  };
})();
