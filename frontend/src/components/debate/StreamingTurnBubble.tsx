'use client';

import type { StreamingTurn } from '@/stores/debateStore';

type Props = {
  turn: StreamingTurn;
  agentAName: string;
  agentBName: string;
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

export function StreamingTurnBubble({ turn, agentAName, agentBName }: Props) {
  const isAgentA = turn.speaker === 'agent_a';
  const name = isAgentA ? agentAName : agentBName;
  const partialClaim = extractPartialClaim(turn.raw);

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
          <span className="text-xs font-bold text-text">{name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium animate-pulse">
            생성 중...
          </span>
          <span className="text-[10px] text-text-muted">Turn {turn.turn_number}</span>
        </div>

        {/* 스트리밍 텍스트 또는 대기 점 */}
        {partialClaim ? (
          <p className="text-sm text-text whitespace-pre-wrap">
            {partialClaim}
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
