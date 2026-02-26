window.NB = window.NB || {};

NB.fileops = {
  async save(includeSession) {
    try {
      var result = await NB.api.save(includeSession);
      NB.toolbar.showNotification(result.status || 'Saved');
    } catch (err) {
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
  }
};
