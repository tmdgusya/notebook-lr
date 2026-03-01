window.NB = window.NB || {};

NB.toolbar = {
  init() {
    document.getElementById('run-all-btn').addEventListener('click', function() {
      NB.execution.executeAll();
    });

    document.getElementById('save-btn').addEventListener('click', function() {
      NB.fileops.save(false);
    });

    document.getElementById('save-session-btn').addEventListener('click', function() {
      NB.fileops.save(true);
    });

    document.getElementById('load-btn').addEventListener('click', function() {
      document.getElementById('load-file-input').click();
    });

    document.getElementById('load-file-input').addEventListener('change', function(e) {
      if (e.target.files[0]) {
        NB.fileops.load(e.target.files[0]);
        e.target.value = '';  // Reset so same file can be loaded again
      }
    });

    document.getElementById('vars-btn').addEventListener('click', function() {
      NB.toolbar.toggleVariables();
    });

    document.getElementById('clear-vars-btn').addEventListener('click', async function() {
      await NB.api.clearVariables();
      NB.toolbar.showSuccess('Variables cleared');
      document.getElementById('variables-panel').classList.add('hidden');
    });

    document.getElementById('close-vars-btn').addEventListener('click', function() {
      document.getElementById('variables-panel').classList.add('hidden');
    });

    // Add cell buttons
    var addCodeBtn = document.getElementById('add-code-btn');
    var addMdBtn = document.getElementById('add-md-btn');
    var helpBtn = document.getElementById('help-btn');
    
    if (addCodeBtn) {
      addCodeBtn.addEventListener('click', function() {
        var selectedIdx = NB.cells.getSelectedIndex();
        NB.cells.addCell(selectedIdx >= 0 ? selectedIdx : -1, 'code');
      });
    }
    
    if (addMdBtn) {
      addMdBtn.addEventListener('click', function() {
        var selectedIdx = NB.cells.getSelectedIndex();
        NB.cells.addCell(selectedIdx >= 0 ? selectedIdx : -1, 'markdown');
      });
    }
    
    if (helpBtn) {
      helpBtn.addEventListener('click', function() {
        NB.toolbar.showShortcutsModal();
      });
    }
    
    // Close shortcuts modal
    var closeShortcutsBtn = document.getElementById('close-shortcuts-btn');
    var shortcutsModal = document.getElementById('shortcuts-modal');
    if (closeShortcutsBtn && shortcutsModal) {
      closeShortcutsBtn.addEventListener('click', function() {
        shortcutsModal.classList.add('hidden');
      });
      shortcutsModal.querySelector('.modal-overlay').addEventListener('click', function() {
        shortcutsModal.classList.add('hidden');
      });
    }

    NB.toolbar.initKeyboardShortcuts();

    // Monitor cell changes for autosave indicator (idempotent)
    if (!NB.api._updateCellPatched) {
      const origUpdateCell = NB.api.updateCell;
      NB.api.updateCell = async function() {
        NB.fileops.markDirty();
        return origUpdateCell.apply(NB.api, arguments);
      };
      NB.api._updateCellPatched = true;
    }
  },

  async updateInfo() {
    try {
      const info = await NB.api.getNotebookInfo();
      var el = document.getElementById('notebook-info');
      if (el && info) {
        el.textContent = info.name + ' | ' + info.cell_count + ' cells (' +
          info.code_count + ' code, ' + info.md_count + ' markdown) | ' +
          info.executed_count + ' executed';
      }
    } catch (e) {
      // ignore info update errors
    }
  },

  async toggleVariables() {
    var panel = document.getElementById('variables-panel');
    if (panel.classList.contains('hidden')) {
      var data = await NB.api.getVariables();
      var content = document.getElementById('variables-content');
      if (data.variables && data.variables.length > 0) {
        var html = '<table class="vars-table"><thead><tr><th>Name</th><th>Type</th><th>Value</th></tr></thead><tbody>';
        for (var i = 0; i < data.variables.length; i++) {
          var v = data.variables[i];
          html += '<tr><td>' + escapeHtml(v.name) + '</td><td>' + escapeHtml(v.type) + '</td><td>' + escapeHtml(v.value) + '</td></tr>';
        }
        html += '</tbody></table>';
        content.innerHTML = html;
      } else {
        content.textContent = 'No variables defined';
      }
      panel.classList.remove('hidden');
    } else {
      panel.classList.add('hidden');
    }
  },

  showNotification(message, type, duration) {
    duration = duration || 3000;
    type = type || 'info'; // 'info', 'success', 'error', 'warning'
    
    var notif = document.getElementById('notification');
    if (!notif) {
      notif = document.createElement('div');
      notif.id = 'notification';
      document.body.appendChild(notif);
    }
    
    // Clear previous classes
    notif.className = '';
    notif.classList.add(type);
    
    // Add icon based on type
    var icon = '';
    if (type === 'success') icon = '&#10003; ';
    else if (type === 'error') icon = '&#10007; ';
    else if (type === 'warning') icon = '&#9888; ';
    else if (type === 'info') icon = '&#9432; ';
    
    notif.innerHTML = icon + message;
    notif.classList.remove('hidden');
    
    // Clear any existing timeout
    if (notif._timeout) {
      clearTimeout(notif._timeout);
    }
    
    notif._timeout = setTimeout(function() { 
      notif.classList.add('hidden'); 
    }, duration);
  },
  
  showError(message, duration) {
    this.showNotification(message, 'error', duration || 5000);
  },
  
  showSuccess(message, duration) {
    this.showNotification(message, 'success', duration || 3000);
  },

  showShortcutsModal() {
    var modal = document.getElementById('shortcuts-modal');
    if (modal) {
      modal.classList.remove('hidden');
    }
  },

  initKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
      var cmFocused = e.target.closest('.CodeMirror');
      
      // Global shortcuts (work everywhere)
      // Ctrl+S / Cmd+S: Save
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 's') {
        e.preventDefault();
        NB.fileops._updateIndicator('saving');
        NB.fileops.save(false);
        return;
      }
      // Ctrl+Shift+S: Save with session
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
        e.preventDefault();
        NB.fileops._updateIndicator('saving');
        NB.fileops.save(true);
        return;
      }
      // ?: Show shortcuts modal
      if (!cmFocused && e.key === '?' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        NB.toolbar.showShortcutsModal();
        return;
      }
      // Escape: Close modal
      if (e.key === 'Escape') {
        var modal = document.getElementById('shortcuts-modal');
        if (modal && !modal.classList.contains('hidden')) {
          modal.classList.add('hidden');
          return;
        }
      }
      // Ctrl+Shift+D: Toggle debug panel
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        if (NB.debugPanel) {
          NB.debugPanel.toggle();
        }
        return;
      }
      
      // Shortcuts that don't work while editing
      if (cmFocused) return;
      
      var selectedIdx = NB.cells.getSelectedIndex();
      
      // A: Add code cell after selected
      if (e.key === 'a' || e.key === 'A') {
        e.preventDefault();
        NB.cells.addCell(selectedIdx >= 0 ? selectedIdx : -1, 'code');
        return;
      }
      // M: Add markdown cell after selected  
      if (e.key === 'm' || e.key === 'M') {
        e.preventDefault();
        NB.cells.addCell(selectedIdx >= 0 ? selectedIdx : -1, 'markdown');
        return;
      }
      // D: Delete selected cell
      if ((e.key === 'd' || e.key === 'D') && selectedIdx >= 0) {
        e.preventDefault();
        if (confirm('Delete this cell?')) {
          NB.cells.deleteCell(selectedIdx);
        }
        return;
      }
      // Arrow navigation
      if (e.key === 'ArrowDown' || e.key === 'j' || e.key === 'J') {
        e.preventDefault();
        var nextIdx = selectedIdx + 1;
        var totalCells = document.querySelectorAll('#cells-container .cell').length;
        if (nextIdx < totalCells) {
          NB.cells.selectCell(nextIdx);
        }
        return;
      }
      if (e.key === 'ArrowUp' || e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        var prevIdx = selectedIdx - 1;
        if (prevIdx >= 0) {
          NB.cells.selectCell(prevIdx);
        }
        return;
      }
      // Enter: Edit selected cell
      if (e.key === 'Enter' && selectedIdx >= 0) {
        e.preventDefault();
        var cell = document.querySelector('#cells-container .cell[data-index="' + selectedIdx + '"]');
        if (cell) {
          cell.classList.add('editing');
          var cm = cell.querySelector('.CodeMirror');
          if (cm && cm.CodeMirror) {
            cm.CodeMirror.focus();
          }
        }
        return;
      }
    });
  }
};

function escapeHtml(str) {
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
