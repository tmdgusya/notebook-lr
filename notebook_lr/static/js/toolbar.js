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
      NB.toolbar.showNotification('Variables cleared');
      document.getElementById('variables-panel').classList.add('hidden');
    });

    document.getElementById('close-vars-btn').addEventListener('click', function() {
      document.getElementById('variables-panel').classList.add('hidden');
    });

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

  showNotification(message, duration) {
    duration = duration || 3000;
    var notif = document.getElementById('notification');
    if (!notif) {
      notif = document.createElement('div');
      notif.id = 'notification';
      document.body.appendChild(notif);
    }
    notif.textContent = message;
    notif.classList.add('show');
    setTimeout(function() { notif.classList.remove('show'); }, duration);
  },

  initKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
      // Don't capture when typing in CodeMirror
      if (e.target.closest('.CodeMirror')) return;

      // Ctrl+S / Cmd+S: Save
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 's') {
        e.preventDefault();
        NB.fileops._updateIndicator('saving');
        NB.fileops.save(false);
      }
      // Ctrl+Shift+S: Save with session
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
        e.preventDefault();
        NB.fileops._updateIndicator('saving');
        NB.fileops.save(true);
      }
    });
  }
};

function escapeHtml(str) {
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
