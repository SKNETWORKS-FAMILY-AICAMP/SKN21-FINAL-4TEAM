'use client';

import { AlertTriangle, ShieldAlert } from 'lucide-react';
import type { TurnLog } from '@/stores/debateStore';

type Props = {
  turn: TurnLog;
  agentAName: string;
  agentBName: string;
};

const ACTION_STYLES: Record<string, string> = {
  argue: 'bg-blue-500/10 text-blue-500',
  rebut: 'bg-orange-500/10 text-orange-500',
  concede: 'bg-green-500/10 text-green-500',
  question: 'bg-purple-500/10 text-purple-500',
  summarize: 'bg-text-muted/10 text-text-muted',
};

export function TurnBubble({ turn, agentAName, agentBName }: Props) {
  const isAgentA = turn.speaker === 'agent_a';
  const name = isAgentA ? agentAName : agentBName;

  return (
    <div className={`flex ${isAgentA ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[80%] rounded-xl p-3 ${
          isAgentA
            ? 'bg-bg-surface border border-border rounded-tl-none'
            : 'bg-primary/5 border border-primary/20 rounded-tr-none'
        }`}
      >
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-bold text-text">{name}</span>
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
              ACTION_STYLES[turn.action] || ACTION_STYLES.argue
            }`}
          >
            {turn.action}
          </span>
          <span className="text-[10px] text-text-muted">Turn {turn.turn_number}</span>
        </div>

        <p className="text-sm text-text whitespace-pre-wrap">{turn.claim}</p>

        {turn.evidence && (
          <div className="mt-2 px-2.5 py-1.5 bg-bg rounded border border-border">
            <span className="text-[10px] text-text-muted font-semibold uppercase">Evidence</span>
            <p className="text-xs text-text-secondary mt-0.5">{turn.evidence}</p>
          </div>
        )}

        {turn.penalty_total > 0 && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-danger">
            <AlertTriangle size={12} />
            <span>-{turn.penalty_total} 벌점</span>
            {turn.penalties && (
              <span className="text-text-muted">
                ({Object.entries(turn.penalties).map(([k, v]) => `${k}: -${v}`).join(', ')})
              </span>
            )}
          </div>
        )}

        {turn.human_suspicion_score > 30 && (
          <div
            className={`mt-2 flex items-center gap-1.5 text-xs ${
              turn.human_suspicion_score > 60
                ? 'text-red-500'
                : 'text-yellow-500'
            }`}
          >
            <ShieldAlert size={12} />
            <span>
              {turn.human_suspicion_score > 60 ? '높은 의심' : '의심'}
              {' '}(점수: {turn.human_suspicion_score})
            </span>
          </div>
        )}

        <div className="mt-1.5 flex items-center gap-2 text-[10px] text-text-muted">
          <span>{turn.input_tokens + turn.output_tokens} tokens</span>
          {turn.response_time_ms != null && (
            <span>{(turn.response_time_ms / 1000).toFixed(1)}s</span>
          )}
        </div>
      </div>
    </div>
  );
}
