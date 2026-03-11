'use client';

import { useEffect, useRef, useState } from 'react';
import { useDebateStore } from '@/stores/debateStore';
import type { TurnLog, TurnReview, PromotionSeries } from '@/stores/debateStore';

type UseDebateStreamOptions = {
  onSeriesUpdate?: (series: PromotionSeries) => void;
};

type UseDebateStreamResult = {
  connected: boolean;
  error: string | null;
};

/**
 * SSE 연결을 생성하고 이벤트 타입별 스토어 액션을 호출한다.
 * in_progress 상태인 매치에만 연결하며, 언마운트 시 AbortController로 연결을 취소한다.
 */
export function useDebateStream(
  matchId: string | null,
  matchStatus: string | undefined,
  { onSeriesUpdate }: UseDebateStreamOptions = {},
): UseDebateStreamResult {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // props 콜백은 ref로 관리 — 변경 시 SSE 재연결 방지
  const onSeriesUpdateRef = useRef(onSeriesUpdate);
  onSeriesUpdateRef.current = onSeriesUpdate;

  useEffect(() => {
    if (!matchId || matchStatus !== 'in_progress') return;

    // Zustand 액션은 getState()로 직접 접근 — 의존성 배열에서 제외해 불필요한 재연결 방지
    // 의존성이 많을수록 onSeriesUpdate 같은 prop 변경 시 의도치 않은 재연결 위험 증가
    const store = useDebateStore.getState();
    store.fetchTurns(matchId);
    store.fetchPredictionStats(matchId);

    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const controller = new AbortController();
    store.setStreaming(true);
    setConnected(true);
    setError(null);

    (async () => {
      // finished/error 이벤트를 받았으면 true — 루프 종료 후 중복 fetchMatch 방지
      let finished = false;

      // 네트워크 단절 시 최대 2회 재연결 (총 3회 시도)
      for (let attempt = 0; attempt < 3; attempt++) {
        if (controller.signal.aborted) break;
        try {
          const response = await fetch(`/api/matches/${matchId}/stream`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            signal: controller.signal,
          });

          const reader = response.body?.getReader();
          if (!reader) break;

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
                // 이벤트 처리 시점마다 getState() — 동기 Zustand 업데이트가 바로 반영됨
                const s = useDebateStore.getState();
                if (event.event === 'turn_chunk') {
                  const { turn_number, speaker, chunk } = event.data as {
                    turn_number: number;
                    speaker: string;
                    chunk: string;
                  };
                  s.appendChunk(turn_number, speaker, chunk);
                } else if (event.event === 'turn') {
                  s.addTurnFromSSE(event.data as TurnLog);
                } else if (event.event === 'turn_review') {
                  s.addTurnReview(event.data as TurnReview);
                } else if (event.event === 'series_update') {
                  onSeriesUpdateRef.current?.(event.data as PromotionSeries);
                } else if (event.event === 'finished' || event.event === 'error') {
                  finished = true;
                  s.clearStreamingTurn();
                  // 결과창 즉시 표시 — fetchMatch 후에도 debateShowAll이 리셋되지 않도록 먼저 설정
                  s.setDebateShowAll(true);
                  // 매치 상태를 서버에서 재조회해 최종 점수/상태 반영
                  s.fetchMatch(matchId);
                }
              } catch {
                // skip parse errors
              }
            }
          }

          // 스트림 정상 종료 — finished 이벤트를 받았으면 재연결 불필요
          if (finished) break;
        } catch {
          if (controller.signal.aborted) break;
          // 네트워크 오류 — 마지막 시도가 아니면 2초 후 재연결
          if (attempt < 2) await new Promise((r) => setTimeout(r, 2000));
          else setError('SSE 연결 실패');
        }
      }

      const s = useDebateStore.getState();
      s.clearStreamingTurn();
      s.setStreaming(false);
      setConnected(false);
      s.setDebateShowAll(true);
      if (!finished) s.fetchMatch(matchId);
    })();

    return () => {
      controller.abort();
    };
  }, [matchId, matchStatus]); // Zustand 액션은 getState()로 접근해 의존성 제외

  return { connected, error };
}
