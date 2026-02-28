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

  _renderRichData(div, data) {
    if (data['text/html']) {
      div.innerHTML = data['text/html'];
    } else if (data['text/markdown']) {
      div.classList.add('markdown-rendered');
      div.innerHTML = (typeof marked !== 'undefined' && marked.parse)
        ? marked.parse(data['text/markdown'])
        : data['text/markdown'];
    } else if (data['image/png']) {
      var img = document.createElement('img');
      img.src = 'data:image/png;base64,' + data['image/png'];
      img.className = 'output-image';
      div.appendChild(img);
    } else if (data['image/svg+xml']) {
      var svgDiv = document.createElement('div');
      svgDiv.className = 'output-image output-svg';
      svgDiv.innerHTML = data['image/svg+xml'];
      div.appendChild(svgDiv);
    } else if (data['text/latex']) {
      var latexDiv = document.createElement('div');
      latexDiv.className = 'output-latex';
      var latexStr = data['text/latex'];
      latexDiv.textContent = latexStr;
      div.appendChild(latexDiv);
      if (typeof katex !== 'undefined') {
        // Strip surrounding $ or $$ delimiters
        var stripped = latexStr.trim();
        if (stripped.startsWith('$$') && stripped.endsWith('$$')) {
          stripped = stripped.slice(2, -2).trim();
        } else if (stripped.startsWith('$') && stripped.endsWith('$')) {
          stripped = stripped.slice(1, -1).trim();
        }
        try {
          katex.render(stripped, latexDiv, {throwOnError: false, displayMode: true});
        } catch(e) {}
      }
    } else if (data['application/json']) {
      var jsonPre = document.createElement('pre');
      jsonPre.className = 'output-json';
      try {
        jsonPre.textContent = JSON.stringify(data['application/json'], null, 2);
      } catch(e) {
        jsonPre.textContent = String(data['application/json']);
      }
      div.appendChild(jsonPre);
    } else {
      div.textContent = data['text/plain'] || '';
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
          NB.execution._renderRichData(div, data);
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
          NB.execution._renderRichData(div, dd);
          break;
        }

        default:
          div.className = 'output-unknown';
          div.textContent = JSON.stringify(output);
      }

      outputElement.appendChild(div);
    }

    // Output folding
    setTimeout(function() {
      if (outputElement.scrollHeight > 400) {
        outputElement.classList.add('output-folded');
        var expandBtn = document.createElement('button');
        expandBtn.className = 'output-expand-btn';
        expandBtn.textContent = '더 보기 ▼';
        expandBtn.addEventListener('click', function() {
          if (outputElement.classList.contains('output-folded')) {
            outputElement.classList.remove('output-folded');
            outputElement.classList.add('output-expanded');
            expandBtn.textContent = '접기 ▲';
          } else {
            outputElement.classList.add('output-folded');
            outputElement.classList.remove('output-expanded');
            expandBtn.textContent = '더 보기 ▼';
          }
        });
        outputElement.parentNode.insertBefore(expandBtn, outputElement.nextSibling);
      }
    }, 0);
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
