import { create } from 'zustand';
import { api } from '@/lib/api';

type CharacterPageStats = {
  post_count: number;
  follower_count: number;
  like_count: number;
  chat_count: number;
};

type CharacterPage = {
  id: string;
  display_name: string;
  description: string | null;
  greeting_message: string | null;
  age_rating: 'all' | '15+' | '18+';
  category: string | null;
  tags: string[] | null;
  background_image_url: string | null;
  live2d_model_id: string | null;
  creator_name: string | null;
  stats: CharacterPageStats;
  is_following: boolean;
  created_at: string;
};

type CharacterPost = {
  id: string;
  board_id: string;
  title: string | null;
  content: string;
  age_rating: string;
  is_ai_generated: boolean;
  reaction_count: number;
  comment_count: number;
  created_at: string;
};

type FollowResponse = {
  following: boolean;
  follower_count: number;
};

type CharacterPageState = {
  page: CharacterPage | null;
  posts: CharacterPost[];
  postsTotal: number;
  loading: boolean;
  fetchPage: (personaId: string) => Promise<void>;
  fetchPosts: (personaId: string, skip?: number) => Promise<void>;
  follow: (personaId: string) => Promise<void>;
  unfollow: (personaId: string) => Promise<void>;
};

export const useCharacterPageStore = create<CharacterPageState>((set, get) => ({
  page: null,
  posts: [],
  postsTotal: 0,
  loading: false,
  fetchPage: async (personaId: string) => {
    set({ loading: true });
    try {
      const data = await api.get<CharacterPage>(`/character-pages/${personaId}`);
      set({ page: data });
    } catch (err) {
      console.error('Failed to fetch character page:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchPosts: async (personaId: string, skip = 0) => {
    try {
      const data = await api.get<{ items: CharacterPost[]; total: number }>(
        `/character-pages/${personaId}/posts?skip=${skip}&limit=20`,
      );
      set((s) =>
        skip === 0
          ? { posts: data.items, postsTotal: data.total }
          : { posts: [...s.posts, ...data.items], postsTotal: data.total },
      );
    } catch (err) {
      console.error('Failed to fetch character posts:', err);
    }
  },
  follow: async (personaId: string) => {
    try {
      const data = await api.post<FollowResponse>(`/character-pages/${personaId}/follow`);
      set((s) => ({
        page: s.page
          ? { ...s.page, is_following: data.following, stats: { ...s.page.stats, follower_count: data.follower_count } }
          : s.page,
      }));
    } catch (err) {
      console.error('Follow failed:', err);
    }
  },
  unfollow: async (personaId: string) => {
    try {
      const data = await api.delete<FollowResponse>(`/character-pages/${personaId}/follow`);
      set((s) => ({
        page: s.page
          ? { ...s.page, is_following: data.following, stats: { ...s.page.stats, follower_count: data.follower_count } }
          : s.page,
      }));
    } catch (err) {
      console.error('Unfollow failed:', err);
    }
  },
}));

export type { CharacterPage, CharacterPost, CharacterPageStats };
