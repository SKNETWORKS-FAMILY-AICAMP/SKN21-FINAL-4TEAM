'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { WaitingRoomVS } from '@/components/debate/WaitingRoomVS';
import { SkeletonCard } from '@/components/ui/Skeleton';
import type { DebateTopic } from '@/stores/debateStore';

type Agent = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
};

export default function WaitingRoomPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const agentId = searchParams.get('agent') ?? '';

  const [topic, setTopic] = useState<DebateTopic | null>(null);
  const [myAgent, setMyAgent] = useState<Agent | null>(null);
  const [opponent, setOpponent] = useState<Agent | null>(null);
  const [startedAt] = useState(() => new Date());
  const [isMatched, setIsMatched] = useState(false);
  const [isAutoMatched, setIsAutoMatched] = useState(false);
  const [isRevealing, setIsRevealing] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const matchIdRef = useRef<string | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  // 초기 데이터 로드
  useEffect(() => {
    if (!agentId) {
      router.push(`/debate/topics/${topicId}`);
      return;
    }

    Promise.all([
      api.get<DebateTopic>(`/topics/${topicId}`),
      api.get<Agent>(`/agents/${agentId}`),
    ])
      .then(([t, a]) => {
        setTopic(t);
        setMyAgent(a);
      })
      .catch(() => setError('데이터를 불러오지 못했습니다.'));
  }, [topicId, agentId, router]);

  // 이미 매칭됐는지 확인 후 SSE 연결
  useEffect(() => {
    if (!myAgent) return;

    api
      .get<{ status: string; match_id?: string }>(`/topics/${topicId}/queue/status?agent_id=${agentId}`)
      .then((res) => {
        if (res.status === 'matched' && res.match_id) {
          // 이미 매칭 완료 상태 — 바로 이동
          router.push(`/debate/matches/${res.match_id}`);
        } else if (res.status === 'not_in_queue') {
          // 큐에서 빠져나간 경우 토픽으로 복귀
          router.push(`/debate/topics/${topicId}`);
        } else {
          // queued — SSE 연결 시작
          connectSSE();
        }
      })
      .catch(() => connectSSE());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myAgent]);

  const connectSSE = useCallback(() => {
    // 기존 연결 정리
    if (sseRef.current) {
      sseRef.current.close();
    }

    const url = `/api/topics/${topicId}/queue/stream?agent_id=${agentId}`;
    const es = new EventSource(url, { withCredentials: true });
    sseRef.current = es;

    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        const { event, data } = parsed;

        if (event === 'matched') {
          handleMatched(data.match_id, data.opponent_agent_id, data.auto_matched ?? false);
        } else if (event === 'timeout') {
          setError('플랫폼 에이전트가 없어 자동 매칭에 실패했습니다. 나중에 다시 시도해 주세요.');
          es.close();
        } else if (event === 'cancelled') {
          router.push(`/debate/topics/${topicId}`);
        }
      } catch {
        // 하트비트 등 무시
      }
    };

    es.onerror = () => {
      es.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId, agentId]);

  const handleMatched = useCallback(
    async (matchId: string, opponentAgentId: string, autoMatched: boolean) => {
      matchIdRef.current = matchId;
      setIsAutoMatched(autoMatched);

      // 상대 에이전트 정보 조회
      try {
        const opp = await api.get<Agent>(`/agents/${opponentAgentId}`);
        setOpponent(opp);
      } catch {
        setOpponent({
          id: opponentAgentId,
          name: '상대 에이전트',
          provider: 'unknown',
          model_id: '',
          elo_rating: 1500,
          wins: 0,
          losses: 0,
          draws: 0,
        });
      }

      // 슬라이드인 → 매치 상태 전환 → 3초 후 이동
      setIsRevealing(true);
      setTimeout(() => setIsMatched(true), 300);
      setTimeout(() => {
        router.push(`/debate/matches/${matchId}`);
      }, 3000);
    },
    [router],
  );

  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try {
      await api.delete(`/topics/${topicId}/queue?agent_id=${agentId}`);
    } catch {
      // 이미 큐에서 제거됐을 수 있음
    } finally {
      router.push(`/debate/topics/${topicId}`);
    }
  }, [topicId, agentId, router]);

  // 언마운트 시 SSE 정리
  useEffect(() => {
    return () => {
      sseRef.current?.close();
    };
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center gap-4 px-4">
        <p className="text-red-400 text-sm text-center">{error}</p>
        <button
          onClick={() => router.push(`/debate/topics/${topicId}`)}
          className="px-4 py-2 rounded-lg border border-gray-600 text-sm text-gray-400
            hover:border-gray-400 transition-colors"
        >
          토픽으로 돌아가기
        </button>
      </div>
    );
  }

  if (!topic || !myAgent) return <SkeletonCard />;

  return (
    <WaitingRoomVS
      topicTitle={topic.title}
      myAgent={myAgent}
      opponent={opponent}
      startedAt={startedAt}
      isMatched={isMatched}
      isAutoMatched={isAutoMatched}
      isRevealing={isRevealing}
      onCancel={handleCancel}
      cancelling={cancelling}
    />
  );
}
