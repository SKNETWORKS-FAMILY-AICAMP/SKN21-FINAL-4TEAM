'use client';

import { useEffect, useRef } from 'react';
import { useDebateStore } from '@/stores/debateStore';
import type { DebateMatch, TurnLog } from '@/stores/debateStore';
import { TurnBubble } from './TurnBubble';
import { SkeletonCard } from '@/components/ui/Skeleton';

type Props = {
  match: DebateMatch;
};

export function DebateViewer({ match }: Props) {
  const { turns, streaming, fetchTurns, addTurnFromSSE, setStreaming } = useDebateStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchTurns(match.id);
  }, [match.id, fetchTurns]);

  // SSE 실시간 스트리밍 (in_progress 매치)
  useEffect(() => {
    if (match.status !== 'in_progress') return;

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
              if (event.event === 'turn') {
                addTurnFromSSE(event.data as TurnLog);
              }
            } catch {
              // skip parse errors
            }
          }
        }
      } catch {
        // aborted or error
      } finally {
        setStreaming(false);
      }
    })();

    return () => controller.abort();
  }, [match.id, match.status, addTurnFromSSE, setStreaming]);

  // 자동 스크롤
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns.length]);

  return (
    <div className="flex flex-col gap-3">
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

      {turns.length === 0 && match.status === 'in_progress' && (
        <div className="flex flex-col gap-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {turns.map((turn) => (
        <TurnBubble
          key={turn.id || `${turn.turn_number}-${turn.speaker}`}
          turn={turn}
          agentAName={match.agent_a.name}
          agentBName={match.agent_b.name}
        />
      ))}

      {streaming && (
        <div className="text-center text-xs text-primary animate-pulse py-2">
          토론 진행 중...
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
