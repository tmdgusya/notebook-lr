window.NB = window.NB || {};

NB.cells = (function () {
  let selectedIndex = -1;
  let cellEditors = {}; // index -> CodeMirror instance
  let debounceTimers = {}; // index -> timer id

  function clearEditors() {
    if (NB.comments) NB.comments.clearAll();
    cellEditors = {};
  }

  function renderKaTeX(element) {
    if (typeof renderMathInElement === 'function') {
      try {
        renderMathInElement(element, {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\(', right: '\\)', display: false},
            {left: '\\[', right: '\\]', display: true}
          ],
          throwOnError: false
        });
      } catch(e) { /* KaTeX not loaded */ }
    }
  }

  function renderMermaid(element) {
    if (typeof mermaid === 'undefined') return;
    var mermaidBlocks = element.querySelectorAll('pre code.language-mermaid');
    if (mermaidBlocks.length === 0) return;
    mermaidBlocks.forEach(function(codeEl) {
      var pre = codeEl.parentElement;
      var mermaidDiv = document.createElement('div');
      mermaidDiv.className = 'mermaid';
      mermaidDiv.textContent = codeEl.textContent;
      pre.parentNode.replaceChild(mermaidDiv, pre);
    });
    try {
      mermaid.run({ nodes: element.querySelectorAll('.mermaid') });
    } catch(e) { console.warn('Mermaid render failed:', e); }
  }

  function renderDivider(afterIndex) {
    const div = document.createElement('div');
    div.className = 'add-cell-divider';
    div.dataset.after = afterIndex;

    const line = document.createElement('div');
    line.className = 'divider-line';

    const codeBtn = document.createElement('button');
    codeBtn.className = 'add-code-btn';
    codeBtn.textContent = '+ Code';
    codeBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      addCell(afterIndex, 'code');
    });

    const mdBtn = document.createElement('button');
    mdBtn.className = 'add-md-btn';
    mdBtn.textContent = '+ Markdown';
    mdBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      addCell(afterIndex, 'markdown');
    });

    const btnGroup = document.createElement('div');
    btnGroup.className = 'divider-buttons';
    btnGroup.appendChild(codeBtn);
    btnGroup.appendChild(mdBtn);

    div.appendChild(line);
    div.appendChild(btnGroup);
    return div;
  }

  function renderCell(cell, index) {
    const cellDiv = document.createElement('div');
    cellDiv.className = 'cell';
    cellDiv.dataset.index = index;
    cellDiv.dataset.type = cell.type || 'code';
    cellDiv.dataset.cellId = cell.id || cell.cell_id || '';

    // Gutter
    const gutter = document.createElement('div');
    gutter.className = 'cell-gutter';

    const execCount = document.createElement('span');
    execCount.className = 'cell-exec-count';
    const count = cell.execution_count != null ? cell.execution_count : ' ';
    execCount.textContent = '[' + count + ']';

    const runBtn = document.createElement('button');
    runBtn.className = 'run-cell-btn';
    runBtn.title = 'Run cell';
    runBtn.innerHTML = '&#9654;';
    runBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      NB.execution.executeCell(index);
    });

    const collapseBtn = document.createElement('button');
    collapseBtn.className = 'cell-collapse-btn';
    collapseBtn.title = 'Collapse cell';
    collapseBtn.innerHTML = '&#9660;'; // ▼
    collapseBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      const isCollapsed = cellDiv.classList.toggle('cell-collapsed');
      collapseBtn.innerHTML = isCollapsed ? '&#9654;' : '&#9660;'; // ▶ or ▼
      collapseBtn.title = isCollapsed ? 'Expand cell' : 'Collapse cell';
    });

    gutter.appendChild(execCount);
    gutter.appendChild(runBtn);
    gutter.insertBefore(collapseBtn, gutter.firstChild);

    // Content
    const content = document.createElement('div');
    content.className = 'cell-content';

    const editorEl = document.createElement('div');
    editorEl.className = 'cell-editor';

    const previewEl = document.createElement('div');
    previewEl.className = 'cell-md-preview';
    previewEl.style.display = 'none';

    const outputEl = document.createElement('div');
    outputEl.className = 'cell-output';

    content.appendChild(editorEl);
    content.appendChild(previewEl);
    content.appendChild(outputEl);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'cell-actions';

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-cell-btn';
    deleteBtn.title = 'Delete';
    deleteBtn.innerHTML = '&times;';
    deleteBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      deleteCell(index);
    });

    const moveUpBtn = document.createElement('button');
    moveUpBtn.className = 'move-up-btn';
    moveUpBtn.title = 'Move up';
    moveUpBtn.innerHTML = '&uarr;';
    moveUpBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      moveCell(index, 'up');
    });

    const moveDownBtn = document.createElement('button');
    moveDownBtn.className = 'move-down-btn';
    moveDownBtn.title = 'Move down';
    moveDownBtn.innerHTML = '&darr;';
    moveDownBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      moveCell(index, 'down');
    });

    actions.appendChild(deleteBtn);
    actions.appendChild(moveUpBtn);
    actions.appendChild(moveDownBtn);

    cellDiv.appendChild(gutter);
    cellDiv.appendChild(content);
    cellDiv.appendChild(actions);

    // Click to select
    cellDiv.addEventListener('click', function () {
      selectCell(index);
    });

    // Determine mode
    const cellType = cell.type || 'code';
    const mode = cellType === 'markdown' ? 'markdown' : 'python';
    const value = cell.source || '';

    // For markdown cells, add a preview toggle button to gutter
    let previewActive = false;
    if (cellType === 'markdown') {
      const previewBtn = document.createElement('button');
      previewBtn.className = 'preview-toggle-btn';
      previewBtn.title = 'Toggle preview';
      previewBtn.textContent = 'Preview';
      previewBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        previewActive = !previewActive;
        if (previewActive) {
          const src = cm ? cm.getValue() : value;
          previewEl.innerHTML = (typeof marked !== 'undefined')
            ? marked.parse(src)
            : src;
          renderKaTeX(previewEl);
          renderMermaid(previewEl);
          previewEl.style.display = '';
          editorEl.style.display = 'none';
          previewBtn.textContent = 'Edit';
          previewBtn.classList.add('active');
        } else {
          previewEl.style.display = 'none';
          editorEl.style.display = '';
          previewBtn.textContent = 'Preview';
          previewBtn.classList.remove('active');
          if (cm) cm.refresh();
        }
      });
      gutter.appendChild(previewBtn);
    }

    // Mount CodeMirror
    const cm = NB.editor.create(editorEl, {
      mode: mode,
      value: value,
      onChange: function (newValue) {
        // Debounce API update
        if (debounceTimers[index]) {
          clearTimeout(debounceTimers[index]);
        }
        debounceTimers[index] = setTimeout(function () {
          delete debounceTimers[index];
          NB.api.updateCell(index, newValue);
        }, 500);
      },
      onRun: cellType === 'markdown' ? null : function () {
        NB.execution.executeCell(index);
      },
      onExitEdit: cellType === 'markdown' ? function () {
        // Shift-Enter/Ctrl-Enter on markdown cells triggers preview
        previewActive = !previewActive;
        if (previewActive) {
          const src = cm ? cm.getValue() : value;
          previewEl.innerHTML = (typeof marked !== 'undefined')
            ? marked.parse(src)
            : src;
          renderKaTeX(previewEl);
          renderMermaid(previewEl);
          previewEl.style.display = '';
          editorEl.style.display = 'none';
          const previewBtn = cellDiv.querySelector('.preview-toggle-btn');
          if (previewBtn) { previewBtn.textContent = 'Edit'; previewBtn.classList.add('active'); }
        } else {
          previewEl.style.display = 'none';
          editorEl.style.display = '';
          const previewBtn = cellDiv.querySelector('.preview-toggle-btn');
          if (previewBtn) { previewBtn.textContent = 'Preview'; previewBtn.classList.remove('active'); }
          if (cm) cm.refresh();
        }
      } : null
    });

    cellEditors[index] = cm;

    // Attach inline comment support
    if (NB.comments) NB.comments.attachToEditor(cm, cell);

    // Refresh editor after a brief delay to ensure proper rendering
    // This fixes the issue where content is only visible after clicking
    setTimeout(function() {
      cm.refresh();
    }, 0);

    // Markdown cells with content default to preview mode
    if (cellType === 'markdown' && value.trim().length > 0) {
      previewActive = true;
      previewEl.innerHTML = (typeof marked !== 'undefined')
        ? marked.parse(value)
        : value;
      renderKaTeX(previewEl);
      renderMermaid(previewEl);
      previewEl.style.display = '';
      editorEl.style.display = 'none';
      const previewBtn = cellDiv.querySelector('.preview-toggle-btn');
      if (previewBtn) { previewBtn.textContent = 'Edit'; previewBtn.classList.add('active'); }
    }

    // Display existing outputs
    if (cell.outputs && cell.outputs.length > 0) {
      NB.execution.displayOutputs(outputEl, cell.outputs);
    }

    return cellDiv;
  }

  function renderAll(cells) {
    const container = document.getElementById('cells-container');
    if (!container) return;

    clearEditors();
    container.innerHTML = '';

    // Top divider (after=-1)
    container.appendChild(renderDivider(-1));

    cells.forEach(function (cell, index) {
      container.appendChild(renderCell(cell, index));
      container.appendChild(renderDivider(index));
    });

    // Select first cell if any
    if (cells.length > 0) {
      selectCell(0);
    } else {
      selectedIndex = -1;
    }
  }

  function selectCell(index) {
    // Remove selected and editing from all cells
    const allCells = document.querySelectorAll('#cells-container .cell');
    allCells.forEach(function (el) {
      el.classList.remove('selected');
      el.classList.remove('editing');
    });

    // Find and select target cell
    const target = document.querySelector('#cells-container .cell[data-index="' + index + '"]');
    if (target) {
      target.classList.add('selected');
      target.classList.add('editing');
      selectedIndex = index;

      // Focus the editor
      if (cellEditors[index] && typeof cellEditors[index].focus === 'function') {
        cellEditors[index].focus();
      }

      // Update toolbar info if available
      if (NB.toolbar && typeof NB.toolbar.updateInfo === 'function') {
        NB.toolbar.updateInfo(index);
      }
    }
  }

  function getSelectedIndex() {
    return selectedIndex;
  }

  async function addCell(afterIndex, type) {
    try {
      await NB.api.addCell(afterIndex, type);
      const nb = await NB.api.getNotebook();
      renderAll(nb.cells);
      // Select the newly added cell (afterIndex + 1)
      const newIndex = afterIndex + 1;
      if (newIndex >= 0 && newIndex < nb.cells.length) {
        selectCell(newIndex);
      }
    } catch (err) {
      console.error('Failed to add cell:', err);
    }
  }

  async function deleteCell(index) {
    try {
      await NB.api.deleteCell(index);
      const nb = await NB.api.getNotebook();
      renderAll(nb.cells);
      // Select nearest cell
      if (nb.cells.length > 0) {
        const nearestIndex = Math.min(index, nb.cells.length - 1);
        selectCell(nearestIndex);
      }
    } catch (err) {
      console.error('Failed to delete cell:', err);
    }
  }

  async function moveCell(index, direction) {
    try {
      const result = await NB.api.moveCell(index, direction);
      const nb = await NB.api.getNotebook();
      renderAll(nb.cells);
      // Select the moved cell at its new position
      const newIndex = result.new_index != null ? result.new_index : index;
      selectCell(newIndex);
    } catch (err) {
      console.error('Failed to move cell:', err);
    }
  }

  function updateCellOutput(index, outputs, executionCount) {
    const cellEl = document.querySelector('#cells-container .cell[data-index="' + index + '"]');
    if (!cellEl) return;

    // Update output area
    const outputEl = cellEl.querySelector('.cell-output');
    if (outputEl) {
      outputEl.innerHTML = '';
      if (outputs && outputs.length > 0) {
        NB.execution.displayOutputs(outputEl, outputs);
      }
    }

    // Update execution count
    const execCountEl = cellEl.querySelector('.cell-exec-count');
    if (execCountEl) {
      const count = executionCount != null ? executionCount : ' ';
      execCountEl.textContent = '[' + count + ']';
    }
  }

  function getEditorContent(index) {
    const cm = cellEditors[index];
    if (!cm) return null;
    if (typeof cm.getValue === 'function') {
      return cm.getValue();
    }
    return null;
  }

  return {
    renderAll: renderAll,
    renderCell: renderCell,
    renderDivider: renderDivider,
    selectCell: selectCell,
    getSelectedIndex: getSelectedIndex,
    addCell: addCell,
    deleteCell: deleteCell,
    moveCell: moveCell,
    updateCellOutput: updateCellOutput,
    getEditorContent: getEditorContent,
    clearEditors: clearEditors
  };
})();
