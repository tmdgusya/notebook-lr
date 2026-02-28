window.NB = window.NB || {};

NB.fileops = {
  async save(includeSession) {
    NB.fileops._updateIndicator('saving');
    try {
      var result = await NB.api.save(includeSession);
      NB.fileops._isDirty = false;
      NB.fileops._updateIndicator('saved');
      NB.toolbar.showNotification(result.status || 'Saved');
    } catch (err) {
      NB.fileops._updateIndicator('modified');
      NB.toolbar.showNotification('Save failed: ' + err.message);
    }
  },

  async load(file) {
    try {
      var data = await NB.api.load(file);
      NB.cells.renderAll(data.cells);
      NB.toolbar.updateInfo();
      NB.toolbar.showNotification('Loaded ' + file.name);
    } catch (err) {
      NB.toolbar.showNotification('Load failed: ' + err.message);
    }
  },

  _autosaveTimer: null,
  _isDirty: false,

  markDirty() {
    NB.fileops._isDirty = true;
    NB.fileops._updateIndicator('modified');
    NB.fileops._startAutosave();
  },

  _updateIndicator(state) {
    const el = document.getElementById('save-indicator');
    if (!el) return;
    el.className = 'save-indicator save-' + state;
    if (state === 'saved') { el.innerHTML = '&#10003; Saved'; el.title = 'All changes saved'; }
    else if (state === 'modified') { el.innerHTML = '&#9679; Modified'; el.title = 'Unsaved changes'; }
    else if (state === 'saving') { el.innerHTML = '&#8987; Saving...'; el.title = 'Saving...'; }
  },

  _startAutosave() {
    if (NB.fileops._autosaveTimer) clearTimeout(NB.fileops._autosaveTimer);
    NB.fileops._autosaveTimer = setTimeout(async function() {
      if (NB.fileops._isDirty) {
        NB.fileops._updateIndicator('saving');
        try {
          await NB.api.save(false);
          NB.fileops._isDirty = false;
          NB.fileops._updateIndicator('saved');
        } catch(e) {
          NB.fileops._updateIndicator('modified');
        }
      }
    }, 30000); // 30초 후 자동저장
  },
};
