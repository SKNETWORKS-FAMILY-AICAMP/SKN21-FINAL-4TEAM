import { create } from 'zustand';
import { api } from '@/lib/api';

type PostAuthor = {
  type: 'user' | 'persona';
  id: string;
  display_name: string;
};

type Post = {
  id: string;
  board_id: string;
  title: string | null;
  content: string;
  author: PostAuthor;
  age_rating: string;
  is_ai_generated: boolean;
  reaction_count: number;
  comment_count: number;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
  my_reaction: string | null;
};

type Comment = {
  id: string;
  post_id: string;
  parent_id: string | null;
  author: PostAuthor;
  content: string;
  is_ai_generated: boolean;
  reaction_count: number;
  created_at: string;
  my_reaction: string | null;
  children: Comment[];
};

type Board = {
  id: string;
  board_key: string;
  display_name: string;
  description: string | null;
  age_rating: string;
  is_active: boolean;
};

type FeedResponse = {
  items: Post[];
  total: number;
};

type CommunityState = {
  boards: Board[];
  currentFeed: FeedResponse | null;
  loading: boolean;
  fetchBoards: () => Promise<void>;
  fetchFeed: (boardId: string, sort?: string, skip?: number) => Promise<void>;
};

export const useCommunityStore = create<CommunityState>((set) => ({
  boards: [],
  currentFeed: null,
  loading: false,
  fetchBoards: async () => {
    try {
      const data = await api.get<Board[]>('/board/boards');
      set({ boards: data });
    } catch (err) {
      console.error('Community action failed:', err);
    }
  },
  fetchFeed: async (boardId: string, sort = 'latest', skip = 0) => {
    set({ loading: true });
    try {
      const data = await api.get<FeedResponse>(
        `/board/${boardId}/posts?sort=${sort}&skip=${skip}&limit=20`,
      );
      set({ currentFeed: data });
    } catch (err) {
      console.error('Community action failed:', err);
    } finally {
      set({ loading: false });
    }
  },
}));

export type { Post, Comment, Board, PostAuthor };
