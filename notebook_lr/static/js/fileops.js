window.NB = window.NB || {};

NB.fileops = {
  async save(includeSession) {
    NB.fileops._updateIndicator('saving');
    try {
      var result = await NB.api.save(includeSession);
      NB.fileops._isDirty = false;
      NB.fileops._updateIndicator('saved');
      if (NB.fileSync) NB.fileSync.notifySaved();
      NB.toolbar.showSuccess(result.status || 'Saved successfully');
    } catch (err) {
      NB.fileops._updateIndicator('modified');
      NB.toolbar.showError('Save failed: ' + (err.message || 'Unknown error'));
      console.error('Save error:', err);
    }
  },

  async load(file) {
    try {
      var data = await NB.api.load(file);
      NB.cells.renderAll(data.cells);
      NB.toolbar.updateInfo();
      NB.toolbar.showSuccess('Loaded ' + file.name);
    } catch (err) {
      NB.toolbar.showError('Load failed: ' + (err.message || 'Unknown error'));
      console.error('Load error:', err);
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
    
    const iconEl = el.querySelector('.save-icon');
    const textEl = el.querySelector('.save-text');
    
    if (state === 'saved') { 
      if (iconEl) iconEl.innerHTML = '&#10003;'; 
      if (textEl) textEl.textContent = 'Saved'; 
      el.title = 'All changes saved'; 
    }
    else if (state === 'modified') { 
      if (iconEl) iconEl.innerHTML = '&#9679;'; 
      if (textEl) textEl.textContent = 'Modified'; 
      el.title = 'Unsaved changes - will auto-save in 30s'; 
    }
    else if (state === 'saving') { 
      if (iconEl) iconEl.innerHTML = '&#9203;'; 
      if (textEl) textEl.textContent = 'Saving...'; 
      el.title = 'Saving...'; 
    }
  },

  _startAutosave() {
    // Don't reset timer if one is already pending
    if (NB.fileops._autosaveTimer) return;
    NB.fileops._autosaveTimer = setTimeout(async function() {
      NB.fileops._autosaveTimer = null;
      if (NB.fileops._isDirty) {
        NB.fileops._updateIndicator('saving');
        try {
          await NB.api.save(false);
          NB.fileops._isDirty = false;
          NB.fileops._updateIndicator('saved');
          if (NB.fileSync) NB.fileSync.notifySaved();
        } catch(e) {
          NB.fileops._updateIndicator('modified');
        }
      }
    }, 30000);
  },
};
