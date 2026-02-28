import { create } from 'zustand';
import { api } from '@/lib/api';

type AgentSummary = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  image_url?: string | null;
};

type DebateTopic = {
  id: string;
  title: string;
  description: string | null;
  mode: string;
  status: string;
  max_turns: number;
  turn_token_limit: number;
  scheduled_start_at: string | null;
  scheduled_end_at: string | null;
  is_admin_topic: boolean;
  tools_enabled: boolean;
  queue_count: number;
  match_count: number;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  creator_nickname: string | null;
  is_password_protected?: boolean;
};

type DebateMatch = {
  id: string;
  topic_id: string;
  topic_title: string;
  agent_a: AgentSummary;
  agent_b: AgentSummary;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'waiting_agent' | 'forfeit';
  winner_id: string | null;
  score_a: number;
  score_b: number;
  penalty_a: number;
  penalty_b: number;
  turn_count?: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  elo_a_before?: number | null;
  elo_b_before?: number | null;
  elo_a_after?: number | null;
  elo_b_after?: number | null;
};

type TurnLog = {
  id: string;
  turn_number: number;
  speaker: string;
  agent_id: string;
  action: string;
  claim: string;
  evidence: string | null;
  tool_used: string | null;
  tool_result: string | null;
  penalties: Record<string, number> | null;
  penalty_total: number;
  human_suspicion_score: number;
  response_time_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  review_result: {
    logic_score: number;
    violations: { type: string; severity: string; detail: string }[];
    feedback: string;
    blocked: boolean;
    skipped?: boolean;
  } | null;
  is_blocked: boolean;
  created_at: string;
};

type TurnReview = {
  turn_number: number;
  speaker: string;
  logic_score: number | null;
  violations: { type: string; severity: string; detail: string }[];
  feedback: string;
  blocked: boolean;
  skipped?: boolean;
};

type StreamingTurn = {
  turn_number: number;
  speaker: string;
  raw: string;
};

type RankingEntry = {
  id: string;
  name: string;
  owner_nickname: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  image_url?: string | null;
  tier?: string;
  is_profile_public?: boolean;
};

type TopicCreatePayload = {
  title: string;
  description?: string | null;
  mode?: string;
  max_turns?: number;
  turn_token_limit?: number;
  tools_enabled?: boolean;
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
  password?: string | null;
};

type DebateState = {
  topics: DebateTopic[];
  topicsTotal: number;
  popularTopics: DebateTopic[];
  popularTopicsTotal: number;
  currentMatch: DebateMatch | null;
  turns: TurnLog[];
  streamingTurn: StreamingTurn | null;
  turnReviews: TurnReview[];
  ranking: RankingEntry[];
  loading: boolean;
  streaming: boolean;
  fetchTopics: (params?: { status?: string; sort?: string; page?: number; pageSize?: number }) => Promise<void>;
  fetchPopularTopics: () => Promise<void>;
  fetchMatch: (matchId: string) => Promise<void>;
  fetchTurns: (matchId: string) => Promise<void>;
  fetchRanking: () => Promise<void>;
  createTopic: (payload: TopicCreatePayload) => Promise<DebateTopic>;
  updateTopic: (topicId: string, payload: Partial<TopicCreatePayload>) => Promise<DebateTopic>;
  deleteTopic: (topicId: string) => Promise<void>;
  joinQueue: (topicId: string, agentId: string, password?: string) => Promise<{ status: string; match_id?: string; opponent_agent_id?: string }>;
  randomMatch: (agentId: string) => Promise<{ topic_id: string; status: string; opponent_agent_id?: string }>;
  leaveQueue: (topicId: string, agentId: string) => Promise<void>;
  addTurnFromSSE: (turn: TurnLog) => void;
  appendChunk: (turn_number: number, speaker: string, chunk: string) => void;
  clearStreamingTurn: () => void;
  setStreaming: (v: boolean) => void;
  addTurnReview: (review: TurnReview) => void;
};

export const useDebateStore = create<DebateState>((set) => ({
  topics: [],
  topicsTotal: 0,
  popularTopics: [],
  popularTopicsTotal: 0,
  currentMatch: null,
  turns: [],
  streamingTurn: null,
  turnReviews: [],
  ranking: [],
  loading: false,
  streaming: false,
  fetchTopics: async (params?: { status?: string; sort?: string; page?: number; pageSize?: number }) => {
    set({ loading: true });
    try {
      const { status, sort, page = 1, pageSize = 20 } = params ?? {};
      const queryParams = new URLSearchParams();
      if (status) queryParams.set('status', status);
      if (sort) queryParams.set('sort', sort);
      queryParams.set('page', String(page));
      queryParams.set('page_size', String(pageSize));
      const data = await api.get<{ items: DebateTopic[]; total: number }>(`/topics?${queryParams}`);
      set({ topics: data.items, topicsTotal: data.total });
    } catch (err) {
      console.error('Failed to fetch topics:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchPopularTopics: async () => {
    set({ loading: true });
    try {
      const data = await api.get<{ items: DebateTopic[]; total: number }>(
        '/topics?sort=popular_week&page_size=10',
      );
      set({ popularTopics: data.items, popularTopicsTotal: data.total });
    } catch (err) {
      console.error('Failed to fetch popular topics:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchMatch: async (matchId) => {
    // 새 매치 로드 전 이전 턴 초기화 — 같은 상대와의 이전 매치 내용이 잔류하지 않도록
    set({ loading: true, turns: [], streamingTurn: null, turnReviews: [] });
    try {
      const data = await api.get<DebateMatch>(`/matches/${matchId}`);
      set({ currentMatch: data });
    } catch (err) {
      console.error('Failed to fetch match:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchTurns: async (matchId) => {
    try {
      const data = await api.get<TurnLog[]>(`/matches/${matchId}/turns`);
      set({ turns: data });
    } catch (err) {
      console.error('Failed to fetch turns:', err);
    }
  },
  fetchRanking: async () => {
    set({ loading: true });
    try {
      const data = await api.get<RankingEntry[]>('/agents/ranking');
      set({ ranking: data });
    } catch (err) {
      console.error('Failed to fetch ranking:', err);
    } finally {
      set({ loading: false });
    }
  },
  createTopic: async (payload) => {
    const data = await api.post<DebateTopic>('/topics', payload);
    set((s) => ({ topics: [data, ...s.topics], topicsTotal: s.topicsTotal + 1 }));
    return data;
  },
  updateTopic: async (topicId, payload) => {
    const data = await api.patch<DebateTopic>(`/topics/${topicId}`, payload);
    set((s) => ({
      topics: s.topics.map((t) => (t.id === topicId ? data : t)),
      popularTopics: s.popularTopics.map((t) => (t.id === topicId ? data : t)),
    }));
    return data;
  },
  deleteTopic: async (topicId) => {
    await api.delete(`/topics/${topicId}`);
    set((s) => ({
      topics: s.topics.filter((t) => t.id !== topicId),
      topicsTotal: s.topicsTotal - 1,
      popularTopics: s.popularTopics.filter((t) => t.id !== topicId),
      popularTopicsTotal: Math.max(0, s.popularTopicsTotal - 1),
    }));
  },
  joinQueue: async (topicId, agentId, password?) => {
    return api.post<{ status: string; match_id?: string; opponent_agent_id?: string }>(
      `/topics/${topicId}/join`,
      { agent_id: agentId, ...(password ? { password } : {}) },
    );
  },
  randomMatch: async (agentId) => {
    return api.post<{ topic_id: string; status: string; opponent_agent_id?: string }>(
      '/topics/random-match',
      { agent_id: agentId },
    );
  },
  leaveQueue: async (topicId, agentId) => {
    await api.delete(`/topics/${topicId}/queue?agent_id=${agentId}`);
  },
  addTurnFromSSE: (turn) => {
    set((s) => {
      const exists = s.turns.some(
        (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
      );
      if (exists) {
        return {
          turns: s.turns.map((t) =>
            t.turn_number === turn.turn_number && t.speaker === turn.speaker ? turn : t,
          ),
          streamingTurn: null,
        };
      }
      return { turns: [...s.turns, turn], streamingTurn: null };
    });
  },
  addTurnReview: (review) => {
    set((s) => {
      const exists = s.turnReviews.some(
        (r) => r.turn_number === review.turn_number && r.speaker === review.speaker,
      );
      if (exists) {
        return {
          turnReviews: s.turnReviews.map((r) =>
            r.turn_number === review.turn_number && r.speaker === review.speaker ? review : r,
          ),
        };
      }
      return { turnReviews: [...s.turnReviews, review] };
    });
  },
  appendChunk: (turn_number, speaker, chunk) => {
    set((s) => {
      if (s.streamingTurn && s.streamingTurn.turn_number === turn_number && s.streamingTurn.speaker === speaker) {
        return { streamingTurn: { ...s.streamingTurn, raw: s.streamingTurn.raw + chunk } };
      }
      return { streamingTurn: { turn_number, speaker, raw: chunk } };
    });
  },
  clearStreamingTurn: () => set({ streamingTurn: null }),
  setStreaming: (v) => set({ streaming: v }),
}));

export type { DebateTopic, DebateMatch, TurnLog, TurnReview, StreamingTurn, RankingEntry, AgentSummary, TopicCreatePayload };
