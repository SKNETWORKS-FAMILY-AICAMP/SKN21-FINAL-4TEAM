'use client';

import Link from 'next/link';

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'text-green-400',
  anthropic: 'text-orange-400',
  google: 'text-blue-400',
  runpod: 'text-purple-400',
  local: 'text-gray-400',
};

type Props = {
  agentId: string;
  agentName: string;
  provider: string;
  hp: number; // 0-100
  side: 'left' | 'right';
  isWinner?: boolean;
};

function hpBarColor(hp: number, side: 'left' | 'right'): string {
  if (hp <= 20) return 'bg-red-500';
  if (hp <= 45) return 'bg-yellow-500';
  return side === 'left' ? 'bg-blue-500' : 'bg-orange-500';
}

export function FightingHPBar({ agentId, agentName, provider, hp, side, isWinner = false }: Props) {
  const clamped = Math.max(0, Math.min(100, Math.round(hp)));
  const color = hpBarColor(clamped, side);
  const isCritical = clamped <= 20;
  const providerColor = PROVIDER_COLORS[provider] ?? 'text-gray-400';

  return (
    <div className={`flex-1 min-w-0 flex flex-col gap-1.5 ${side === 'right' ? 'items-end' : 'items-start'}`}>
      {/* 에이전트 정보 */}
      <div className={`flex items-center gap-2 ${side === 'right' ? 'flex-row-reverse' : ''}`}>
        <div
          className={`w-10 h-10 rounded-xl bg-gray-800 border-2 shrink-0
            flex items-center justify-center text-xl
            ${side === 'left' ? 'border-blue-500/40' : 'border-orange-500/40'}`}
        >
          🤖
        </div>
        <div className={`min-w-0 ${side === 'right' ? 'text-right' : ''}`}>
          <div className={`flex items-center gap-1 min-w-0 ${side === 'right' ? 'flex-row-reverse' : ''}`}>
            <Link
              href={`/debate/agents/${agentId}`}
              className={`text-sm font-bold truncate max-w-[110px] no-underline hover:underline
                ${side === 'left' ? 'text-blue-400 hover:text-blue-300' : 'text-orange-400 hover:text-orange-300'}`}
            >
              {agentName}
            </Link>
            {isWinner && <span className="text-base shrink-0 leading-none">👑</span>}
          </div>
          <p className={`text-[11px] ${providerColor}`}>{provider}</p>
        </div>
      </div>

      {/* HP 게이지 */}
      <div className={`flex items-center gap-2 w-full ${side === 'right' ? 'flex-row-reverse' : ''}`}>
        <span
          className={`text-xs font-mono font-bold w-7 tabular-nums shrink-0 text-center
            ${isCritical ? 'text-red-400 animate-pulse' : 'text-gray-200'}`}
        >
          {clamped}
        </span>
        <div className="flex-1 h-4 bg-gray-900 rounded border border-gray-700 overflow-hidden">
          {side === 'left' ? (
            <div
              className={`h-full ${color} transition-all duration-700 ease-out ${isCritical ? 'animate-pulse' : ''}`}
              style={{ width: `${clamped}%` }}
            />
          ) : (
            // 우측 바는 오른쪽에서 채워지도록 (중앙 → 바깥으로 줄어듦)
            <div className="h-full flex justify-end">
              <div
                className={`h-full ${color} transition-all duration-700 ease-out ${isCritical ? 'animate-pulse' : ''}`}
                style={{ width: `${clamped}%` }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
