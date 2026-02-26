'use client';

import { useEffect, useRef, useState } from 'react';
import type { StreamingTurn } from '@/stores/debateStore';

// 타이핑 속도: 6글자 / 30ms ≈ 200자/sec — 너무 빠르지 않게 읽기 편한 속도
const CHARS_PER_TICK = 6;
const TICK_MS = 30;

type Props = {
  turn: StreamingTurn;
  agentAName: string;
  agentBName: string;
  agentAImageUrl?: string | null;
  agentBImageUrl?: string | null;
};

/**
 * 부분 JSON에서 "claim" 필드 텍스트를 추출.
 * LLM이 {"action":"...", "claim": "여기 내용..."} 형식으로 출력하므로
 * claim이 시작된 이후 텍스트만 표시해 자연스러운 타이핑 효과를 제공한다.
 */
function extractPartialClaim(raw: string): string {
  const match = raw.match(/"claim"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)/s);
  if (!match) return '';
  return match[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\');
}

export function StreamingTurnBubble({ turn, agentAName, agentBName, agentAImageUrl, agentBImageUrl }: Props) {
  const isAgentA = turn.speaker === 'agent_a';
  const name = isAgentA ? agentAName : agentBName;
  const imageUrl = isAgentA ? agentAImageUrl : agentBImageUrl;

  // 전체 claim 텍스트 (SSE 수신 기준)
  const fullClaim = extractPartialClaim(turn.raw);
  // 타이핑 효과로 표시할 텍스트
  const [displayedClaim, setDisplayedClaim] = useState('');
  // 최신 fullClaim을 interval 내부에서 참조하기 위한 ref
  const targetRef = useRef(fullClaim);
  targetRef.current = fullClaim;

  // 턴이 바뀌면 표시 텍스트 초기화
  useEffect(() => {
    setDisplayedClaim('');
  }, [turn.turn_number, turn.speaker]);

  // 고정 interval로 타이핑 효과 구현
  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayedClaim((prev) => {
        const target = targetRef.current;
        if (prev.length >= target.length) return prev;
        return target.slice(0, prev.length + CHARS_PER_TICK);
      });
    }, TICK_MS);
    return () => clearInterval(interval);
  }, []); // 컴포넌트 생애주기 동안 한 번만 등록

  return (
    <div className={`flex ${isAgentA ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[82%] rounded-xl p-3 ${
          isAgentA
            ? 'bg-bg-surface border border-border rounded-tl-none'
            : 'bg-primary/5 border border-primary/20 rounded-tr-none'
        }`}
      >
        {/* 헤더 */}
        <div className="flex items-center gap-2 mb-1.5">
          {imageUrl && (
            <img
              src={imageUrl}
              alt={name}
              className="w-5 h-5 rounded-full object-cover flex-shrink-0"
            />
          )}
          <span className="text-xs font-bold text-text">{name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium animate-pulse">
            생성 중...
          </span>
          <span className="text-[10px] text-text-muted">Turn {turn.turn_number}</span>
        </div>

        {/* 타이핑 효과 텍스트 또는 대기 점 */}
        {displayedClaim ? (
          <p className="text-sm text-text whitespace-pre-wrap">
            {displayedClaim}
            <span className="inline-block w-0.5 h-3.5 bg-primary animate-pulse ml-0.5 align-middle" />
          </p>
        ) : (
          <div className="flex items-center gap-1 py-1">
            <span
              className="w-1.5 h-1.5 rounded-full bg-text-muted/60 animate-bounce"
              style={{ animationDelay: '0ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-text-muted/60 animate-bounce"
              style={{ animationDelay: '150ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-text-muted/60 animate-bounce"
              style={{ animationDelay: '300ms' }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
