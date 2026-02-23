import { describe, it, expect, beforeEach } from 'vitest';
import { usePendingPostStore } from './pendingPostStore';

const mockPending = (id: string, status = 'pending') => ({
  id,
  persona_id: 'p1',
  persona_display_name: '캐릭터',
  content_type: 'post' as const,
  title: '테스트 제목',
  content: 'AI가 생성한 내용',
  target_post_id: null,
  target_comment_id: null,
  status,
  input_tokens: 100,
  output_tokens: 50,
  cost: 0.0002,
  created_at: '2026-01-01T00:00:00Z',
  reviewed_at: null,
});

describe('usePendingPostStore', () => {
  beforeEach(() => {
    usePendingPostStore.setState({
      items: [],
      total: 0,
      loading: false,
    });
  });

  it('should start with empty items', () => {
    expect(usePendingPostStore.getState().items).toEqual([]);
    expect(usePendingPostStore.getState().total).toBe(0);
  });

  it('should start with loading false', () => {
    expect(usePendingPostStore.getState().loading).toBe(false);
  });

  it('should set pending items', () => {
    const items = [mockPending('1'), mockPending('2')];
    usePendingPostStore.setState({ items, total: 2 });
    expect(usePendingPostStore.getState().items).toHaveLength(2);
    expect(usePendingPostStore.getState().total).toBe(2);
  });

  it('should remove item on approve (optimistic update)', () => {
    const items = [mockPending('1'), mockPending('2'), mockPending('3')];
    usePendingPostStore.setState({ items, total: 3 });

    // approve 후 상태 업데이트 시뮬레이션
    usePendingPostStore.setState((s) => ({
      items: s.items.filter((p) => p.id !== '2'),
      total: s.total - 1,
    }));

    expect(usePendingPostStore.getState().items).toHaveLength(2);
    expect(usePendingPostStore.getState().total).toBe(2);
    expect(usePendingPostStore.getState().items.find((p) => p.id === '2')).toBeUndefined();
  });

  it('should remove item on reject (optimistic update)', () => {
    const items = [mockPending('1'), mockPending('2')];
    usePendingPostStore.setState({ items, total: 2 });

    usePendingPostStore.setState((s) => ({
      items: s.items.filter((p) => p.id !== '1'),
      total: s.total - 1,
    }));

    expect(usePendingPostStore.getState().items).toHaveLength(1);
    expect(usePendingPostStore.getState().items[0].id).toBe('2');
  });

  it('should handle different content types', () => {
    const post = mockPending('1');
    const comment = { ...mockPending('2'), content_type: 'comment', target_post_id: 'post-1' };
    usePendingPostStore.setState({ items: [post, comment], total: 2 });

    expect(usePendingPostStore.getState().items[0].content_type).toBe('post');
    expect(usePendingPostStore.getState().items[1].content_type).toBe('comment');
  });

  it('should handle loading state', () => {
    usePendingPostStore.setState({ loading: true });
    expect(usePendingPostStore.getState().loading).toBe(true);
    usePendingPostStore.setState({ loading: false });
    expect(usePendingPostStore.getState().loading).toBe(false);
  });
});
