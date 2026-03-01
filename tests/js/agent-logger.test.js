const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadAgentLogger() {
  window.NB = {};
  const code = fs.readFileSync(
    path.resolve(__dirname, '../../notebook_lr/static/js/agent-logger.js'),
    'utf-8'
  );
  new Function(code)();
  return window.NB.agentLogger;
}

describe('agent-logger', () => {
  let logger;

  beforeEach(() => {
    logger = loadAgentLogger();
  });

  describe('logStart', () => {
    it('이벤트를 생성하고 ID를 반환한다', () => {
      const id = logger.logStart(logger.EventType.API_CALL, { url: '/test' });
      expect(id).toBeTruthy();
      expect(id).toMatch(/^evt_/);
    });

    it('생성된 이벤트가 events 배열에 추가된다', () => {
      logger.logStart(logger.EventType.API_CALL);
      const events = logger.getEvents();
      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('api_call');
      expect(events[0].status).toBe('pending');
    });

    it('data를 이벤트에 포함한다', () => {
      const id = logger.logStart(logger.EventType.AI_CALL, { provider: 'openai' });
      const event = logger.findEvent(id);
      expect(event.data.provider).toBe('openai');
    });

    it('parentId 지정 시 부모의 children에 연결한다', () => {
      const parentId = logger.logStart(logger.EventType.API_CALL);
      const childId = logger.logStart(logger.EventType.AI_CALL, {}, parentId);

      const parent = logger.findEvent(parentId);
      const child = logger.findEvent(childId);

      expect(parent.children).toContain(childId);
      expect(child.parentId).toBe(parentId);
    });

    it('존재하지 않는 parentId를 지정해도 에러가 발생하지 않는다', () => {
      const id = logger.logStart(logger.EventType.API_CALL, {}, 'nonexistent');
      expect(id).toBeTruthy();
      const event = logger.findEvent(id);
      expect(event.parentId).toBe('nonexistent');
    });

    it('isEnabled=false이면 null을 반환한다', () => {
      logger.setEnabled(false);
      const id = logger.logStart(logger.EventType.API_CALL);
      expect(id).toBeNull();
      expect(logger.getEvents()).toHaveLength(0);
    });

    it('MAX_EVENTS(1000) 초과 시 오래된 이벤트를 제거한다', () => {
      for (let i = 0; i < 1005; i++) {
        logger.logStart(logger.EventType.API_CALL, { index: i });
      }
      const events = logger.getEvents();
      expect(events.length).toBeLessThanOrEqual(1000);
    });
  });

  describe('logComplete', () => {
    it('이벤트 상태를 success로 변경하고 duration을 계산한다', () => {
      const id = logger.logStart(logger.EventType.API_CALL);
      logger.logComplete(id, logger.EventStatus.SUCCESS, { result: 'ok' });

      const event = logger.findEvent(id);
      expect(event.status).toBe('success');
      expect(event.duration).toBeGreaterThanOrEqual(0);
      expect(event.data.result).toBe('ok');
    });

    it('존재하지 않는 eventId에 대해 에러 없이 무시한다', () => {
      expect(() => logger.logComplete('nonexistent')).not.toThrow();
    });

    it('isEnabled=false이면 무시한다', () => {
      const id = logger.logStart(logger.EventType.API_CALL);
      logger.setEnabled(false);
      logger.logComplete(id, logger.EventStatus.SUCCESS);
      // setEnabled(false) after logStart means logComplete is skipped
      const event = logger.findEvent(id);
      expect(event.status).toBe('pending');
    });
  });

  describe('logError', () => {
    it('에러 정보를 기록하고 status를 ERROR로 변경한다', () => {
      const id = logger.logStart(logger.EventType.AI_CALL);
      const error = new TypeError('Network failure');
      logger.logError(id, error, { retryCount: 3 });

      const event = logger.findEvent(id);
      expect(event.status).toBe('error');
      expect(event.data.error).toBe('Network failure');
      expect(event.data.errorType).toBe('TypeError');
      expect(event.data.retryCount).toBe(3);
      expect(event.duration).toBeGreaterThanOrEqual(0);
    });

    it('문자열 에러도 처리한다', () => {
      const id = logger.logStart(logger.EventType.AI_CALL);
      logger.logError(id, 'simple error');

      const event = logger.findEvent(id);
      expect(event.data.error).toBe('simple error');
    });

    it('존재하지 않는 eventId에 대해 에러 없이 무시한다', () => {
      expect(() => logger.logError('nonexistent', new Error('test'))).not.toThrow();
    });
  });

  describe('logTimeout', () => {
    it('timeout 정보를 기록하고 status를 TIMEOUT으로 변경한다', () => {
      const id = logger.logStart(logger.EventType.AI_CALL);
      logger.logTimeout(id, 5000);

      const event = logger.findEvent(id);
      expect(event.status).toBe('timeout');
      expect(event.duration).toBe(5000);
      expect(event.data.error).toContain('5000ms');
      expect(event.data.errorType).toBe('TimeoutError');
    });

    it('존재하지 않는 eventId에 대해 에러 없이 무시한다', () => {
      expect(() => logger.logTimeout('nonexistent', 5000)).not.toThrow();
    });
  });

  describe('getEvents (필터링)', () => {
    beforeEach(() => {
      logger.logStart(logger.EventType.API_CALL, { n: 1 });
      logger.logStart(logger.EventType.AI_CALL, { n: 2 });
      const id3 = logger.logStart(logger.EventType.API_CALL, { n: 3 });
      logger.logComplete(id3);
    });

    it('필터 없이 전체 이벤트를 반환한다', () => {
      expect(logger.getEvents()).toHaveLength(3);
    });

    it('type으로 필터링한다', () => {
      const apiEvents = logger.getEvents({ type: 'api_call' });
      expect(apiEvents).toHaveLength(2);
      apiEvents.forEach(e => expect(e.type).toBe('api_call'));
    });

    it('status로 필터링한다', () => {
      const successEvents = logger.getEvents({ status: 'success' });
      expect(successEvents).toHaveLength(1);
    });

    it('since로 시간 기준 필터링한다', () => {
      const futureTime = Date.now() + 10000;
      const events = logger.getEvents({ since: futureTime });
      expect(events).toHaveLength(0);
    });

    it('parentId로 필터링한다', () => {
      const rootEvents = logger.getEvents({ parentId: null });
      expect(rootEvents).toHaveLength(3);
    });
  });

  describe('getRootEvents / getChildren', () => {
    it('루트 이벤트만 반환한다', () => {
      const parentId = logger.logStart(logger.EventType.API_CALL);
      logger.logStart(logger.EventType.AI_CALL, {}, parentId);
      logger.logStart(logger.EventType.API_CALL);

      const roots = logger.getRootEvents();
      expect(roots).toHaveLength(2);
      roots.forEach(e => expect(e.parentId).toBeNull());
    });

    it('특정 이벤트의 자식들을 반환한다', () => {
      const parentId = logger.logStart(logger.EventType.API_CALL);
      logger.logStart(logger.EventType.AI_CALL, {}, parentId);
      logger.logStart(logger.EventType.AI_RESPONSE, {}, parentId);

      const children = logger.getChildren(parentId);
      expect(children).toHaveLength(2);
      children.forEach(c => expect(c.parentId).toBe(parentId));
    });

    it('자식이 없는 이벤트는 빈 배열을 반환한다', () => {
      const id = logger.logStart(logger.EventType.API_CALL);
      expect(logger.getChildren(id)).toHaveLength(0);
    });
  });

  describe('clear', () => {
    it('모든 이벤트를 삭제한다', () => {
      logger.logStart(logger.EventType.API_CALL);
      logger.logStart(logger.EventType.AI_CALL);
      logger.clear();
      expect(logger.getEvents()).toHaveLength(0);
    });
  });

  describe('setEnabled', () => {
    it('비활성화 후 활성화하면 다시 로깅한다', () => {
      logger.setEnabled(false);
      logger.logStart(logger.EventType.API_CALL);
      expect(logger.getEvents()).toHaveLength(0);

      logger.setEnabled(true);
      logger.logStart(logger.EventType.API_CALL);
      expect(logger.getEvents()).toHaveLength(1);
    });
  });

  describe('subscribe', () => {
    it('이벤트 발생 시 콜백을 호출한다', () => {
      const callback = jest.fn();
      logger.subscribe(callback);

      const id = logger.logStart(logger.EventType.API_CALL);
      expect(callback).toHaveBeenCalledWith('add', expect.objectContaining({ id }));

      logger.logComplete(id);
      expect(callback).toHaveBeenCalledWith('complete', expect.objectContaining({ id }));
    });

    it('에러/타임아웃 이벤트도 콜백을 호출한다', () => {
      const callback = jest.fn();
      logger.subscribe(callback);

      const id1 = logger.logStart(logger.EventType.AI_CALL);
      logger.logError(id1, new Error('fail'));
      expect(callback).toHaveBeenCalledWith('error', expect.objectContaining({ id: id1 }));

      const id2 = logger.logStart(logger.EventType.AI_CALL);
      logger.logTimeout(id2, 3000);
      expect(callback).toHaveBeenCalledWith('timeout', expect.objectContaining({ id: id2 }));
    });

    it('clear 이벤트도 콜백을 호출한다', () => {
      const callback = jest.fn();
      logger.subscribe(callback);
      logger.clear();
      expect(callback).toHaveBeenCalledWith('clear', null);
    });

    it('unsubscribe 함수를 반환하고 호출 시 구독을 해제한다', () => {
      const callback = jest.fn();
      const unsubscribe = logger.subscribe(callback);

      logger.logStart(logger.EventType.API_CALL);
      expect(callback).toHaveBeenCalledTimes(1);

      unsubscribe();
      logger.logStart(logger.EventType.API_CALL);
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('리스너 에러가 다른 리스너에 영향을 주지 않는다', () => {
      const errorCallback = jest.fn(() => { throw new Error('listener error'); });
      const normalCallback = jest.fn();

      logger.subscribe(errorCallback);
      logger.subscribe(normalCallback);

      logger.logStart(logger.EventType.API_CALL);
      expect(errorCallback).toHaveBeenCalledTimes(1);
      expect(normalCallback).toHaveBeenCalledTimes(1);
    });
  });

  describe('getStats', () => {
    it('빈 상태에서 기본 통계를 반환한다', () => {
      const stats = logger.getStats();
      expect(stats.total).toBe(0);
      expect(stats.errors).toBe(0);
      expect(stats.timeouts).toBe(0);
      expect(stats.avgDuration).toBe(0);
    });

    it('이벤트별 타입/상태 통계를 정확히 계산한다', () => {
      const id1 = logger.logStart(logger.EventType.API_CALL);
      logger.logComplete(id1);
      const id2 = logger.logStart(logger.EventType.AI_CALL);
      logger.logError(id2, new Error('fail'));
      const id3 = logger.logStart(logger.EventType.AI_CALL);
      logger.logTimeout(id3, 5000);

      const stats = logger.getStats();
      expect(stats.total).toBe(3);
      expect(stats.byType['api_call']).toBe(1);
      expect(stats.byType['ai_call']).toBe(2);
      expect(stats.byStatus['success']).toBe(1);
      expect(stats.byStatus['error']).toBe(1);
      expect(stats.byStatus['timeout']).toBe(1);
      expect(stats.errors).toBe(1);
      expect(stats.timeouts).toBe(1);
      expect(stats.avgDuration).toBeGreaterThanOrEqual(0);
    });
  });

  describe('findEvent', () => {
    it('존재하는 이벤트를 찾는다', () => {
      const id = logger.logStart(logger.EventType.API_CALL);
      const event = logger.findEvent(id);
      expect(event).toBeTruthy();
      expect(event.id).toBe(id);
    });

    it('존재하지 않는 이벤트는 undefined를 반환한다', () => {
      expect(logger.findEvent('nonexistent')).toBeUndefined();
    });
  });

  describe('EventType / EventStatus 상수', () => {
    it('EventType 상수가 정의되어 있다', () => {
      expect(logger.EventType.AI_CALL).toBe('ai_call');
      expect(logger.EventType.AI_RESPONSE).toBe('ai_response');
      expect(logger.EventType.AI_ERROR).toBe('ai_error');
      expect(logger.EventType.API_CALL).toBe('api_call');
      expect(logger.EventType.API_RESPONSE).toBe('api_response');
      expect(logger.EventType.API_ERROR).toBe('api_error');
      expect(logger.EventType.COMMENT_ADD).toBe('comment_add');
      expect(logger.EventType.COMMENT_COMPLETE).toBe('comment_complete');
      expect(logger.EventType.FILE_CHANGE_DETECTED).toBe('file_change_detected');
      expect(logger.EventType.FILE_AUTO_RELOAD).toBe('file_auto_reload');
      expect(logger.EventType.FILE_CONFLICT).toBe('file_conflict');
      expect(logger.EventType.FILE_CONFLICT_RESOLVED).toBe('file_conflict_resolved');
      expect(logger.EventType.FILE_POLL_ERROR).toBe('file_poll_error');
    });

    it('EventStatus 상수가 정의되어 있다', () => {
      expect(logger.EventStatus.PENDING).toBe('pending');
      expect(logger.EventStatus.SUCCESS).toBe('success');
      expect(logger.EventStatus.ERROR).toBe('error');
      expect(logger.EventStatus.TIMEOUT).toBe('timeout');
    });
  });
});
