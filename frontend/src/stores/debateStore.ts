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

type PromotionSeries = {
  id: string;
  agent_id: string;
  series_type: 'promotion' | 'demotion';
  from_tier: string;
  to_tier: string;
  required_wins: number;
  current_wins: number;
  current_losses: number;
  status: 'active' | 'won' | 'lost' | 'cancelled';
  created_at: string;
  completed_at: string | null;
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
  match_type?: 'ranked' | 'promotion' | 'demotion';
  series_id?: string | null;
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
  // 최적화 모드에서 A 검토 중 B가 동시 스트리밍될 때 B 청크를 버퍼링
  pendingStreamingTurn: StreamingTurn | null;
  turnReviews: TurnReview[];
  ranking: RankingEntry[];
  featuredMatches: DebateMatch[];
  topicsLoading: boolean;
  matchLoading: boolean;
  rankingLoading: boolean;
  streaming: boolean;
  // 리플레이 상태
  replayMode: boolean;
  replayIndex: number;
  replaySpeed: number; // 0.5 | 1 | 2
  replayPlaying: boolean;
  replayTyping: boolean; // 타이핑 애니메이션 진행 중 여부 (true이면 tick 대기)
  // 완료된 매치 전체 보기 여부 — false: 턴 숨김(기본), true: 전체 표시
  // Scorecard/SummaryReport 노출 제어에도 사용
  debateShowAll: boolean;
  fetchTopics: (params?: { status?: string; sort?: string; page?: number; pageSize?: number }) => Promise<void>;
  fetchPopularTopics: () => Promise<void>;
  fetchMatch: (matchId: string) => Promise<void>;
  fetchTurns: (matchId: string) => Promise<void>;
  fetchRanking: (seasonId?: string) => Promise<void>;
  fetchFeatured: (limit?: number) => Promise<void>;
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
  // 리플레이 액션
  startReplay: () => void;
  stopReplay: () => void;
  setReplaySpeed: (speed: number) => void;
  tickReplay: () => void;
  setReplayTyping: (v: boolean) => void;
  setDebateShowAll: (v: boolean) => void;
};

export const useDebateStore = create<DebateState>((set, get) => ({
  topics: [],
  topicsTotal: 0,
  popularTopics: [],
  popularTopicsTotal: 0,
  currentMatch: null,
  turns: [],
  streamingTurn: null,
  pendingStreamingTurn: null,
  turnReviews: [],
  ranking: [],
  featuredMatches: [],
  topicsLoading: false,
  matchLoading: false,
  rankingLoading: false,
  streaming: false,
  replayMode: false,
  replayIndex: 0,
  replaySpeed: 1,
  replayPlaying: false,
  replayTyping: false,
  debateShowAll: false,
  fetchTopics: async (params?: { status?: string; sort?: string; page?: number; pageSize?: number }) => {
    set({ topicsLoading: true });
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
      set({ topicsLoading: false });
    }
  },
  fetchPopularTopics: async () => {
    set({ topicsLoading: true });
    try {
      const data = await api.get<{ items: DebateTopic[]; total: number }>(
        '/topics?sort=popular_week&page_size=10',
      );
      set({ popularTopics: data.items, popularTopicsTotal: data.total });
    } catch (err) {
      console.error('Failed to fetch popular topics:', err);
    } finally {
      set({ topicsLoading: false });
    }
  },
  fetchMatch: async (matchId) => {
    // 동일 매치 로딩 중 중복 호출 방지 (빠른 새로고침 시 DB 커넥션 풀 고갈 방지)
    if (get().matchLoading) return;
    // 새 매치 로드 시에만 상태 초기화 — 동일 매치 재조회(SSE finished, 폴링)는 기존 상태 유지
    // 동일 매치 리셋 시 debateShowAll이 false로 돌아가 completed 상태에서 결과창이 비워지는 버그 방지
    const isSameMatch = get().currentMatch?.id === matchId;
    set({
      matchLoading: true,
      ...(!isSameMatch && {
        turns: [],
        streamingTurn: null,
        pendingStreamingTurn: null,
        turnReviews: [],
        replayMode: false,
        replayPlaying: false,
        replayIndex: -1,
        replayTyping: false,
        debateShowAll: false,
      }),
    });
    try {
      const data = await api.get<DebateMatch>(`/matches/${matchId}`);
      set({ currentMatch: data });
    } catch (err) {
      console.error('Failed to fetch match:', err);
    } finally {
      set({ matchLoading: false });
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
  fetchRanking: async (seasonId?: string) => {
    set({ rankingLoading: true });
    try {
      const params = seasonId ? `?season_id=${seasonId}` : '';
      const data = await api.get<RankingEntry[]>(`/agents/ranking${params}`);
      set({ ranking: data });
    } catch (err) {
      console.error('Failed to fetch ranking:', err);
    } finally {
      set({ rankingLoading: false });
    }
  },
  fetchFeatured: async (limit = 5) => {
    try {
      const data = await api.get<{ items: DebateMatch[]; total: number }>(
        `/matches/featured?limit=${limit}`,
      );
      set({ featuredMatches: data.items });
    } catch (err) {
      console.error('Failed to fetch featured matches:', err);
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
      // 완료된 턴과 동일한 화자일 때만 streamingTurn 제거 — 다른 화자(병렬 스트리밍)는 유지
      const isCurrentStreaming =
        s.streamingTurn?.turn_number === turn.turn_number &&
        s.streamingTurn?.speaker === turn.speaker;
      const nextStreaming = isCurrentStreaming ? s.pendingStreamingTurn : s.streamingTurn;
      const nextPending = isCurrentStreaming ? null : s.pendingStreamingTurn;

      if (exists) {
        return {
          turns: s.turns.map((t) =>
            t.turn_number === turn.turn_number && t.speaker === turn.speaker ? turn : t,
          ),
          streamingTurn: nextStreaming,
          pendingStreamingTurn: nextPending,
        };
      }
      return {
        turns: [...s.turns, turn],
        streamingTurn: nextStreaming,
        pendingStreamingTurn: nextPending,
      };
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
      // 현재 스트리밍 중인 화자와 같은 턴이면 이어 붙이기
      if (s.streamingTurn?.turn_number === turn_number && s.streamingTurn?.speaker === speaker) {
        return { streamingTurn: { ...s.streamingTurn, raw: s.streamingTurn.raw + chunk } };
      }
      // 다른 화자의 chunk가 왔고 현재 streamingTurn이 활성 상태 — pending 버퍼에 쌓기
      if (s.streamingTurn) {
        if (s.pendingStreamingTurn?.turn_number === turn_number && s.pendingStreamingTurn?.speaker === speaker) {
          return { pendingStreamingTurn: { ...s.pendingStreamingTurn, raw: s.pendingStreamingTurn.raw + chunk } };
        }
        return { pendingStreamingTurn: { turn_number, speaker, raw: chunk } };
      }
      // streamingTurn 없음 — 바로 활성화
      return { streamingTurn: { turn_number, speaker, raw: chunk } };
    });
  },
  clearStreamingTurn: () => set({ streamingTurn: null, pendingStreamingTurn: null }),
  setStreaming: (v) => set({ streaming: v }),
  // replayIndex -1: 재생 시작 시 0턴도 아직 안 보임. 첫 tick에서 0으로 올라가 첫 턴 등장
  startReplay: () => set({ replayMode: true, replayIndex: -1, replayPlaying: true, replayTyping: false, debateShowAll: false }),
  stopReplay: () => set({ replayMode: false, replayPlaying: false, replayIndex: -1, replayTyping: false, debateShowAll: true }),
  setReplaySpeed: (speed) => set({ replaySpeed: speed }),
  tickReplay: () => {
    const { replayIndex, turns, replayTyping } = get();
    // 타이핑 애니메이션 진행 중이면 tick 건너뜀
    if (replayTyping) return;
    const maxIndex = turns.length - 1;
    if (replayIndex >= maxIndex) {
      set({ replayPlaying: false });
    } else {
      set({ replayIndex: replayIndex + 1 });
    }
  },
  setReplayTyping: (v) => set({ replayTyping: v }),
  setDebateShowAll: (v) => set({ debateShowAll: v }),
}));

export type { DebateTopic, DebateMatch, TurnLog, TurnReview, StreamingTurn, RankingEntry, AgentSummary, TopicCreatePayload, PromotionSeries };
export type { DebateState };
