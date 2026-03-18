// debateStore.ts — 하위 호환성 유지를 위한 re-export 파사드
// 실제 구현은 아래 3개 스토어에 분산됨:
//   - debateTopicStore: 토픽 목록, 큐 관련
//   - debateMatchStore: 매치 관전, 스트리밍, 리플레이, 예측투표
//   - debateRankingStore: 랭킹, 하이라이트

export { useDebateTopicStore } from './debateTopicStore';
export type { DebateTopicState } from './debateTopicStore';

export { useDebateMatchStore } from './debateMatchStore';
export type { DebateMatchState } from './debateMatchStore';

export { useDebateRankingStore } from './debateRankingStore';
export type { DebateRankingState } from './debateRankingStore';

// 기존 코드에서 useDebateStore를 사용하는 경우를 위해
// 3개 스토어의 상태/액션을 합친 단일 Zustand 스토어를 유지
import { create } from 'zustand';
import { api } from '@/lib/api';
import type {
  DebateTopic,
  DebateMatch,
  TurnLog,
  TurnReview,
  StreamingTurn,
  PredictionStats,
  RankingEntry,
  TopicCreatePayload,
} from '@/types/debate';

type DebateState = {
  // ─── topic 상태 ────────────────────────────────────────────
  topics: DebateTopic[];
  topicsTotal: number;
  popularTopics: DebateTopic[];
  popularTopicsTotal: number;
  topicsLoading: boolean;
  // ─── match 상태 ────────────────────────────────────────────
  currentMatch: DebateMatch | null;
  turns: TurnLog[];
  streamingTurn: StreamingTurn | null;
  // 최적화 모드에서 A 검토 중 B가 동시 스트리밍될 때 B 청크를 버퍼링
  pendingStreamingTurn: StreamingTurn | null;
  // turn SSE 이벤트가 도착했지만 StreamingTurnBubble 타이핑이 아직 진행 중인 턴을 보관
  pendingTurnLogs: TurnLog[];
  turnReviews: TurnReview[];
  matchLoading: boolean;
  streaming: boolean;
  nextSpeaker: string | null; // A turn 완료 후 B 청크 대기 구간에서 표시할 다음 화자
  // 리플레이 상태
  replayMode: boolean;
  replayIndex: number;
  replaySpeed: number; // 0.5 | 1 | 2
  replayPlaying: boolean;
  replayTyping: boolean; // 타이핑 애니메이션 진행 중 여부 (true이면 tick 대기)
  // 완료된 매치 전체 보기 여부 — false: 턴 숨김(기본), true: 전체 표시
  // Scorecard/SummaryReport 노출 제어에도 사용
  debateShowAll: boolean;
  predictionStats: PredictionStats | null;
  predictionLoading: boolean;
  // SSE 특수 이벤트 상태
  waitingAgent: boolean;
  creditInsufficient: boolean;
  matchVoidReason: string | null;
  // ─── ranking 상태 ──────────────────────────────────────────
  ranking: RankingEntry[];
  rankingLoading: boolean;
  featuredMatches: DebateMatch[];
  // ─── topic 액션 ────────────────────────────────────────────
  fetchTopics: (params?: { status?: string; sort?: string; page?: number; pageSize?: number }) => Promise<void>;
  fetchPopularTopics: () => Promise<void>;
  createTopic: (payload: TopicCreatePayload) => Promise<DebateTopic>;
  updateTopic: (topicId: string, payload: Partial<TopicCreatePayload>) => Promise<DebateTopic>;
  deleteTopic: (topicId: string) => Promise<void>;
  joinQueue: (topicId: string, agentId: string, password?: string) => Promise<{ status: string; match_id?: string; opponent_agent_id?: string }>;
  leaveQueue: (topicId: string, agentId: string) => Promise<void>;
  randomMatch: (agentId: string) => Promise<{ topic_id: string; status: string; opponent_agent_id?: string }>;
  // ─── match 액션 ────────────────────────────────────────────
  fetchMatch: (matchId: string) => Promise<void>;
  fetchTurns: (matchId: string) => Promise<void>;
  addTurnFromSSE: (turn: TurnLog) => void;
  // StreamingTurnBubble 타이핑 완료 후 호출 — pendingTurnLogs에 있던 턴을 turns로 이동
  flushPendingTurn: (turn_number: number, speaker: string) => void;
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
  setWaitingAgent: (v: boolean) => void;
  setCreditInsufficient: (v: boolean) => void;
  setMatchVoidReason: (reason: string | null) => void;
  submitPrediction: (matchId: string, prediction: 'a_win' | 'b_win' | 'draw') => Promise<void>;
  fetchPredictionStats: (matchId: string) => Promise<void>;
  // ─── ranking 액션 ──────────────────────────────────────────
  fetchRanking: (seasonId?: string) => Promise<void>;
  fetchFeatured: (limit?: number) => Promise<void>;
};

export const useDebateStore = create<DebateState>((set, get) => ({
  // ─── topic 초기 상태 ────────────────────────────────────────
  topics: [],
  topicsTotal: 0,
  popularTopics: [],
  popularTopicsTotal: 0,
  topicsLoading: false,
  // ─── match 초기 상태 ────────────────────────────────────────
  currentMatch: null,
  turns: [],
  streamingTurn: null,
  pendingStreamingTurn: null,
  pendingTurnLogs: [],
  turnReviews: [],
  matchLoading: false,
  streaming: false,
  nextSpeaker: null,
  replayMode: false,
  replayIndex: 0,
  replaySpeed: 1,
  replayPlaying: false,
  replayTyping: false,
  debateShowAll: false,
  predictionStats: null,
  predictionLoading: false,
  waitingAgent: false,
  creditInsufficient: false,
  matchVoidReason: null,
  // ─── ranking 초기 상태 ──────────────────────────────────────
  ranking: [],
  rankingLoading: false,
  featuredMatches: [],
  // ─── topic 액션 구현 ────────────────────────────────────────
  fetchTopics: async (params?) => {
    set({ topicsLoading: true });
    try {
      const { status, sort, page = 1, pageSize = 20 } = params ?? {};
      const queryParams = new URLSearchParams();
      if (status) queryParams.set('status', status);
      if (sort) queryParams.set('sort', sort);
      queryParams.set('page', String(page));
      queryParams.set('page_size', String(pageSize));
      const data = await api.get<{ items: DebateTopic[]; total: number }>(`/topics?${queryParams}`);
      set((s) => ({
        topics: page > 1 ? [...s.topics, ...data.items] : data.items,
        topicsTotal: data.total,
      }));
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
  leaveQueue: async (topicId, agentId) => {
    await api.delete(`/topics/${topicId}/queue?agent_id=${agentId}`);
  },
  randomMatch: async (agentId) => {
    return api.post<{ topic_id: string; status: string; opponent_agent_id?: string }>(
      '/topics/random-match',
      { agent_id: agentId },
    );
  },
  // ─── match 액션 구현 ────────────────────────────────────────
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
        pendingTurnLogs: [],
        turnReviews: [],
        replayMode: false,
        replayPlaying: false,
        replayIndex: -1,
        replayTyping: false,
        debateShowAll: false,
        predictionStats: null,
        waitingAgent: false,
        creditInsufficient: false,
        matchVoidReason: null,
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
      // turn_number 오름차순, 동점 시 agent_a 먼저 (백엔드 ORDER BY 보완)
      const sorted = data.sort(
        (a, b) =>
          a.turn_number - b.turn_number ||
          (a.speaker === 'agent_a' ? -1 : 1) - (b.speaker === 'agent_a' ? -1 : 1),
      );
      set({ turns: sorted });
    } catch (err) {
      console.error('Failed to fetch turns:', err);
    }
  },
  addTurnFromSSE: (turn) => {
    set((s) => {
      // StreamingTurnBubble이 같은 (turn_number, speaker)를 타이핑 중이면
      // 타이핑이 끝날 때까지 turns에 추가하지 않고 pendingTurnLogs에 버퍼링
      const isCurrentStreaming =
        s.streamingTurn?.turn_number === turn.turn_number &&
        s.streamingTurn?.speaker === turn.speaker;

      if (isCurrentStreaming) {
        // findIndex: some() + map() 이중 순회 대신 단일 순회로 교체
        const pendingIdx = s.pendingTurnLogs.findIndex(
          (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
        );
        return {
          pendingTurnLogs:
            pendingIdx >= 0
              ? s.pendingTurnLogs.map((t, i) => (i === pendingIdx ? turn : t))
              : [...s.pendingTurnLogs, turn],
        };
      }

      // pendingStreamingTurn과 동일한 (turn_number, speaker) — A 타이핑 중 B turn 이벤트 도착
      // streamingTurn(A)이 아직 타이핑 중이므로 pendingTurnLogs에 버퍼링. flushPendingTurn(A) 시 승격.
      const isPendingStreaming =
        s.pendingStreamingTurn?.turn_number === turn.turn_number &&
        s.pendingStreamingTurn?.speaker === turn.speaker;

      if (isPendingStreaming) {
        const pendingIdx = s.pendingTurnLogs.findIndex(
          (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
        );
        return {
          pendingTurnLogs:
            pendingIdx >= 0
              ? s.pendingTurnLogs.map((t, i) => (i === pendingIdx ? turn : t))
              : [...s.pendingTurnLogs, turn],
        };
      }

      // 현재 스트리밍 중인 화자가 아닌 경우 — 즉시 turns에 추가 (pendingStreamingTurn 승격)
      const turnIdx = s.turns.findIndex(
        (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
      );
      return {
        turns:
          turnIdx >= 0
            ? s.turns.map((t, i) => (i === turnIdx ? turn : t))
            : [...s.turns, turn].sort(
                (a, b) =>
                  a.turn_number - b.turn_number ||
                  (a.speaker === 'agent_a' ? -1 : 1) - (b.speaker === 'agent_a' ? -1 : 1),
              ),
        streamingTurn: s.pendingStreamingTurn,
        pendingStreamingTurn: null,
        nextSpeaker: turn.speaker === 'agent_a' ? 'agent_b' : 'agent_a',
      };
    });
  },
  flushPendingTurn: (turn_number, speaker) => {
    set((s) => {
      const pendingIdx = s.pendingTurnLogs.findIndex(
        (t) => t.turn_number === turn_number && t.speaker === speaker,
      );
      if (pendingIdx < 0) {
        // pending이 없어도 streamingTurn/pendingStreamingTurn 승격은 수행
        const isCurrentStreaming =
          s.streamingTurn?.turn_number === turn_number && s.streamingTurn?.speaker === speaker;
        if (!isCurrentStreaming) return {};
        return {
          streamingTurn: s.pendingStreamingTurn,
          pendingStreamingTurn: null,
          nextSpeaker: speaker === 'agent_a' ? 'agent_b' : 'agent_a',
        };
      }

      const pending = s.pendingTurnLogs[pendingIdx];
      const remainingPendingLogs = s.pendingTurnLogs.filter((_, i) => i !== pendingIdx);
      const turnIdx = s.turns.findIndex(
        (t) => t.turn_number === turn_number && t.speaker === speaker,
      );
      const updatedTurns =
        turnIdx >= 0
          ? s.turns.map((t, i) => (i === turnIdx ? pending : t))
          : [...s.turns, pending];

      return {
        turns: updatedTurns,
        pendingTurnLogs: remainingPendingLogs,
        streamingTurn: s.pendingStreamingTurn,
        pendingStreamingTurn: null,
        nextSpeaker: speaker === 'agent_a' ? 'agent_b' : 'agent_a',
      };
    });
  },
  addTurnReview: (review) => {
    set((s) => {
      const idx = s.turnReviews.findIndex(
        (r) => r.turn_number === review.turn_number && r.speaker === review.speaker,
      );
      if (idx >= 0) {
        return { turnReviews: s.turnReviews.map((r, i) => (i === idx ? review : r)) };
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
        if (
          s.pendingStreamingTurn?.turn_number === turn_number &&
          s.pendingStreamingTurn?.speaker === speaker
        ) {
          return {
            pendingStreamingTurn: {
              ...s.pendingStreamingTurn,
              raw: s.pendingStreamingTurn.raw + chunk,
            },
          };
        }
        return { pendingStreamingTurn: { turn_number, speaker, raw: chunk } };
      }
      // streamingTurn 없음 — 바로 활성화
      return { streamingTurn: { turn_number, speaker, raw: chunk }, nextSpeaker: null };
    });
  },
  clearStreamingTurn: () =>
    set((s) => {
      // 대기 중인 pendingTurnLogs를 turns에 병합 — finished/error 이벤트 시 손실 방지
      const logsToFlush = s.pendingTurnLogs;
      if (logsToFlush.length === 0) {
        return { streamingTurn: null, pendingStreamingTurn: null, pendingTurnLogs: [], nextSpeaker: null };
      }
      // 기존 turns를 Map으로 인덱싱 — O(n²) some+map 중첩 대신 O(n) 단일 패스로 병합
      const turnMap = new Map(s.turns.map((t, i) => [`${t.turn_number}:${t.speaker}`, i]));
      const updatedTurns = [...s.turns];
      for (const pending of logsToFlush) {
        const key = `${pending.turn_number}:${pending.speaker}`;
        const idx = turnMap.get(key);
        if (idx !== undefined) {
          updatedTurns[idx] = pending;
        } else {
          updatedTurns.push(pending);
          turnMap.set(key, updatedTurns.length - 1);
        }
      }
      return {
        turns: updatedTurns,
        streamingTurn: null,
        pendingStreamingTurn: null,
        pendingTurnLogs: [],
        nextSpeaker: null,
      };
    }),
  setStreaming: (v) => set({ streaming: v }),
  // replayIndex -1: 재생 시작 시 0턴도 아직 안 보임. 첫 tick에서 0으로 올라가 첫 턴 등장
  startReplay: () =>
    set({ replayMode: true, replayIndex: -1, replayPlaying: true, replayTyping: false, debateShowAll: false }),
  stopReplay: () =>
    set({ replayMode: false, replayPlaying: false, replayIndex: -1, replayTyping: false, debateShowAll: true }),
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
  setWaitingAgent: (v) => set({ waitingAgent: v }),
  setCreditInsufficient: (v) => set({ creditInsufficient: v }),
  setMatchVoidReason: (reason) => set({ matchVoidReason: reason }),
  submitPrediction: async (matchId, prediction) => {
    await api.post(`/matches/${matchId}/predictions`, { prediction });
    // 제출 후 통계 갱신
    const stats = await api.get<PredictionStats>(`/matches/${matchId}/predictions`);
    set({ predictionStats: stats });
  },
  fetchPredictionStats: async (matchId) => {
    set({ predictionLoading: true });
    try {
      const stats = await api.get<PredictionStats>(`/matches/${matchId}/predictions`);
      set({ predictionStats: stats });
    } catch {
      // 로그인 안 된 경우 등 무시
    } finally {
      set({ predictionLoading: false });
    }
  },
  // ─── ranking 액션 구현 ──────────────────────────────────────
  fetchRanking: async (seasonId?) => {
    set({ rankingLoading: true });
    try {
      const params = seasonId ? `?season_id=${seasonId}` : '';
      const data = await api.get<{ items: RankingEntry[]; total: number }>(
        `/agents/ranking${params}`,
      );
      set({ ranking: data.items });
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
}));

// 타입 re-export (기존 import 경로 하위 호환성 유지)
export type {
  DebateTopic,
  DebateMatch,
  TurnLog,
  TurnReview,
  StreamingTurn,
  RankingEntry,
  AgentSummary,
  TopicCreatePayload,
  PromotionSeries,
  PredictionStats,
} from '@/types/debate';

export type { DebateState };
