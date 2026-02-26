window.NB = window.NB || {};

NB.execution = {
  async executeCell(index) {
    const source = NB.cells.getEditorContent(index);

    // Show running state
    NB.execution.showRunning(index);

    try {
      const result = await NB.api.executeCell(index, source);
      NB.cells.updateCellOutput(index, result.outputs, result.execution_count);
      NB.toolbar.updateInfo();
    } catch (err) {
      NB.cells.updateCellOutput(index, [{
        type: 'error',
        ename: 'NetworkError',
        evalue: err.message
      }], null);
    } finally {
      NB.execution.hideRunning(index);
    }
  },

  async executeAll() {
    try {
      const result = await NB.api.executeAll();
      // Refresh all cells to show updated outputs
      const nb = await NB.api.getNotebook();
      NB.cells.renderAll(nb.cells);
      NB.toolbar.updateInfo();
    } catch (err) {
      NB.toolbar.showNotification('Execute all failed: ' + err.message);
    }
  },

  displayOutputs(outputElement, outputs) {
    outputElement.innerHTML = '';
    outputElement.classList.remove('has-error');

    if (!outputs || outputs.length === 0) {
      outputElement.classList.add('empty');
      return;
    }
    outputElement.classList.remove('empty');

    for (const output of outputs) {
      const div = document.createElement('div');

      switch (output.type) {
        case 'stream':
          div.className = output.name === 'stderr' ? 'output-stream output-stderr' : 'output-stream';
          div.textContent = output.text || '';
          break;

        case 'execute_result': {
          div.className = 'output-result';
          const data = output.data || {};
          if (data['text/html']) {
            div.innerHTML = data['text/html'];
          } else if (data['text/markdown']) {
            div.textContent = data['text/markdown'];
          } else {
            div.textContent = data['text/plain'] || '';
          }
          break;
        }

        case 'error':
          div.className = 'output-error';
          div.textContent = (output.ename || 'Error') + ': ' + (output.evalue || '');
          outputElement.classList.add('has-error');
          break;

        case 'display_data': {
          div.className = 'output-display';
          const dd = output.data || {};
          if (dd['text/html']) {
            div.innerHTML = dd['text/html'];
          } else {
            div.textContent = dd['text/plain'] || '';
          }
          break;
        }

        default:
          div.className = 'output-unknown';
          div.textContent = JSON.stringify(output);
      }

      outputElement.appendChild(div);
    }
  },

  showRunning(index) {
    const cell = document.querySelector('.cell[data-index="' + index + '"]');
    if (cell) {
      cell.classList.add('running');
      const count = cell.querySelector('.cell-exec-count');
      if (count) count.textContent = '[*]';
    }
  },

  hideRunning(index) {
    const cell = document.querySelector('.cell[data-index="' + index + '"]');
    if (cell) cell.classList.remove('running');
  }
};
