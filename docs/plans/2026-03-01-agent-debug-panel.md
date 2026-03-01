# Agent Debug Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an agent activity debugging panel to the web interface that visualizes AI operations (comment requests, executions) in a tree structure, with detailed logging for errors like timeouts.

**Architecture:** Create a client-side event logging system that captures agent activities (API calls, responses, errors) with timestamps and durations. Display in a slide-out panel with a tree view showing hierarchical operations (parent requests → child operations → errors). Events are stored in memory with configurable retention.

**Tech Stack:** Vanilla JS (no new dependencies), CSS for tree visualization, integrated with existing Flask web interface

---

### Task 1: Create Agent Logger Module

**Files:**
- Create: `notebook_lr/static/js/agent-logger.js`
- Test: Open web interface and verify module loads

**Step 1: Create the agent logger module**

Create `notebook_lr/static/js/agent-logger.js`:

```javascript
/**
 * Agent Logger - Captures and stores agent activities for debugging
 */
window.NB = window.NB || {};

NB.agentLogger = (function() {
  // Configuration
  const MAX_EVENTS = 1000;  // Maximum events to retain
  const DEFAULT_RETENTION_MINUTES = 30;
  
  // State
  let events = [];
  let listeners = [];
  let isEnabled = true;
  
  // Event types
  const EventType = {
    AI_CALL: 'ai_call',           // AI API call initiated
    AI_RESPONSE: 'ai_response',   // AI response received
    AI_ERROR: 'ai_error',         // AI call failed
    API_CALL: 'api_call',         // General API call
    API_RESPONSE: 'api_response', // API response
    API_ERROR: 'api_error',       // API error
    COMMENT_ADD: 'comment_add',   // Comment creation started
    COMMENT_COMPLETE: 'comment_complete', // Comment creation done
  };
  
  const EventStatus = {
    PENDING: 'pending',
    SUCCESS: 'success',
    ERROR: 'error',
    TIMEOUT: 'timeout',
  };
  
  /**
   * Generate unique ID
   */
  function generateId() {
    return 'evt_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }
  
  /**
   * Create a new event
   */
  function createEvent(type, data = {}, parentId = null) {
    return {
      id: generateId(),
      parentId: parentId,
      type: type,
      status: EventStatus.PENDING,
      timestamp: Date.now(),
      duration: null,
      data: data,
      children: [],
    };
  }
  
  /**
   * Log an event start
   */
  function logStart(type, data = {}, parentId = null) {
    if (!isEnabled) return null;
    
    const event = createEvent(type, data, parentId);
    events.push(event);
    
    // Link to parent if exists
    if (parentId) {
      const parent = findEvent(parentId);
      if (parent) {
        parent.children.push(event.id);
      }
    }
    
    // Trim old events
    if (events.length > MAX_EVENTS) {
      events.shift();
    }
    
    notifyListeners('add', event);
    return event.id;
  }
  
  /**
   * Log an event completion
   */
  function logComplete(eventId, status = EventStatus.SUCCESS, resultData = {}) {
    if (!isEnabled) return;
    
    const event = findEvent(eventId);
    if (!event) return;
    
    event.status = status;
    event.duration = Date.now() - event.timestamp;
    Object.assign(event.data, resultData);
    
    notifyListeners('complete', event);
  }
  
  /**
   * Log an error
   */
  function logError(eventId, error, errorData = {}) {
    if (!isEnabled) return;
    
    const event = findEvent(eventId);
    if (!event) return;
    
    event.status = EventStatus.ERROR;
    event.duration = Date.now() - event.timestamp;
    event.data.error = error.message || String(error);
    event.data.errorType = error.name || 'Error';
    Object.assign(event.data, errorData);
    
    notifyListeners('error', event);
  }
  
  /**
   * Log a timeout
   */
  function logTimeout(eventId, timeoutMs) {
    if (!isEnabled) return;
    
    const event = findEvent(eventId);
    if (!event) return;
    
    event.status = EventStatus.TIMEOUT;
    event.duration = timeoutMs;
    event.data.error = `Operation timed out after ${timeoutMs}ms`;
    event.data.errorType = 'TimeoutError';
    
    notifyListeners('timeout', event);
  }
  
  /**
   * Find event by ID
   */
  function findEvent(eventId) {
    return events.find(e => e.id === eventId);
  }
  
  /**
   * Get all events (optionally filtered)
   */
  function getEvents(filter = {}) {
    let result = [...events];
    
    if (filter.type) {
      result = result.filter(e => e.type === filter.type);
    }
    if (filter.status) {
      result = result.filter(e => e.status === filter.status);
    }
    if (filter.parentId !== undefined) {
      result = result.filter(e => e.parentId === filter.parentId);
    }
    if (filter.since) {
      result = result.filter(e => e.timestamp >= filter.since);
    }
    
    return result;
  }
  
  /**
   * Get root events (no parent)
   */
  function getRootEvents() {
    return events.filter(e => e.parentId === null);
  }
  
  /**
   * Get children of an event
   */
  function getChildren(eventId) {
    return events.filter(e => e.parentId === eventId);
  }
  
  /**
   * Clear all events
   */
  function clear() {
    events = [];
    notifyListeners('clear');
  }
  
  /**
   * Enable/disable logging
   */
  function setEnabled(enabled) {
    isEnabled = enabled;
  }
  
  /**
   * Subscribe to events
   */
  function subscribe(callback) {
    listeners.push(callback);
    return function unsubscribe() {
      listeners = listeners.filter(l => l !== callback);
    };
  }
  
  /**
   * Notify all listeners
   */
  function notifyListeners(action, event = null) {
    listeners.forEach(cb => {
      try {
        cb(action, event);
      } catch (e) {
        console.error('Agent logger listener error:', e);
      }
    });
  }
  
  /**
   * Get statistics
   */
  function getStats() {
    const stats = {
      total: events.length,
      byType: {},
      byStatus: {},
      avgDuration: 0,
      errors: 0,
      timeouts: 0,
    };
    
    let totalDuration = 0;
    let durationCount = 0;
    
    events.forEach(e => {
      // By type
      stats.byType[e.type] = (stats.byType[e.type] || 0) + 1;
      // By status
      stats.byStatus[e.status] = (stats.byStatus[e.status] || 0) + 1;
      // Duration
      if (e.duration !== null) {
        totalDuration += e.duration;
        durationCount++;
      }
      // Errors and timeouts
      if (e.status === EventStatus.ERROR) stats.errors++;
      if (e.status === EventStatus.TIMEOUT) stats.timeouts++;
    });
    
    if (durationCount > 0) {
      stats.avgDuration = Math.round(totalDuration / durationCount);
    }
    
    return stats;
  }
  
  // Public API
  return {
    EventType,
    EventStatus,
    logStart,
    logComplete,
    logError,
    logTimeout,
    findEvent,
    getEvents,
    getRootEvents,
    getChildren,
    clear,
    setEnabled,
    subscribe,
    getStats,
  };
})();
```

**Step 2: Add to HTML template**

Modify `notebook_lr/templates/notebook.html` around line 152 to include the new JS file:

```html
  <script src="/static/js/api.js"></script>
  <script src="/static/js/agent-logger.js"></script>
  <script src="/static/js/editor.js"></script>
```

**Step 3: Test in browser**

Run: Open web interface (`notebook-lr web test.nblr`), open browser console, verify:
```javascript
> NB.agentLogger
// Should show the logger object
```

**Step 4: Commit**

```bash
git add notebook_lr/static/js/agent-logger.js notebook_lr/templates/notebook.html
git commit -m "feat: add agent logger module for tracking AI operations"
```

---

### Task 2: Create Debug Panel UI

**Files:**
- Create: `notebook_lr/static/js/debug-panel.js`
- Modify: `notebook_lr/templates/notebook.html` - Add panel HTML
- Modify: `notebook_lr/static/css/notebook.css` - Add panel styles

**Step 1: Add panel HTML to template**

Add to `notebook_lr/templates/notebook.html` before the closing `</div>` of `#notebook-app` (around line 141):

```html
    <!-- Debug Panel -->
    <div id="debug-panel" class="panel hidden">
      <div class="panel-header">
        <h3>Agent Debug</h3>
        <div class="panel-actions">
          <button id="debug-clear-btn" class="panel-btn" title="Clear All">Clear</button>
          <button id="debug-pause-btn" class="panel-btn" title="Pause/Resume">Pause</button>
          <button id="close-debug-btn" class="close-btn">&times;</button>
        </div>
      </div>
      <div class="panel-toolbar">
        <div class="debug-stats">
          <span class="stat-item"><span class="stat-label">Total:</span> <span id="debug-stat-total">0</span></span>
          <span class="stat-item"><span class="stat-label">Errors:</span> <span id="debug-stat-errors">0</span></span>
          <span class="stat-item"><span class="stat-label">Timeouts:</span> <span id="debug-stat-timeouts">0</span></span>
        </div>
        <div class="debug-filter">
          <select id="debug-filter-type">
            <option value="">All Types</option>
            <option value="ai_call">AI Calls</option>
            <option value="api_call">API Calls</option>
            <option value="comment_add">Comments</option>
          </select>
          <select id="debug-filter-status">
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
            <option value="timeout">Timeout</option>
          </select>
        </div>
      </div>
      <div id="debug-content" class="panel-content">
        <div class="debug-tree"></div>
      </div>
    </div>
```

**Step 2: Add CSS styles**

Add to `notebook_lr/static/css/notebook.css`:

```css
/* Debug Panel */
#debug-panel {
  position: fixed;
  right: 0;
  top: 0;
  width: 450px;
  height: 100%;
  background: #1e1e1e;
  border-left: 1px solid #333;
  display: flex;
  flex-direction: column;
  z-index: 1000;
  transform: translateX(100%);
  transition: transform 0.3s ease;
}

#debug-panel.visible {
  transform: translateX(0);
}

#debug-panel .panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #252526;
  border-bottom: 1px solid #333;
}

#debug-panel .panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: #cccccc;
}

#debug-panel .panel-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.panel-btn {
  background: #3c3c3c;
  border: 1px solid #555;
  color: #cccccc;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  border-radius: 3px;
}

.panel-btn:hover {
  background: #4c4c4c;
}

#debug-panel .panel-toolbar {
  padding: 10px 16px;
  background: #1e1e1e;
  border-bottom: 1px solid #333;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.debug-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  font-size: 12px;
  color: #969696;
}

.stat-label {
  color: #6e6e6e;
}

.stat-item span:last-child {
  color: #cccccc;
  font-weight: 500;
}

#debug-stat-errors {
  color: #f48771;
}

#debug-stat-timeouts {
  color: #ffcc00;
}

.debug-filter {
  display: flex;
  gap: 8px;
}

.debug-filter select {
  background: #3c3c3c;
  border: 1px solid #555;
  color: #cccccc;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 3px;
}

#debug-panel .panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

/* Debug Tree */
.debug-tree {
  padding: 8px 0;
}

.debug-node {
  display: flex;
  flex-direction: column;
}

.debug-node-header {
  display: flex;
  align-items: flex-start;
  padding: 8px 16px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s;
}

.debug-node-header:hover {
  background: #2a2d2e;
}

.debug-node-header.selected {
  background: #37373d;
  border-left-color: #007acc;
}

.debug-toggle {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 4px;
  color: #969696;
  font-size: 10px;
  flex-shrink: 0;
}

.debug-toggle.leaf {
  visibility: hidden;
}

.debug-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  margin-top: 4px;
  flex-shrink: 0;
}

.debug-status.pending { background: #007acc; animation: pulse 1.5s infinite; }
.debug-status.success { background: #89d185; }
.debug-status.error { background: #f48771; }
.debug-status.timeout { background: #ffcc00; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.debug-info {
  flex: 1;
  min-width: 0;
}

.debug-type {
  font-size: 12px;
  font-weight: 500;
  color: #cccccc;
  margin-bottom: 2px;
}

.debug-summary {
  font-size: 11px;
  color: #969696;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.debug-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #6e6e6e;
  margin-top: 4px;
}

.debug-duration {
  font-family: 'Roboto Mono', monospace;
}

.debug-children {
  margin-left: 20px;
  border-left: 1px solid #333;
}

.debug-node.collapsed .debug-children {
  display: none;
}

.debug-node.collapsed .debug-toggle::before {
  content: '▶';
}

.debug-node.expanded .debug-toggle::before {
  content: '▼';
}

/* Debug Detail View */
.debug-detail {
  padding: 16px;
  background: #252526;
  border-top: 1px solid #333;
  font-size: 12px;
}

.debug-detail-header {
  font-weight: 500;
  color: #cccccc;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #333;
}

.debug-detail-section {
  margin-bottom: 16px;
}

.debug-detail-label {
  color: #6e6e6e;
  font-size: 11px;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.debug-detail-value {
  color: #cccccc;
  font-family: 'Roboto Mono', monospace;
  background: #1e1e1e;
  padding: 8px;
  border-radius: 3px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.debug-detail-value.error {
  color: #f48771;
}

/* Debug Toolbar Button */
#debug-btn {
  position: relative;
}

#debug-btn.has-errors::after {
  content: '';
  position: absolute;
  top: 4px;
  right: 4px;
  width: 8px;
  height: 8px;
  background: #f48771;
  border-radius: 50%;
}
```

**Step 3: Create debug panel JS module**

Create `notebook_lr/static/js/debug-panel.js`:

```javascript
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
    
    if (eventsToShow.length === 0) {
      treeEl.innerHTML = '<div class="debug-empty" style="padding: 20px; text-align: center; color: #6e6e6e;">No events</div>';
      return;
    }
    
    treeEl.innerHTML = '';
    eventsToShow.slice().reverse().forEach(event => {
      treeEl.appendChild(renderNode(event, 0));
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
   * Render a single node
   */
  function renderNode(event, depth) {
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
    header.style.paddingLeft = (16 + depth * 20) + 'px';
    
    // Toggle button
    const children = NB.agentLogger.getChildren(event.id);
    const toggle = document.createElement('span');
    toggle.className = 'debug-toggle' + (children.length === 0 ? ' leaf' : '');
    toggle.textContent = children.length > 0 ? (collapsedNodes.has(event.id) ? '▶' : '▼') : '';
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
    
    header.appendChild(toggle);
    header.appendChild(status);
    header.appendChild(info);
    
    header.addEventListener('click', () => selectEvent(event.id));
    
    node.appendChild(header);
    
    // Children
    if (children.length > 0) {
      const childrenContainer = document.createElement('div');
      childrenContainer.className = 'debug-children';
      
      const filter = getFilter();
      children.forEach(child => {
        if (!filter.type && !filter.status || matchesFilter(child, filter)) {
          childrenContainer.appendChild(renderNode(child, depth + 1));
        }
      });
      
      node.appendChild(childrenContainer);
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
      return `Provider: ${event.data.provider}`;
    }
    if (event.data.cellId) {
      return `Cell: ${event.data.cellId.substring(0, 8)}...`;
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
```

**Step 4: Add to HTML template**

Add script tag in `notebook_lr/templates/notebook.html` after agent-logger.js:

```html
  <script src="/static/js/api.js"></script>
  <script src="/static/js/agent-logger.js"></script>
  <script src="/static/js/debug-panel.js"></script>
  <script src="/static/js/editor.js"></script>
```

**Step 5: Add toolbar button**

Add to toolbar in `notebook_lr/templates/notebook.html` (around line 87):

```html
      <div class="toolbar-spacer"></div>
      <button id="debug-btn" class="toolbar-btn" title="Agent Debug Panel">
        <span class="icon">&#128027;</span> <span class="btn-label">Debug</span>
      </button>
      <button id="help-btn" class="toolbar-btn" title="Keyboard Shortcuts (?)" style="margin-left: auto;">
```

**Step 6: Test**

Run: Start web interface, click Debug button, verify panel opens with empty state.

**Step 7: Commit**

```bash
git add notebook_lr/static/js/debug-panel.js notebook_lr/templates/notebook.html notebook_lr/static/css/notebook.css
git commit -m "feat: add agent debug panel UI with tree visualization"
```

---

### Task 3: Integrate Logger with API Calls

**Files:**
- Modify: `notebook_lr/static/js/api.js`
- Modify: `notebook_lr/static/js/comments.js`
- Modify: `notebook_lr/static/js/app.js` - Add debug button handler

**Step 1: Instrument API module**

Modify `notebook_lr/static/js/api.js` to wrap API calls with logging:

```javascript
window.NB = window.NB || {};

NB.api = (function() {
  async function _handleResponse(res, operation, eventId) {
    // Log response
    if (eventId && NB.agentLogger) {
      NB.agentLogger.logComplete(eventId, 'success', { status: res.status });
    }
    
    if (!res.ok) {
      let errorMsg;
      try {
        const errorData = await res.json();
        errorMsg = errorData.error || errorData.message || res.statusText;
      } catch (e) {
        errorMsg = await res.text() || res.statusText || 'Unknown error';
      }
      
      // Log error
      if (eventId && NB.agentLogger) {
        NB.agentLogger.logError(eventId, new Error(errorMsg), { status: res.status });
      }
      
      console.error('API Error (' + operation + '):', errorMsg);
      throw new Error(errorMsg);
    }
    return res.json();
  }

  async function _get(url) {
    // Log API call start
    let eventId = null;
    if (NB.agentLogger) {
      eventId = NB.agentLogger.logStart('api_call', { method: 'GET', url: url });
    }
    
    try {
      const res = await fetch(url);
      return await _handleResponse(res, 'GET ' + url, eventId);
    } catch (err) {
      if (eventId && NB.agentLogger) {
        NB.agentLogger.logError(eventId, err);
      }
      
      if (err.name === 'TypeError' || err.message.includes('fetch')) {
        throw new Error('Network error - please check your connection');
      }
      throw err;
    }
  }

  async function _post(url, data) {
    // Log API call start
    let eventId = null;
    if (NB.agentLogger) {
      eventId = NB.agentLogger.logStart('api_call', { method: 'POST', url: url, body: data });
    }
    
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      return await _handleResponse(res, 'POST ' + url, eventId);
    } catch (err) {
      if (eventId && NB.agentLogger) {
        NB.agentLogger.logError(eventId, err);
      }
      
      if (err.name === 'TypeError' || err.message.includes('fetch')) {
        throw new Error('Network error - please check your connection');
      }
      throw err;
    }
  }

  return {
    getNotebook() { return _get('/api/notebook'); },
    addCell(afterIndex, type) { return _post('/api/cell/add', { after_index: afterIndex, type: type }); },
    deleteCell(index) { return _post('/api/cell/delete', { index: index }); },
    moveCell(index, direction) { return _post('/api/cell/move', { index: index, direction: direction }); },
    updateCell(index, source) { return _post('/api/cell/update', { index: index, source: source }); },
    executeCell(index, source) { return _post('/api/cell/execute', { index: index, source: source }); },
    executeAll() { return _post('/api/execute-all', {}); },
    save(includeSession) { return _post('/api/save', { include_session: includeSession }); },
    async load(file) {
      let eventId = null;
      if (NB.agentLogger) {
        eventId = NB.agentLogger.logStart('api_call', { method: 'POST', url: '/api/load', filename: file.name });
      }
      
      const formData = new FormData();
      formData.append('file', file);
      
      try {
        const res = await fetch('/api/load', { method: 'POST', body: formData });
        const result = await _handleResponse(res, 'POST /api/load', eventId);
        return result;
      } catch (err) {
        if (eventId && NB.agentLogger) {
          NB.agentLogger.logError(eventId, err);
        }
        throw err;
      }
    },
    getVariables() { return _get('/api/variables'); },
    clearVariables() { return _post('/api/clear-variables', {}); },
    getNotebookInfo() { return _get('/api/notebook-info'); },
    addComment(cellId, data) { 
      return _post('/api/cell/comment/add', Object.assign({ cell_id: cellId }, data)); 
    },
    deleteComment(cellId, commentId) { 
      return _post('/api/cell/comment/delete', { cell_id: cellId, comment_id: commentId }); 
    }
  };
})();
```

**Step 2: Instrument comment operations**

Modify `notebook_lr/static/js/comments.js` - in the `createCommentForm` function, wrap the API call with AI-specific logging:

Find the `askBtn.addEventListener('click', ...)` section and replace the API call with:

```javascript
    // Ask AI handler
    askBtn.addEventListener('click', function () {
      var userComment = textarea.value.trim();
      if (!userComment) {
        textarea.focus();
        return;
      }

      // Disable form, show spinner
      textarea.disabled = true;
      askBtn.disabled = true;
      cancelBtn.disabled = true;
      askBtn.innerHTML = '<span class="comment-spinner"></span> Asking...';

      // Log the AI call start
      var parentEventId = null;
      if (NB.agentLogger) {
        parentEventId = NB.agentLogger.logStart('comment_add', { 
          cellId: cellId,
          provider: selectedProvider 
        });
        // Create child event for AI call
        var aiEventId = NB.agentLogger.logStart('ai_call', {
          cellId: cellId,
          provider: selectedProvider,
          userComment: userComment.substring(0, 100)
        }, parentEventId);
      }

      NB.api.addComment(cellId, {
        from_line: from.line,
        from_ch: from.ch,
        to_line: to.line,
        to_ch: to.ch,
        selected_text: selectedText,
        user_comment: userComment,
        provider: selectedProvider
      }).then(function (res) {
        // Complete AI call event
        if (NB.agentLogger && aiEventId) {
          NB.agentLogger.logComplete(aiEventId, res.comment && res.comment.status === 'error' ? 'error' : 'success', {
            commentId: res.comment ? res.comment.id : null
          });
        }
        
        // Complete parent event
        if (NB.agentLogger && parentEventId) {
          NB.agentLogger.logComplete(parentEventId, res.comment && res.comment.status === 'error' ? 'error' : 'success');
        }
        
        if (res.ok && res.comment) {
          replaceFormWithResult(cm, cellId, node, marker, res.comment);
        } else {
          askBtn.textContent = 'Ask AI';
          askBtn.disabled = false;
          textarea.disabled = false;
          cancelBtn.disabled = false;
        }
      }).catch(function (err) {
        console.error('Comment error:', err);
        
        // Check for timeout
        var isTimeout = err.message && (
          err.message.includes('timeout') || 
          err.message.includes('시간 초과') ||
          err.message.includes('time out')
        );
        
        if (NB.agentLogger && aiEventId) {
          if (isTimeout) {
            NB.agentLogger.logTimeout(aiEventId, 120000); // 2 min default timeout
          } else {
            NB.agentLogger.logError(aiEventId, err);
          }
        }
        
        if (NB.agentLogger && parentEventId) {
          NB.agentLogger.logError(parentEventId, err);
        }
        
        askBtn.textContent = 'Ask AI';
        askBtn.disabled = false;
        textarea.disabled = false;
        cancelBtn.disabled = false;
      });
    });
```

**Step 3: Add debug button handler**

Modify `notebook_lr/static/js/app.js` - add initialization for debug panel. Find where other buttons are initialized and add:

```javascript
  // Debug panel button
  var debugBtn = document.getElementById('debug-btn');
  if (debugBtn && NB.debugPanel) {
    debugBtn.addEventListener('click', function() {
      NB.debugPanel.toggle();
    });
  }
  
  // Initialize debug panel
  if (NB.debugPanel) {
    NB.debugPanel.init();
  }
```

**Step 4: Test**

Run: Start web interface, open debug panel, add a comment and verify:
1. Events appear in tree
2. AI call shows as child of comment_add
3. On timeout, shows timeout status with yellow indicator
4. Details panel shows full event info

**Step 5: Commit**

```bash
git add notebook_lr/static/js/api.js notebook_lr/static/js/comments.js notebook_lr/static/js/app.js
git commit -m "feat: integrate agent logger with API and comment operations"
```

---

### Task 4: Add Execution Logging

**Files:**
- Modify: `notebook_lr/static/js/execution.js`

**Step 1: Add logging to cell execution**

Modify `notebook_lr/static/js/execution.js` - wrap cell execution with logging:

Find where cells are executed and add logging. Example pattern:

```javascript
  function executeCell(index) {
    // ... existing code ...
    
    // Log execution start
    var eventId = null;
    if (NB.agentLogger) {
      eventId = NB.agentLogger.logStart('cell_execute', { 
        cellIndex: index,
        cellId: cell.id 
      });
    }
    
    return NB.api.executeCell(index, source)
      .then(function(result) {
        // Log success
        if (eventId && NB.agentLogger) {
          NB.agentLogger.logComplete(eventId, result.success ? 'success' : 'error', {
            executionCount: result.execution_count,
            outputCount: result.outputs ? result.outputs.length : 0
          });
        }
        
        // ... existing success handling ...
      })
      .catch(function(err) {
        // Log error
        if (eventId && NB.agentLogger) {
          NB.agentLogger.logError(eventId, err);
        }
        
        // ... existing error handling ...
      });
  }
```

**Step 2: Add logging to execute all**

Similarly wrap the execute all functionality:

```javascript
  function executeAll() {
    var eventId = null;
    if (NB.agentLogger) {
      eventId = NB.agentLogger.logStart('execute_all', { cellCount: NB.cells.getCellCount() });
    }
    
    // ... existing execute all code ...
    
    // On completion:
    if (eventId && NB.agentLogger) {
      NB.agentLogger.logComplete(eventId, 'success', { executed: executedCount });
    }
  }
```

**Step 3: Test**

Run: Execute cells, verify execution events appear in debug panel.

**Step 4: Commit**

```bash
git add notebook_lr/static/js/execution.js
git commit -m "feat: add execution logging to agent debug panel"
```

---

### Task 5: Add Keyboard Shortcut

**Files:**
- Modify: `notebook_lr/static/js/app.js`
- Modify: `notebook_lr/templates/notebook.html` - Update shortcuts modal

**Step 1: Add keyboard shortcut**

Modify `notebook_lr/static/js/app.js` - add to keyboard handler:

```javascript
  // Keyboard shortcuts
  document.addEventListener('keydown', function(e) {
    // Debug panel: Ctrl/Cmd + Shift + D
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
      e.preventDefault();
      if (NB.debugPanel) {
        NB.debugPanel.toggle();
      }
      return;
    }
    
    // ... existing shortcuts ...
  });
```

**Step 2: Update shortcuts modal**

Add to `notebook_lr/templates/notebook.html` in the shortcuts modal:

```html
            <div class="shortcut-section">
              <h4>Debug</h4>
              <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>D</kbd> Toggle Debug Panel</div>
            </div>
```

**Step 3: Test**

Run: Press Ctrl+Shift+D, verify panel toggles.

**Step 4: Commit**

```bash
git add notebook_lr/static/js/app.js notebook_lr/templates/notebook.html
git commit -m "feat: add keyboard shortcut for debug panel (Ctrl+Shift+D)"
```

---

### Task 6: Final Verification

**Files:**
- All modified files

**Step 1: Run all tests**

```bash
pytest tests/test_web_*.py -v --tb=short
```
Expected: All web tests pass

**Step 2: Manual verification checklist**

Run web interface and verify:
- [ ] Debug button appears in toolbar
- [ ] Clicking debug button opens panel
- [ ] Panel shows empty state initially
- [ ] Adding comment creates events in tree
- [ ] AI call shows as child of comment event
- [ ] Timeout shows yellow status indicator
- [ ] Error shows red status indicator
- [ ] Clicking event shows details
- [ ] Filters work (type, status)
- [ ] Clear button clears events
- [ ] Pause button pauses updates
- [ ] Ctrl+Shift+D toggles panel
- [ ] Panel closes with X button

**Step 3: Commit final changes**

```bash
git add -A
git commit -m "feat: complete agent debug panel implementation"
```

---

## Summary

This implementation adds:

1. **Agent Logger** (`agent-logger.js`) - Captures all agent activities with parent-child relationships
2. **Debug Panel** (`debug-panel.js`) - Tree visualization with:
   - Hierarchical display (parent → children)
   - Color-coded status indicators (pending/blue, success/green, error/red, timeout/yellow)
   - Real-time statistics (total, errors, timeouts)
   - Filters (by type, by status)
   - Event detail view
   - Pause/resume and clear controls
3. **Integration** - All API calls, comment operations, and cell executions are logged
4. **Keyboard Shortcut** - Ctrl+Shift+D to toggle panel

The tree structure lets you see:
```
Add Comment
└── AI Call (Claude)
    └── Error: AI 응답 시간 초과
```

This makes debugging agent issues much easier!
