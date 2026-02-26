window.NB = window.NB || {};

NB.api = (function() {
  async function _get(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function _post(url, data) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  return {
    getNotebook()              { return _get('/api/notebook'); },
    addCell(afterIndex, type)  { return _post('/api/cell/add', { after_index: afterIndex, type: type }); },
    deleteCell(index)          { return _post('/api/cell/delete', { index: index }); },
    moveCell(index, direction) { return _post('/api/cell/move', { index: index, direction: direction }); },
    updateCell(index, source)  { return _post('/api/cell/update', { index: index, source: source }); },
    executeCell(index, source) { return _post('/api/cell/execute', { index: index, source: source }); },
    executeAll()               { return _post('/api/execute-all', {}); },
    save(includeSession)       { return _post('/api/save', { include_session: includeSession }); },
    async load(file) {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/load', { method: 'POST', body: formData });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    getVariables()             { return _get('/api/variables'); },
    clearVariables()           { return _post('/api/clear-variables', {}); },
    getNotebookInfo()          { return _get('/api/notebook-info'); }
  };
})();
