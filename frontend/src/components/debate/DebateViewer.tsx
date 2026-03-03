'use client';

import { useEffect, useRef, useState } from 'react';
import { Play } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import type { DebateMatch, TurnLog, TurnReview } from '@/stores/debateStore';
import { TurnBubble } from './TurnBubble';
import { StreamingTurnBubble } from './StreamingTurnBubble';
import { ReplayControls } from './ReplayControls';
import { LiveBadge } from './LiveBadge';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { ScrollToTop } from '@/components/ui/ScrollToTop';
import { api } from '@/lib/api';

type Props = {
  match: DebateMatch;
};

export function DebateViewer({ match }: Props) {
  // 슬라이스별 구독 — appendChunk로 streamingTurn이 바뀔 때 turns는 재렌더링하지 않음
  const turns = useDebateStore((s) => s.turns);
  const streamingTurn = useDebateStore((s) => s.streamingTurn);
  const turnReviews = useDebateStore((s) => s.turnReviews);
  const streaming = useDebateStore((s) => s.streaming);
  const replayMode = useDebateStore((s) => s.replayMode);
  const replayIndex = useDebateStore((s) => s.replayIndex);
  const startReplay = useDebateStore((s) => s.startReplay);
  const fetchTurns = useDebateStore((s) => s.fetchTurns);
  const fetchMatch = useDebateStore((s) => s.fetchMatch);
  const addTurnFromSSE = useDebateStore((s) => s.addTurnFromSSE);
  const appendChunk = useDebateStore((s) => s.appendChunk);
  const clearStreamingTurn = useDebateStore((s) => s.clearStreamingTurn);
  const setStreaming = useDebateStore((s) => s.setStreaming);
  const addTurnReview = useDebateStore((s) => s.addTurnReview);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // 관전자 수 (in_progress 매치만)
  const [viewerCount, setViewerCount] = useState(0);

  useEffect(() => {
    fetchTurns(match.id);
  }, [match.id, fetchTurns]);

  // 관전자 수 폴링 (in_progress 매치, 30초 간격)
  useEffect(() => {
    if (match.status !== 'in_progress') return;
    const fetchViewers = async () => {
      try {
        const data = await api.get<{ count: number }>(`/matches/${match.id}/viewers`);
        setViewerCount(data.count);
      } catch {
        /* ignore */
      }
    };
    fetchViewers();
    const interval = setInterval(fetchViewers, 30000);
    return () => clearInterval(interval);
  }, [match.id, match.status]);

  // 바닥 감지: window 레벨 스크롤
  useEffect(() => {
    const handleScroll = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      isNearBottomRef.current = maxScroll <= 0 || window.scrollY >= maxScroll - 100;
    };
    window.addEventListener('scroll', handleScroll);
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // SSE 실시간 스트리밍 (in_progress 매치)
  useEffect(() => {
    if (match.status !== 'in_progress') return;

    // SSE 연결 시점에 기존 턴 재조회 — pending → in_progress 전환 중 생성된 턴을 보정
    fetchTurns(match.id);

    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const controller = new AbortController();
    setStreaming(true);

    (async () => {
      try {
        const response = await fetch(`/api/matches/${match.id}/stream`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        });

        const reader = response.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;
            const payload = trimmed.slice(6);
            try {
              const event = JSON.parse(payload);
              if (event.event === 'turn_chunk') {
                const { turn_number, speaker, chunk } = event.data as {
                  turn_number: number;
                  speaker: string;
                  chunk: string;
                };
                appendChunk(turn_number, speaker, chunk);
              } else if (event.event === 'turn') {
                addTurnFromSSE(event.data as TurnLog);
              } else if (event.event === 'turn_review') {
                addTurnReview(event.data as TurnReview);
              } else if (event.event === 'finished' || event.event === 'error') {
                clearStreamingTurn();
                // 매치 상태를 서버에서 재조회해 최종 점수/상태 반영
                fetchMatch(match.id);
              }
            } catch {
              // skip parse errors
            }
          }
        }
      } catch {
        // aborted or error
      } finally {
        clearStreamingTurn();
        setStreaming(false);
      }
    })();

    return () => controller.abort();
  }, [match.id, match.status, addTurnFromSSE, appendChunk, clearStreamingTurn, fetchMatch, fetchTurns, setStreaming, addTurnReview]);

  // 스마트 자동 스크롤: 완료 턴이 추가될 때만 (스트리밍 청크는 스크롤 안 함)
  useEffect(() => {
    if (isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [turns.length]);

  // 리플레이 모드일 때 표시할 턴 슬라이스
  const visibleTurns = replayMode ? turns.slice(0, replayIndex + 1) : turns;

  return (
    <div className="flex flex-col gap-3">
      {/* 관전자 수 배지 (in_progress) */}
      {match.status === 'in_progress' && viewerCount > 0 && (
        <div className="flex justify-end">
          <LiveBadge count={viewerCount} />
        </div>
      )}

      {/* 완료된 매치 — 리플레이 시작 버튼 (replayMode 아닐 때만 표시) */}
      {match.status === 'completed' && !replayMode && turns.length > 0 && (
        <div className="flex justify-center mb-2">
          <button
            type="button"
            onClick={() => {
              window.scrollTo({ top: 0, behavior: 'smooth' });
              startReplay();
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 text-sm font-semibold transition-colors"
          >
            <Play size={14} />
            리플레이 시작
          </button>
        </div>
      )}

      {/* 리플레이 컨트롤 */}
      <ReplayControls />

      {match.status === 'waiting_agent' && (
        <div className="text-center py-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 text-yellow-600 text-sm">
            <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
            로컬 에이전트 접속 대기 중...
          </div>
        </div>
      )}

      {match.status === 'forfeit' && (
        <div className="text-center py-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 text-red-600 text-sm font-semibold">
            에이전트 미접속 — 몰수패
          </div>
        </div>
      )}

      {turns.length === 0 && !streamingTurn && match.status === 'in_progress' && (
        <div className="flex flex-col gap-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {visibleTurns.map((turn, idx) => {
        const review =
          turnReviews.find(
            (r) => r.turn_number === turn.turn_number && r.speaker === turn.speaker,
          ) ??
          turn.review_result ??
          null;
        // 리플레이 모드에서 마지막 턴에 fade 효과 적용
        const isLast = replayMode && idx === visibleTurns.length - 1;
        return (
          <div
            key={turn.id || `${turn.turn_number}-${turn.speaker}`}
            className={isLast ? 'animate-pulse' : undefined}
          >
            <TurnBubble
              turn={turn}
              agentAName={match.agent_a.name}
              agentBName={match.agent_b.name}
              agentAImageUrl={match.agent_a.image_url}
              agentBImageUrl={match.agent_b.image_url}
              review={review}
            />
          </div>
        );
      })}

      {streamingTurn && (
        <StreamingTurnBubble
          turn={streamingTurn}
          agentAName={match.agent_a.name}
          agentBName={match.agent_b.name}
          agentAImageUrl={match.agent_a.image_url}
          agentBImageUrl={match.agent_b.image_url}
        />
      )}

      {streaming && !streamingTurn && (
        <div className="text-center text-xs text-primary animate-pulse py-2">
          토론 진행 중...
        </div>
      )}

      <div ref={bottomRef} />
      <ScrollToTop />
    </div>
  );
}
