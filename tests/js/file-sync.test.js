const fs = require('fs');
const path = require('path');

// Helper to properly flush async microtask queue
function flushPromises() {
  return new Promise(process.nextTick);
}

function createMockLogger() {
  return {
    EventType: {
      FILE_CHANGE_DETECTED: 'file_change_detected',
      FILE_AUTO_RELOAD: 'file_auto_reload',
      FILE_CONFLICT: 'file_conflict',
      FILE_CONFLICT_RESOLVED: 'file_conflict_resolved',
      FILE_POLL_ERROR: 'file_poll_error',
    },
    EventStatus: { PENDING: 'pending', SUCCESS: 'success', ERROR: 'error' },
    logStart: jest.fn(() => 'mock_evt_id'),
    logComplete: jest.fn(),
    logError: jest.fn(),
  };
}

function loadFileSync(opts = {}) {
  window.NB = {};

  // Mock dependencies
  window.NB.fileops = { _isDirty: false, _updateIndicator: jest.fn() };
  window.NB.cells = { renderAll: jest.fn() };
  window.NB.toolbar = { updateInfo: jest.fn(), showSuccess: jest.fn() };

  if (opts.withLogger) {
    window.NB.agentLogger = createMockLogger();
  }

  const code = fs.readFileSync(
    path.resolve(__dirname, '../../notebook_lr/static/js/file-sync.js'),
    'utf-8'
  );
  new Function(code)();
  return window.NB.fileSync;
}

beforeEach(() => {
  jest.useFakeTimers({ doNotFake: ['nextTick'] });
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.useRealTimers();
  if (window.NB && window.NB.fileSync) {
    window.NB.fileSync.stop();
  }
});

describe('file-sync', () => {
  let fileSync;

  beforeEach(() => {
    document.body.innerHTML = '';
    Object.defineProperty(document, 'hidden', { value: false, writable: true, configurable: true });
    fileSync = loadFileSync();
  });

  describe('start / stop', () => {
    it('start()하면 폴링이 시작된다', () => {
      fileSync.start();
      expect(jest.getTimerCount()).toBe(1);
    });

    it('stop()하면 폴링이 중지된다', () => {
      fileSync.start();
      fileSync.stop();
      expect(jest.getTimerCount()).toBe(0);
    });

    it('중복 start()는 타이머를 중복 생성하지 않는다', () => {
      fileSync.start();
      fileSync.start();
      expect(jest.getTimerCount()).toBe(1);
    });
  });

  describe('polling', () => {
    it('변경 없으면 아무 동작 없이 다음 폴링을 예약한다', async () => {
      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ changed: false }),
      });

      fileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith('/api/notebook/check-updates');
      expect(document.getElementById('file-sync-toast')).toBeNull();
    });

    it('변경 감지 + dirty=false이면 자동 리로드한다', async () => {
      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({
            cells: [{ id: '1', type: 'code', source: 'x=1' }],
            metadata: {},
            mtime: 123,
          }),
        });

      window.NB.fileops._isDirty = false;
      fileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith('/api/notebook/reload', { method: 'POST' });
      expect(window.NB.cells.renderAll).toHaveBeenCalled();
      expect(window.NB.toolbar.updateInfo).toHaveBeenCalled();
    });

    it('변경 감지 + dirty=true이면 충돌 다이얼로그를 표시한다', async () => {
      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ changed: true }),
      });

      window.NB.fileops._isDirty = true;
      fileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      const modal = document.getElementById('file-conflict-modal');
      expect(modal).toBeTruthy();
      expect(document.getElementById('conflict-reload-btn')).toBeTruthy();
      expect(document.getElementById('conflict-keep-btn')).toBeTruthy();
    });
  });

  describe('conflict dialog', () => {
    beforeEach(async () => {
      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ changed: true }),
      });
      window.NB.fileops._isDirty = true;
      fileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();
    });

    it('Reload 선택 시 서버에서 리로드하고 dirty를 false로 설정한다', async () => {
      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({
          cells: [{ id: '1', type: 'code', source: 'y=2' }],
          metadata: {},
          mtime: 456,
        }),
      });

      document.getElementById('conflict-reload-btn').click();
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith('/api/notebook/reload', { method: 'POST' });
      expect(window.NB.cells.renderAll).toHaveBeenCalled();
      expect(window.NB.fileops._isDirty).toBe(false);
      expect(document.getElementById('file-conflict-modal')).toBeNull();
    });

    it('Keep mine 선택 시 acknowledge API를 호출한다', async () => {
      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ acknowledged: true, mtime: 789 }),
      });

      document.getElementById('conflict-keep-btn').click();
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith('/api/notebook/acknowledge', { method: 'POST' });
      expect(document.getElementById('file-conflict-modal')).toBeNull();
    });

    it('다이얼로그가 열려 있으면 추가 폴링을 하지 않는다', () => {
      const fetchCallCount = global.fetch.mock.calls.length;
      jest.advanceTimersByTime(8000);
      expect(global.fetch.mock.calls.length).toBe(fetchCallCount);
    });
  });

  describe('notifySaved', () => {
    it('저장 직후에는 폴링을 스킵한다', async () => {
      fileSync.start();
      // Advance to just before poll fires, then notify saved
      jest.advanceTimersByTime(3000);
      fileSync.notifySaved(); // _lastSaveTime = 3000
      jest.advanceTimersByTime(1000); // poll fires at 4000, 4000-3000=1000 < 2000 cooldown
      await flushPromises();

      // Should not have called check-updates because of save cooldown
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('toast', () => {
    it('자동 리로드 시 토스트를 표시한다', async () => {
      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ cells: [], metadata: {}, mtime: 1 }),
        });

      window.NB.fileops._isDirty = false;
      fileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      const toast = document.getElementById('file-sync-toast');
      expect(toast).toBeTruthy();
      expect(toast.textContent).toContain('리로드');
    });

    it('토스트가 4초 후 자동으로 사라진다', async () => {
      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ cells: [], metadata: {}, mtime: 1 }),
        });

      window.NB.fileops._isDirty = false;
      fileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      expect(document.getElementById('file-sync-toast')).toBeTruthy();
      jest.advanceTimersByTime(4300);
      expect(document.getElementById('file-sync-toast')).toBeNull();
    });
  });

  describe('visibility change', () => {
    it('페이지가 hidden이면 폴링을 중지한다', () => {
      fileSync.start();
      Object.defineProperty(document, 'hidden', { value: true, writable: true });
      document.dispatchEvent(new Event('visibilitychange'));

      expect(jest.getTimerCount()).toBe(0);
    });
  });

  describe('network error', () => {
    it('네트워크 에러 시 폴링을 계속한다', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'));
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      fileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      expect(jest.getTimerCount()).toBeGreaterThan(0);
      consoleSpy.mockRestore();
    });
  });

  describe('agent-logger 연동 (T5)', () => {
    let loggerFileSync;

    beforeEach(() => {
      document.body.innerHTML = '';
      loggerFileSync = loadFileSync({ withLogger: true });
    });

    it('변경 감지 시 FILE_CHANGE_DETECTED를 로깅한다', async () => {
      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ cells: [], metadata: {}, mtime: 1 }),
        });

      window.NB.fileops._isDirty = false;
      loggerFileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      const logger = window.NB.agentLogger;
      expect(logger.logStart).toHaveBeenCalledWith(
        'file_change_detected',
        expect.objectContaining({ action: '외부 파일 변경 감지' })
      );
    });

    it('자동 리로드 시 FILE_AUTO_RELOAD를 로깅한다', async () => {
      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ cells: [{ id: '1' }], metadata: {}, mtime: 1 }),
        });

      window.NB.fileops._isDirty = false;
      loggerFileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      const logger = window.NB.agentLogger;
      expect(logger.logStart).toHaveBeenCalledWith(
        'file_auto_reload',
        expect.objectContaining({ action: '자동 리로드 완료', cellCount: 1 })
      );
      expect(logger.logComplete).toHaveBeenCalledWith('mock_evt_id', 'success');
    });

    it('충돌 다이얼로그 표시 시 FILE_CONFLICT를 로깅한다', async () => {
      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ changed: true }),
      });

      window.NB.fileops._isDirty = true;
      loggerFileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      const logger = window.NB.agentLogger;
      expect(logger.logStart).toHaveBeenCalledWith(
        'file_conflict',
        expect.objectContaining({ action: '충돌 다이얼로그 표시', dirty: true })
      );
    });

    it('Reload 선택 시 FILE_CONFLICT_RESOLVED를 로깅한다', async () => {
      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) });

      window.NB.fileops._isDirty = true;
      loggerFileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ cells: [], metadata: {}, mtime: 2 }),
      });

      document.getElementById('conflict-reload-btn').click();
      await flushPromises();

      const logger = window.NB.agentLogger;
      expect(logger.logStart).toHaveBeenCalledWith(
        'file_conflict_resolved',
        expect.objectContaining({ choice: 'reload' })
      );
    });

    it('Keep mine 선택 시 FILE_CONFLICT_RESOLVED를 로깅한다', async () => {
      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) });

      window.NB.fileops._isDirty = true;
      loggerFileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      global.fetch.mockResolvedValueOnce({
        json: () => Promise.resolve({ acknowledged: true, mtime: 3 }),
      });

      document.getElementById('conflict-keep-btn').click();
      await flushPromises();

      const logger = window.NB.agentLogger;
      expect(logger.logStart).toHaveBeenCalledWith(
        'file_conflict_resolved',
        expect.objectContaining({ choice: 'keep' })
      );
    });

    it('네트워크 에러 시 FILE_POLL_ERROR를 로깅한다', async () => {
      const networkError = new Error('Network error');
      global.fetch.mockRejectedValueOnce(networkError);
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      loggerFileSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      const logger = window.NB.agentLogger;
      expect(logger.logStart).toHaveBeenCalledWith('file_poll_error', {});
      expect(logger.logError).toHaveBeenCalledWith('mock_evt_id', networkError);
      consoleSpy.mockRestore();
    });

    it('agentLogger가 없으면 에러 없이 동작한다', async () => {
      // Re-load without logger
      document.body.innerHTML = '';
      const noLoggerSync = loadFileSync({ withLogger: false });

      global.fetch
        .mockResolvedValueOnce({ json: () => Promise.resolve({ changed: true }) })
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ cells: [], metadata: {}, mtime: 1 }),
        });

      window.NB.fileops._isDirty = false;
      noLoggerSync.start();
      jest.advanceTimersByTime(4000);
      await flushPromises();

      // Should not throw — just works without logging
      expect(global.fetch).toHaveBeenCalledWith('/api/notebook/check-updates');
    });
  });
});
