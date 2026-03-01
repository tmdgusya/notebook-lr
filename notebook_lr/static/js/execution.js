window.NB = window.NB || {};

NB.execution = {
  _executionTimes: {}, // index -> { startTime, endTime }

  async executeCell(index) {
    const source = NB.cells.getEditorContent(index);

    // Track execution start time
    NB.execution._executionTimes[index] = { startTime: Date.now() };

    // Show running state
    NB.execution.showRunning(index);

    try {
      const result = await NB.api.executeCell(index, source);
      
      // Calculate execution time
      const execInfo = NB.execution._executionTimes[index];
      if (execInfo) {
        execInfo.endTime = Date.now();
        execInfo.duration = execInfo.endTime - execInfo.startTime;
      }
      
      NB.cells.updateCellOutput(index, result.outputs, result.execution_count);
      
      // Add execution time metadata to output if successful
      if (result.success && execInfo && execInfo.duration > 100) {
        NB.execution._addExecutionTimeToCell(index, execInfo.duration);
      }
      
      NB.toolbar.updateInfo();
    } catch (err) {
      NB.cells.updateCellOutput(index, [{
        type: 'error',
        ename: 'NetworkError',
        evalue: err.message
      }], null);
      NB.toolbar.showError('Cell execution failed: ' + err.message);
    } finally {
      NB.execution.hideRunning(index);
      delete NB.execution._executionTimes[index];
    }
  },

  _addExecutionTimeToCell(index, durationMs) {
    const cell = document.querySelector('.cell[data-index="' + index + '"]');
    if (!cell) return;
    
    // Format duration
    let durationText;
    if (durationMs < 1000) {
      durationText = durationMs + 'ms';
    } else {
      durationText = (durationMs / 1000).toFixed(2) + 's';
    }
    
    // Find or create execution time element
    let execTimeEl = cell.querySelector('.cell-exec-time');
    if (!execTimeEl) {
      execTimeEl = document.createElement('span');
      execTimeEl.className = 'cell-exec-time';
      const gutter = cell.querySelector('.cell-gutter');
      if (gutter) {
        gutter.appendChild(execTimeEl);
      }
    }
    execTimeEl.textContent = durationText;
    execTimeEl.title = 'Execution time: ' + durationText;
  },

  async executeAll() {
    const startTime = Date.now();
    try {
      const result = await NB.api.executeAll();
      const duration = Date.now() - startTime;
      
      // Refresh all cells to show updated outputs
      const nb = await NB.api.getNotebook();
      NB.cells.renderAll(nb.cells);
      NB.toolbar.updateInfo();
      
      // Show success message with timing
      let durationText;
      if (duration < 1000) {
        durationText = duration + 'ms';
      } else {
        durationText = (duration / 1000).toFixed(1) + 's';
      }
      NB.toolbar.showSuccess('All cells executed in ' + durationText);
    } catch (err) {
      NB.toolbar.showError('Execute all failed: ' + err.message);
    }
  },

  _sanitizeHtml(html) {
    if (typeof DOMPurify !== 'undefined') {
      return DOMPurify.sanitize(html);
    }
    return html;
  },

  _sanitizeSvg(svg) {
    if (typeof DOMPurify !== 'undefined') {
      return DOMPurify.sanitize(svg, {USE_PROFILES: {svg: true, svgFilters: true}});
    }
    // Minimal fallback: parse and strip scripts/event handlers
    var parser = new DOMParser();
    var doc = parser.parseFromString(svg, 'image/svg+xml');
    var dangerous = doc.querySelectorAll('script, foreignObject');
    dangerous.forEach(function(el) { el.remove(); });
    // Strip event handler attributes
    var allEls = doc.querySelectorAll('*');
    allEls.forEach(function(el) {
      var attrs = Array.from(el.attributes);
      attrs.forEach(function(attr) {
        if (attr.name.startsWith('on')) el.removeAttribute(attr.name);
      });
    });
    return doc.documentElement ? doc.documentElement.outerHTML : svg;
  },

  _renderRichData(div, data) {
    if (data['text/html']) {
      div.innerHTML = NB.execution._sanitizeHtml(data['text/html']);
    } else if (data['text/markdown']) {
      div.classList.add('markdown-rendered');
      var rendered = (typeof marked !== 'undefined' && marked.parse)
        ? marked.parse(data['text/markdown'])
        : data['text/markdown'];
      div.innerHTML = NB.execution._sanitizeHtml(rendered);
      // Render mermaid diagrams in markdown output
      if (typeof mermaid !== 'undefined') {
        var mermaidBlocks = div.querySelectorAll('pre code.language-mermaid');
        mermaidBlocks.forEach(function(codeEl) {
          var pre = codeEl.parentElement;
          var mermaidDiv = document.createElement('div');
          mermaidDiv.className = 'mermaid';
          mermaidDiv.textContent = codeEl.textContent;
          pre.parentNode.replaceChild(mermaidDiv, pre);
        });
        try {
          mermaid.run({ nodes: div.querySelectorAll('.mermaid') });
        } catch(e) { console.warn('Mermaid render failed:', e); }
      }
    } else if (data['image/png']) {
      var img = document.createElement('img');
      img.src = 'data:image/png;base64,' + data['image/png'];
      img.className = 'output-image';
      div.appendChild(img);
    } else if (data['image/svg+xml']) {
      var svgDiv = document.createElement('div');
      svgDiv.className = 'output-image output-svg';
      svgDiv.innerHTML = NB.execution._sanitizeSvg(data['image/svg+xml']);
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
        } catch(e) {
          console.warn('KaTeX render failed:', e);
        }
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
      // Clean up any existing expand button from previous render
      var existingBtn = outputElement.parentNode && outputElement.parentNode.querySelector('.output-expand-btn');
      if (existingBtn) existingBtn.remove();
      outputElement.classList.remove('output-folded', 'output-expanded');

      if (outputElement.scrollHeight > 400) {
        outputElement.classList.add('output-folded');
        var expandBtn = document.createElement('button');
        expandBtn.className = 'output-expand-btn';
        expandBtn.textContent = 'Show more \u25BC';
        expandBtn.addEventListener('click', function() {
          if (outputElement.classList.contains('output-folded')) {
            outputElement.classList.remove('output-folded');
            outputElement.classList.add('output-expanded');
            expandBtn.textContent = 'Show less \u25B2';
          } else {
            outputElement.classList.add('output-folded');
            outputElement.classList.remove('output-expanded');
            expandBtn.textContent = 'Show more \u25BC';
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
