window.NB = window.NB || {};

NB.editor = (function() {
  // Simple debounce helper
  function debounce(fn, ms) {
    let timer;
    return function(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  return {
    create(element, options) {
      // options: { mode: 'python'|'markdown', value: str, onChange: fn, onRun: fn }
      const cm = CodeMirror(element, {
        value: options.value || '',
        mode: options.mode || 'python',
        theme: 'default',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        autoCloseBrackets: true,
        matchBrackets: true,
        lineWrapping: true,
        viewportMargin: Infinity,  // Auto-height: editor grows with content
        extraKeys: {
          'Shift-Enter': function(cm) {
            if (options.onRun) options.onRun();
          },
          'Ctrl-Enter': function(cm) {
            if (options.onRun) options.onRun();
          },
          'Tab': function(cm) {
            if (cm.somethingSelected()) {
              cm.indentSelection('add');
            } else {
              cm.replaceSelection('    ', 'end');
            }
          }
        }
      });

      // Register change handler with debouncing
      if (options.onChange) {
        const debouncedChange = debounce(function() {
          options.onChange(cm.getValue());
        }, 500);
        cm.on('change', debouncedChange);
      }

      return cm;
    },

    getContent(cmInstance) {
      return cmInstance ? cmInstance.getValue() : '';
    },

    setContent(cmInstance, value) {
      if (cmInstance) cmInstance.setValue(value);
    },

    focus(cmInstance) {
      if (cmInstance) {
        cmInstance.focus();
        cmInstance.setCursor(cmInstance.lineCount(), 0);
      }
    },

    refresh(cmInstance) {
      if (cmInstance) cmInstance.refresh();
    },

    destroy(cmInstance) {
      // CodeMirror 5 doesn't have a destroy method
      // Just remove DOM - the parent will handle this
    },

    refreshAll() {
      // Iterate all editors and call .refresh()
      // This fixes sizing issues after show/hide
      document.querySelectorAll('.CodeMirror').forEach(function(el) {
        if (el.CodeMirror) el.CodeMirror.refresh();
      });
    }
  };
})();
