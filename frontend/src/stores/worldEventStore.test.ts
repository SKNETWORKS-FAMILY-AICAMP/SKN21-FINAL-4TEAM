import { describe, it, expect, beforeEach } from 'vitest';
import { useWorldEventStore } from './worldEventStore';

const mockEvent = (id: string, overrides = {}) => ({
  id,
  created_by: 'admin-1',
  title: `이벤트 ${id}`,
  content: `이벤트 ${id} 내용`,
  event_type: 'world_state',
  priority: 0,
  is_active: true,
  starts_at: null,
  expires_at: null,
  age_rating: 'all',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

describe('useWorldEventStore', () => {
  beforeEach(() => {
    useWorldEventStore.setState({
      events: [],
      activeEvents: [],
      total: 0,
      loading: false,
    });
  });

  it('should start with empty events', () => {
    const state = useWorldEventStore.getState();
    expect(state.events).toEqual([]);
    expect(state.activeEvents).toEqual([]);
    expect(state.total).toBe(0);
  });

  it('should start with loading false', () => {
    expect(useWorldEventStore.getState().loading).toBe(false);
  });

  it('should set events list', () => {
    const events = [mockEvent('1'), mockEvent('2')];
    useWorldEventStore.setState({ events, total: 2 });
    expect(useWorldEventStore.getState().events).toHaveLength(2);
    expect(useWorldEventStore.getState().total).toBe(2);
  });

  it('should set active events', () => {
    const active = [mockEvent('1'), mockEvent('3', { event_type: 'crisis' })];
    useWorldEventStore.setState({ activeEvents: active });
    expect(useWorldEventStore.getState().activeEvents).toHaveLength(2);
    expect(useWorldEventStore.getState().activeEvents[1].event_type).toBe('crisis');
  });

  it('should prepend new event on create', () => {
    useWorldEventStore.setState({ events: [mockEvent('1')], total: 1 });

    const newEvent = mockEvent('2', { title: '새 이벤트' });
    useWorldEventStore.setState((s) => ({
      events: [newEvent, ...s.events],
      total: s.total + 1,
    }));

    expect(useWorldEventStore.getState().events).toHaveLength(2);
    expect(useWorldEventStore.getState().events[0].title).toBe('새 이벤트');
    expect(useWorldEventStore.getState().total).toBe(2);
  });

  it('should update event in list', () => {
    useWorldEventStore.setState({ events: [mockEvent('1'), mockEvent('2')], total: 2 });

    const updated = mockEvent('1', { title: '수정된 이벤트', is_active: false });
    useWorldEventStore.setState((s) => ({
      events: s.events.map((e) => (e.id === '1' ? updated : e)),
    }));

    expect(useWorldEventStore.getState().events[0].title).toBe('수정된 이벤트');
    expect(useWorldEventStore.getState().events[0].is_active).toBe(false);
    expect(useWorldEventStore.getState().events[1].title).toBe('이벤트 2');
  });

  it('should remove event from list', () => {
    useWorldEventStore.setState({ events: [mockEvent('1'), mockEvent('2'), mockEvent('3')], total: 3 });

    useWorldEventStore.setState((s) => ({
      events: s.events.filter((e) => e.id !== '2'),
      total: s.total - 1,
    }));

    expect(useWorldEventStore.getState().events).toHaveLength(2);
    expect(useWorldEventStore.getState().total).toBe(2);
    expect(useWorldEventStore.getState().events.find((e) => e.id === '2')).toBeUndefined();
  });

  it('should support different event types', () => {
    const events = [
      mockEvent('1', { event_type: 'world_state' }),
      mockEvent('2', { event_type: 'seasonal' }),
      mockEvent('3', { event_type: 'crisis' }),
      mockEvent('4', { event_type: 'lore_update' }),
    ];
    useWorldEventStore.setState({ events, total: 4 });
    expect(useWorldEventStore.getState().events.map((e) => e.event_type)).toEqual([
      'world_state', 'seasonal', 'crisis', 'lore_update',
    ]);
  });
});
