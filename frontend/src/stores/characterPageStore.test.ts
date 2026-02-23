import { describe, it, expect, beforeEach } from 'vitest';
import { useCharacterPageStore } from './characterPageStore';

describe('useCharacterPageStore', () => {
  beforeEach(() => {
    useCharacterPageStore.setState({
      page: null,
      posts: [],
      postsTotal: 0,
      loading: false,
    });
  });

  it('should start with null page', () => {
    expect(useCharacterPageStore.getState().page).toBeNull();
  });

  it('should start with empty posts', () => {
    expect(useCharacterPageStore.getState().posts).toEqual([]);
    expect(useCharacterPageStore.getState().postsTotal).toBe(0);
  });

  it('should start with loading false', () => {
    expect(useCharacterPageStore.getState().loading).toBe(false);
  });

  it('should set page data via setState', () => {
    const mockPage = {
      id: 'p1',
      display_name: '테스트 캐릭터',
      description: '설명',
      greeting_message: null,
      age_rating: 'all',
      category: 'romance',
      tags: ['테스트'],
      background_image_url: null,
      live2d_model_id: null,
      creator_name: 'creator',
      stats: { post_count: 5, follower_count: 10, like_count: 3, chat_count: 2 },
      is_following: false,
      created_at: '2026-01-01T00:00:00Z',
    };
    useCharacterPageStore.setState({ page: mockPage });
    expect(useCharacterPageStore.getState().page?.display_name).toBe('테스트 캐릭터');
    expect(useCharacterPageStore.getState().page?.stats.follower_count).toBe(10);
  });

  it('should set posts data via setState', () => {
    const mockPosts = [
      {
        id: 'post1',
        board_id: 'b1',
        title: '제목',
        content: '내용',
        age_rating: 'all',
        is_ai_generated: true,
        reaction_count: 0,
        comment_count: 0,
        created_at: '2026-01-01T00:00:00Z',
      },
    ];
    useCharacterPageStore.setState({ posts: mockPosts, postsTotal: 1 });
    expect(useCharacterPageStore.getState().posts).toHaveLength(1);
    expect(useCharacterPageStore.getState().postsTotal).toBe(1);
  });

  it('should update follow status in page', () => {
    const mockPage = {
      id: 'p1',
      display_name: '캐릭터',
      description: null,
      greeting_message: null,
      age_rating: 'all',
      category: null,
      tags: null,
      background_image_url: null,
      live2d_model_id: null,
      creator_name: null,
      stats: { post_count: 0, follower_count: 0, like_count: 0, chat_count: 0 },
      is_following: false,
      created_at: '2026-01-01T00:00:00Z',
    };
    useCharacterPageStore.setState({ page: mockPage });

    // 팔로우 상태 수동 업데이트 시뮬레이션
    useCharacterPageStore.setState((s) => ({
      page: s.page ? { ...s.page, is_following: true, stats: { ...s.page.stats, follower_count: 1 } } : s.page,
    }));
    expect(useCharacterPageStore.getState().page?.is_following).toBe(true);
    expect(useCharacterPageStore.getState().page?.stats.follower_count).toBe(1);
  });

  it('should append posts for infinite scroll', () => {
    const first = [
      { id: '1', board_id: 'b', title: null, content: 'a', age_rating: 'all', is_ai_generated: true, reaction_count: 0, comment_count: 0, created_at: '' },
    ];
    const second = [
      { id: '2', board_id: 'b', title: null, content: 'b', age_rating: 'all', is_ai_generated: true, reaction_count: 0, comment_count: 0, created_at: '' },
    ];
    useCharacterPageStore.setState({ posts: first, postsTotal: 2 });
    useCharacterPageStore.setState((s) => ({ posts: [...s.posts, ...second] }));
    expect(useCharacterPageStore.getState().posts).toHaveLength(2);
    expect(useCharacterPageStore.getState().posts[1].id).toBe('2');
  });
});
