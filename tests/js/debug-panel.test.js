const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadModules() {
  window.NB = {};

  // Set up minimal DOM for debug panel
  document.body.innerHTML = `
    <div id="debug-panel" class="hidden">
      <div id="debug-content">
        <div class="debug-tree"></div>
      </div>
      <button id="close-debug-btn"></button>
      <button id="debug-clear-btn"></button>
      <button id="debug-pause-btn">Pause</button>
      <select id="debug-filter-type"><option value="">All</option></select>
      <select id="debug-filter-status"><option value="">All</option></select>
      <span id="debug-stat-total">0</span>
      <span id="debug-stat-errors">0</span>
      <span id="debug-stat-timeouts">0</span>
      <button id="debug-btn"></button>
    </div>
  `;

  // Load agent-logger first (dependency)
  const loggerCode = fs.readFileSync(
    path.resolve(__dirname, '../../notebook_lr/static/js/agent-logger.js'),
    'utf-8'
  );
  new Function(loggerCode)();

  // Load debug-panel
  const panelCode = fs.readFileSync(
    path.resolve(__dirname, '../../notebook_lr/static/js/debug-panel.js'),
    'utf-8'
  );
  new Function(panelCode)();

  return { logger: window.NB.agentLogger, panel: window.NB.debugPanel };
}

describe('debug-panel', () => {
  let logger, panel;

  beforeEach(() => {
    const modules = loadModules();
    logger = modules.logger;
    panel = modules.panel;
    panel.init();
  });

  describe('init', () => {
    it('DOM 요소를 바인딩한다', () => {
      // init should not throw and panel should work
      expect(panel.visible()).toBe(false);
    });

    it('DOM에 debug-panel이 없으면 경고를 출력하고 에러 없이 처리한다', () => {
      window.NB = {};
      document.body.innerHTML = '';

      const loggerCode = fs.readFileSync(
        path.resolve(__dirname, '../../notebook_lr/static/js/agent-logger.js'),
        'utf-8'
      );
      new Function(loggerCode)();

      const panelCode = fs.readFileSync(
        path.resolve(__dirname, '../../notebook_lr/static/js/debug-panel.js'),
        'utf-8'
      );
      new Function(panelCode)();

      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      window.NB.debugPanel.init();
      expect(consoleSpy).toHaveBeenCalledWith('Debug panel not found in DOM');
      consoleSpy.mockRestore();
    });
  });

  describe('show / hide / toggle', () => {
    it('show()하면 패널이 보인다', () => {
      panel.show();
      expect(panel.visible()).toBe(true);
      const el = document.getElementById('debug-panel');
      expect(el.classList.contains('visible')).toBe(true);
      expect(el.classList.contains('hidden')).toBe(false);
    });

    it('hide()하면 패널이 숨겨진다', () => {
      panel.show();
      panel.hide();
      expect(panel.visible()).toBe(false);
      const el = document.getElementById('debug-panel');
      expect(el.classList.contains('hidden')).toBe(true);
      expect(el.classList.contains('visible')).toBe(false);
    });

    it('toggle()하면 상태가 전환된다', () => {
      expect(panel.visible()).toBe(false);
      panel.toggle();
      expect(panel.visible()).toBe(true);
      panel.toggle();
      expect(panel.visible()).toBe(false);
    });

    it('init 전에 show/hide를 호출해도 에러가 발생하지 않는다', () => {
      // Re-create without init
      window.NB = {};
      const loggerCode = fs.readFileSync(
        path.resolve(__dirname, '../../notebook_lr/static/js/agent-logger.js'),
        'utf-8'
      );
      new Function(loggerCode)();
      document.body.innerHTML = '';
      const panelCode = fs.readFileSync(
        path.resolve(__dirname, '../../notebook_lr/static/js/debug-panel.js'),
        'utf-8'
      );
      new Function(panelCode)();

      expect(() => window.NB.debugPanel.show()).not.toThrow();
      expect(() => window.NB.debugPanel.hide()).not.toThrow();
      expect(() => window.NB.debugPanel.toggle()).not.toThrow();
    });
  });

  describe('onClear (clear 버튼)', () => {
    it('agentLogger.clear()를 호출하고 UI를 초기화한다', () => {
      logger.logStart(logger.EventType.API_CALL);
      expect(logger.getEvents()).toHaveLength(1);

      const clearBtn = document.getElementById('debug-clear-btn');
      clearBtn.click();

      expect(logger.getEvents()).toHaveLength(0);
    });

    it('debug-btn의 has-errors 클래스를 제거한다', () => {
      const debugBtn = document.getElementById('debug-btn');
      debugBtn.classList.add('has-errors');

      const clearBtn = document.getElementById('debug-clear-btn');
      clearBtn.click();

      expect(debugBtn.classList.contains('has-errors')).toBe(false);
    });
  });

  describe('onPauseToggle (pause 버튼)', () => {
    it('Pause/Resume 상태를 토글한다', () => {
      const pauseBtn = document.getElementById('debug-pause-btn');

      pauseBtn.click();
      expect(pauseBtn.textContent).toBe('Resume');

      pauseBtn.click();
      expect(pauseBtn.textContent).toBe('Pause');
    });

    it('일시정지 중에는 새 이벤트가 렌더링되지 않는다', () => {
      panel.show();
      const pauseBtn = document.getElementById('debug-pause-btn');
      pauseBtn.click(); // pause

      const renderSpy = jest.spyOn(document.getElementById('debug-content').querySelector('.debug-tree'), 'appendChild');

      logger.logStart(logger.EventType.API_CALL);
      // When paused, onLoggerEvent returns early, so no render call
      // We verify by checking that the tree wasn't updated
      // (render would modify innerHTML)
      expect(renderSpy).not.toHaveBeenCalled();
      renderSpy.mockRestore();
    });
  });

  describe('matchesFilter (필터링)', () => {
    it('type 필터가 일치하는 이벤트를 통과시킨다', () => {
      panel.show();

      logger.logStart(logger.EventType.API_CALL, { n: 1 });
      logger.logStart(logger.EventType.AI_CALL, { n: 2 });

      const filterType = document.getElementById('debug-filter-type');
      // Add option and select it
      const option = document.createElement('option');
      option.value = 'api_call';
      option.textContent = 'API Call';
      filterType.appendChild(option);
      filterType.value = 'api_call';
      filterType.dispatchEvent(new Event('change'));

      const tree = document.getElementById('debug-content').querySelector('.debug-tree');
      const nodes = tree.querySelectorAll('.debug-node');
      // Should only show api_call events
      expect(nodes.length).toBe(1);
    });
  });

  describe('이벤트 렌더링', () => {
    it('이벤트가 없으면 빈 메시지를 표시한다', () => {
      panel.show();
      const tree = document.getElementById('debug-content').querySelector('.debug-tree');
      expect(tree.innerHTML).toContain('No events');
    });

    it('이벤트가 있으면 노드를 렌더링한다', () => {
      panel.show();
      logger.logStart(logger.EventType.API_CALL, { url: '/test' });

      // Trigger re-render via show
      panel.show();

      const tree = document.getElementById('debug-content').querySelector('.debug-tree');
      const nodes = tree.querySelectorAll('.debug-node');
      expect(nodes.length).toBeGreaterThan(0);
    });

    it('부모-자식 관계가 트리 구조로 렌더링된다', () => {
      panel.show();
      const parentId = logger.logStart(logger.EventType.COMMENT_ADD, { userComment: 'test' });
      logger.logStart(logger.EventType.AI_CALL, { provider: 'openai' }, parentId);

      panel.show();

      const tree = document.getElementById('debug-content').querySelector('.debug-tree');
      const children = tree.querySelectorAll('.debug-children');
      expect(children.length).toBeGreaterThan(0);
    });

    it('에러/타임아웃 이벤트 발생 시 debug-btn에 has-errors 클래스를 추가한다', () => {
      const debugBtn = document.getElementById('debug-btn');
      expect(debugBtn.classList.contains('has-errors')).toBe(false);

      const id = logger.logStart(logger.EventType.AI_CALL);
      logger.logError(id, new Error('fail'));

      expect(debugBtn.classList.contains('has-errors')).toBe(true);
    });
  });

  describe('통계 업데이트', () => {
    it('이벤트 추가 시 통계 UI가 업데이트된다', () => {
      const id1 = logger.logStart(logger.EventType.API_CALL);
      logger.logComplete(id1);
      const id2 = logger.logStart(logger.EventType.AI_CALL);
      logger.logError(id2, new Error('fail'));

      const totalEl = document.getElementById('debug-stat-total');
      const errorsEl = document.getElementById('debug-stat-errors');
      expect(totalEl.textContent).toBe('2');
      expect(errorsEl.textContent).toBe('1');
    });
  });

  describe('이벤트 선택 및 상세 보기', () => {
    it('이벤트 클릭 시 상세 패널이 표시된다', () => {
      panel.show();
      logger.logStart(logger.EventType.API_CALL, { url: '/test' });
      panel.show(); // re-render

      const header = document.querySelector('.debug-node-header');
      expect(header).toBeTruthy();
      header.click();
      const detail = document.querySelector('.debug-detail');
      expect(detail).toBeTruthy();
    });
  });

  describe('close 버튼', () => {
    it('close 버튼 클릭 시 패널이 닫힌다', () => {
      panel.show();
      expect(panel.visible()).toBe(true);

      const closeBtn = document.getElementById('close-debug-btn');
      closeBtn.click();
      expect(panel.visible()).toBe(false);
    });
  });
});
