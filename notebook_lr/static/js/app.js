window.NB = window.NB || {};

NB.app = {
  async init() {
    console.log('notebook-lr initializing...');

    // 1. Initialize toolbar (button event listeners)
    NB.toolbar.init();

    // 1b. Initialize inline comments
    if (NB.comments) NB.comments.init();

    // 1c. Initialize debug panel
    if (NB.debugPanel) {
      NB.debugPanel.init();
    }

    // 1d. Debug panel button handler
    var debugBtn = document.getElementById('debug-btn');
    if (debugBtn && NB.debugPanel) {
      debugBtn.addEventListener('click', function() {
        NB.debugPanel.toggle();
      });
    }

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

      // 6. Start file sync polling
      if (NB.fileSync) {
        NB.fileSync.start();
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
