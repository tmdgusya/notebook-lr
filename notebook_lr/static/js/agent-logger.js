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
    FILE_CHANGE_DETECTED: 'file_change_detected', // External file change detected
    FILE_AUTO_RELOAD: 'file_auto_reload',           // Auto-reload triggered
    FILE_CONFLICT: 'file_conflict',                 // Conflict dialog shown
    FILE_CONFLICT_RESOLVED: 'file_conflict_resolved', // User resolved conflict
    FILE_POLL_ERROR: 'file_poll_error',             // Polling error occurred
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
