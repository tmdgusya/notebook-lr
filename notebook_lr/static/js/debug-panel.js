/**
 * Debug Panel - UI for visualizing agent activities
 */
window.NB = window.NB || {};

NB.debugPanel = (function() {
  // DOM elements
  let panel = null;
  let content = null;
  let closeBtn = null;
  let clearBtn = null;
  let pauseBtn = null;
  let filterType = null;
  let filterStatus = null;
  let isVisible = false;
  let isPaused = false;
  let selectedEventId = null;
  
  // Collapsed state
  let collapsedNodes = new Set();
  
  /**
   * Initialize the debug panel
   */
  function init() {
    panel = document.getElementById('debug-panel');
    content = document.getElementById('debug-content');
    closeBtn = document.getElementById('close-debug-btn');
    clearBtn = document.getElementById('debug-clear-btn');
    pauseBtn = document.getElementById('debug-pause-btn');
    filterType = document.getElementById('debug-filter-type');
    filterStatus = document.getElementById('debug-filter-status');
    
    if (!panel) {
      console.warn('Debug panel not found in DOM');
      return;
    }
    
    // Bind events
    closeBtn.addEventListener('click', hide);
    clearBtn.addEventListener('click', onClear);
    pauseBtn.addEventListener('click', onPauseToggle);
    filterType.addEventListener('change', render);
    filterStatus.addEventListener('change', render);
    
    // Subscribe to logger events
    if (NB.agentLogger) {
      NB.agentLogger.subscribe(onLoggerEvent);
    }
    
    // Initial render
    render();
  }
  
  /**
   * Show the panel
   */
  function show() {
    if (!panel) return;
    panel.classList.remove('hidden');
    panel.classList.add('visible');
    isVisible = true;
    render();
  }
  
  /**
   * Hide the panel
   */
  function hide() {
    if (!panel) return;
    panel.classList.remove('visible');
    panel.classList.add('hidden');
    isVisible = false;
  }
  
  /**
   * Toggle visibility
   */
  function toggle() {
    if (isVisible) hide();
    else show();
  }
  
  /**
   * Check if panel is visible
   */
  function visible() {
    return isVisible;
  }
  
  /**
   * Handle logger events
   */
  function onLoggerEvent(action, event) {
    if (isPaused) return;
    
    updateStats();
    
    if (isVisible) {
      render();
    }
    
    // Update toolbar button if there are errors
    if (action === 'error' || action === 'timeout') {
      updateToolbarErrorIndicator();
    }
  }
  
  /**
   * Update statistics display
   */
  function updateStats() {
    if (!NB.agentLogger) return;
    
    const stats = NB.agentLogger.getStats();
    
    const totalEl = document.getElementById('debug-stat-total');
    const errorsEl = document.getElementById('debug-stat-errors');
    const timeoutsEl = document.getElementById('debug-stat-timeouts');
    
    if (totalEl) totalEl.textContent = stats.total;
    if (errorsEl) errorsEl.textContent = stats.errors;
    if (timeoutsEl) timeoutsEl.textContent = stats.timeouts;
  }
  
  /**
   * Update toolbar button error indicator
   */
  function updateToolbarErrorIndicator() {
    const debugBtn = document.getElementById('debug-btn');
    if (debugBtn) {
      debugBtn.classList.add('has-errors');
    }
  }
  
  /**
   * Clear all events
   */
  function onClear() {
    if (NB.agentLogger) {
      NB.agentLogger.clear();
    }
    collapsedNodes.clear();
    selectedEventId = null;
    render();
    
    // Clear error indicator
    const debugBtn = document.getElementById('debug-btn');
    if (debugBtn) {
      debugBtn.classList.remove('has-errors');
    }
  }
  
  /**
   * Toggle pause
   */
  function onPauseToggle() {
    isPaused = !isPaused;
    pauseBtn.textContent = isPaused ? 'Resume' : 'Pause';
    pauseBtn.style.background = isPaused ? '#89d185' : '';
    pauseBtn.style.color = isPaused ? '#1e1e1e' : '';
  }
  
  /**
   * Get filter values
   */
  function getFilter() {
    return {
      type: filterType ? filterType.value : '',
      status: filterStatus ? filterStatus.value : '',
    };
  }
  
  /**
   * Render the tree
   */
  function render() {
    if (!content || !NB.agentLogger) return;
    
    const filter = getFilter();
    const rootEvents = NB.agentLogger.getRootEvents();
    
    // Apply filters
    let eventsToShow = rootEvents;
    if (filter.type || filter.status) {
      eventsToShow = rootEvents.filter(e => matchesFilter(e, filter));
    }
    
    // Build tree HTML
    const treeEl = content.querySelector('.debug-tree');
    if (!treeEl) return;
    
    // Remove existing detail view if any
    const existingDetail = content.querySelector('.debug-detail');
    if (existingDetail) {
      existingDetail.remove();
    }
    
    if (eventsToShow.length === 0) {
      treeEl.innerHTML = '<div class="debug-empty">No events</div>';
      return;
    }
    
    treeEl.innerHTML = '';
    eventsToShow.slice().reverse().forEach((event, index) => {
      const isLast = index === eventsToShow.length - 1;
      treeEl.appendChild(renderNode(event, "", isLast, 0));
    });
    
    // Show detail for selected event
    if (selectedEventId) {
      const selectedEvent = NB.agentLogger.findEvent(selectedEventId);
      if (selectedEvent) {
        showDetail(selectedEvent);
      }
    }
  }
  
  /**
   * Check if event matches filter
   */
  function matchesFilter(event, filter) {
    if (filter.type && event.type !== filter.type) return false;
    if (filter.status && event.status !== filter.status) return false;
    return true;
  }
  
  /**
   * Render a single node with tree connectors
   * @param {Object} event - The event to render
   * @param {string} prefix - Prefix string for tree lines (│   or    )
   * @param {boolean} isLast - Whether this node is the last child
   * @param {number} depth - Depth level for indentation calculation
   */
  function renderNode(event, prefix = "", isLast = true, depth = 0) {
    const node = document.createElement('div');
    node.className = 'debug-node';
    if (!collapsedNodes.has(event.id)) {
      node.classList.add('expanded');
    } else {
      node.classList.add('collapsed');
    }
    
    // Header
    const header = document.createElement('div');
    header.className = 'debug-node-header';
    if (selectedEventId === event.id) {
      header.classList.add('selected');
    }
    header.style.paddingLeft = '12px';
    
    // Tree connector line (├── or └──)
    const connector = document.createElement('span');
    connector.className = 'debug-tree-connector';
    if (depth === 0) {
      connector.textContent = ''; // Root node has no connector
    } else {
      connector.textContent = isLast ? '└── ' : '├── ';
    }
    
    // Toggle button for expanding/collapsing
    const children = NB.agentLogger.getChildren(event.id);
    const toggle = document.createElement('span');
    toggle.className = 'debug-toggle' + (children.length === 0 ? ' leaf' : '');
    toggle.textContent = children.length > 0 ? (collapsedNodes.has(event.id) ? '▶ ' : '▼ ') : '';
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleNode(event.id);
    });
    
    // Status indicator
    const status = document.createElement('span');
    status.className = 'debug-status ' + event.status;
    
    // Info
    const info = document.createElement('div');
    info.className = 'debug-info';
    
    const type = document.createElement('div');
    type.className = 'debug-type';
    type.textContent = formatType(event.type);
    
    const summary = document.createElement('div');
    summary.className = 'debug-summary';
    summary.textContent = getSummary(event);
    
    const meta = document.createElement('div');
    meta.className = 'debug-meta';
    
    const time = document.createElement('span');
    time.textContent = formatTime(event.timestamp);
    
    meta.appendChild(time);
    
    if (event.duration !== null) {
      const duration = document.createElement('span');
      duration.className = 'debug-duration';
      duration.textContent = formatDuration(event.duration);
      meta.appendChild(duration);
    }
    
    info.appendChild(type);
    info.appendChild(summary);
    info.appendChild(meta);
    
    // Build tree prefix section
    const treePrefix = document.createElement('span');
    treePrefix.className = 'debug-tree-prefix';
    treePrefix.textContent = prefix;
    
    // Assemble header: [prefix][connector][toggle][status][info]
    if (depth > 0) {
      header.appendChild(treePrefix);
    }
    header.appendChild(connector);
    header.appendChild(toggle);
    header.appendChild(status);
    header.appendChild(info);
    
    header.addEventListener('click', () => selectEvent(event.id));
    
    node.appendChild(header);
    
    // Children - pass down the prefix for tree lines
    if (children.length > 0 && !collapsedNodes.has(event.id)) {
      const childrenContainer = document.createElement('div');
      childrenContainer.className = 'debug-children';
      
      // Calculate child prefix: add │ if current node is not last, else spaces
      const childPrefix = prefix + (isLast ? '    ' : '│   ');
      
      const filter = getFilter();
      const visibleChildren = children.filter(child => {
        return !filter.type && !filter.status || matchesFilter(child, filter);
      });
      
      visibleChildren.forEach((child, index) => {
        const childIsLast = index === visibleChildren.length - 1;
        childrenContainer.appendChild(renderNode(child, childPrefix, childIsLast, depth + 1));
      });
      
      if (visibleChildren.length > 0) {
        node.appendChild(childrenContainer);
      }
    }
    
    return node;
  }
  
  /**
   * Toggle node collapse state
   */
  function toggleNode(eventId) {
    if (collapsedNodes.has(eventId)) {
      collapsedNodes.delete(eventId);
    } else {
      collapsedNodes.add(eventId);
    }
    render();
  }
  
  /**
   * Select an event
   */
  function selectEvent(eventId) {
    selectedEventId = eventId;
    const event = NB.agentLogger.findEvent(eventId);
    if (event) {
      showDetail(event);
    }
    render();
  }
  
  /**
   * Show event detail
   */
  function showDetail(event) {
    // Remove existing detail
    const existing = content.querySelector('.debug-detail');
    if (existing) {
      existing.remove();
    }
    
    const detail = document.createElement('div');
    detail.className = 'debug-detail';
    
    const header = document.createElement('div');
    header.className = 'debug-detail-header';
    header.textContent = 'Event Details';
    detail.appendChild(header);
    
    // ID
    detail.appendChild(createDetailSection('ID', event.id));
    
    // Type
    detail.appendChild(createDetailSection('Type', formatType(event.type)));
    
    // Status
    detail.appendChild(createDetailSection('Status', event.status));
    
    // Timestamp
    detail.appendChild(createDetailSection('Timestamp', new Date(event.timestamp).toLocaleString()));
    
    // Duration
    if (event.duration !== null) {
      detail.appendChild(createDetailSection('Duration', formatDuration(event.duration)));
    }
    
    // Data
    if (event.data && Object.keys(event.data).length > 0) {
      const dataSection = document.createElement('div');
      dataSection.className = 'debug-detail-section';
      
      const label = document.createElement('div');
      label.className = 'debug-detail-label';
      label.textContent = 'Data';
      dataSection.appendChild(label);
      
      const value = document.createElement('div');
      value.className = 'debug-detail-value' + (event.data.error ? ' error' : '');
      value.textContent = JSON.stringify(event.data, null, 2);
      dataSection.appendChild(value);
      
      detail.appendChild(dataSection);
    }
    
    content.appendChild(detail);
  }
  
  /**
   * Create a detail section
   */
  function createDetailSection(label, value) {
    const section = document.createElement('div');
    section.className = 'debug-detail-section';
    
    const labelEl = document.createElement('div');
    labelEl.className = 'debug-detail-label';
    labelEl.textContent = label;
    
    const valueEl = document.createElement('div');
    valueEl.className = 'debug-detail-value';
    valueEl.textContent = value;
    
    section.appendChild(labelEl);
    section.appendChild(valueEl);
    
    return section;
  }
  
  /**
   * Format event type for display
   */
  function formatType(type) {
    const typeNames = {
      'ai_call': 'AI Call',
      'ai_response': 'AI Response',
      'ai_error': 'AI Error',
      'api_call': 'API Call',
      'api_response': 'API Response',
      'api_error': 'API Error',
      'comment_add': 'Add Comment',
      'comment_complete': 'Comment Complete',
    };
    return typeNames[type] || type;
  }
  
  /**
   * Get summary for event
   */
  function getSummary(event) {
    if (event.data.error) {
      return event.data.error.substring(0, 80);
    }
    if (event.data.provider) {
      return 'Provider: ' + event.data.provider;
    }
    if (event.data.cellId) {
      return 'Cell: ' + event.data.cellId.substring(0, 8) + '...';
    }
    return '';
  }
  
  /**
   * Format timestamp
   */
  function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  }
  
  /**
   * Format duration
   */
  function formatDuration(ms) {
    if (ms < 1000) {
      return ms + 'ms';
    }
    return (ms / 1000).toFixed(2) + 's';
  }
  
  // Public API
  return {
    init,
    show,
    hide,
    toggle,
    visible,
  };
})();
