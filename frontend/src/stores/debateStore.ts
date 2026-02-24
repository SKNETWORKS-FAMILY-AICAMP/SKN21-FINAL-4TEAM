import { create } from 'zustand';
import { api } from '@/lib/api';

type AgentSummary = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
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
  created_at: string;
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
};

type DebateState = {
  topics: DebateTopic[];
  topicsTotal: number;
  currentMatch: DebateMatch | null;
  turns: TurnLog[];
  ranking: RankingEntry[];
  loading: boolean;
  streaming: boolean;
  fetchTopics: (status?: string) => Promise<void>;
  fetchMatch: (matchId: string) => Promise<void>;
  fetchTurns: (matchId: string) => Promise<void>;
  fetchRanking: () => Promise<void>;
  createTopic: (payload: TopicCreatePayload) => Promise<DebateTopic>;
  joinQueue: (topicId: string, agentId: string) => Promise<{ status: string; match_id?: string }>;
  leaveQueue: (topicId: string, agentId: string) => Promise<void>;
  addTurnFromSSE: (turn: TurnLog) => void;
  setStreaming: (v: boolean) => void;
};

export const useDebateStore = create<DebateState>((set) => ({
  topics: [],
  topicsTotal: 0,
  currentMatch: null,
  turns: [],
  ranking: [],
  loading: false,
  streaming: false,
  fetchTopics: async (status?: string) => {
    set({ loading: true });
    try {
      const params = status ? `?status=${status}` : '';
      const data = await api.get<{ items: DebateTopic[]; total: number }>(`/topics${params}`);
      set({ topics: data.items, topicsTotal: data.total });
    } catch (err) {
      console.error('Failed to fetch topics:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchMatch: async (matchId) => {
    set({ loading: true });
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
  joinQueue: async (topicId, agentId) => {
    return api.post<{ status: string; match_id?: string }>(`/topics/${topicId}/join`, {
      agent_id: agentId,
    });
  },
  leaveQueue: async (topicId, agentId) => {
    await api.delete(`/topics/${topicId}/queue?agent_id=${agentId}`);
  },
  addTurnFromSSE: (turn) => {
    set((s) => ({ turns: [...s.turns, turn] }));
  },
  setStreaming: (v) => set({ streaming: v }),
}));

export type { DebateTopic, DebateMatch, TurnLog, RankingEntry, AgentSummary, TopicCreatePayload };
