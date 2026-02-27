window.NB = window.NB || {};

NB.app = {
  async init() {
    console.log('notebook-lr initializing...');

    // 1. Initialize toolbar (button event listeners)
    NB.toolbar.init();

    // 1b. Initialize inline comments
    if (NB.comments) NB.comments.init();

    // 2. Load notebook data from server
    try {
      var data = await NB.api.getNotebook();

      // 3. Render all cells
      NB.cells.renderAll(data.cells);

      // 4. Update notebook info
      NB.toolbar.updateInfo();

      // 5. Select first cell if exists
      if (data.cells.length > 0) {
        NB.cells.selectCell(0);
      }

      console.log('notebook-lr ready (' + data.cells.length + ' cells)');
    } catch (err) {
      console.error('Failed to initialize:', err);
      document.getElementById('cells-container').innerHTML =
        '<div class="error-banner">Failed to load notebook: ' + err.message + '</div>';
    }
  }
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  NB.app.init();
});
