'use client';

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

type Props = {
  agent: Agent | null;
  side: 'left' | 'right';
  isRevealing?: boolean;
};

const PROVIDER_BADGE: Record<string, string> = {
  openai: 'bg-green-500/20 text-green-400',
  anthropic: 'bg-orange-500/20 text-orange-400',
  google: 'bg-blue-500/20 text-blue-400',
  runpod: 'bg-purple-500/20 text-purple-400',
  local: 'bg-gray-500/20 text-gray-400',
};

export function AgentProfilePanel({ agent, side, isRevealing = false }: Props) {
  const ringColor = side === 'left' ? 'ring-blue-500/30' : 'ring-orange-500/30';
  const alignClass = side === 'left' ? 'items-start text-left' : 'items-end text-right';

  if (agent === null) {
    return (
      <div className={`flex flex-col ${alignClass} gap-3 w-full max-w-[220px]`}>
        <div
          className={`w-full aspect-square max-w-[160px] rounded-2xl border-2 border-dashed border-gray-600
            ring-2 ${ringColor} flex items-center justify-center bg-gray-800/50`}
        >
          {/* 펄스 애니메이션 */}
          <div className="relative flex items-center justify-center">
            <span className="animate-ping absolute inline-flex h-12 w-12 rounded-full bg-gray-500 opacity-30" />
            <span className="text-4xl">?</span>
          </div>
        </div>
        <p className="text-sm text-gray-500 animate-pulse">상대를 찾는 중...</p>
      </div>
    );
  }

  const slideClass = isRevealing
    ? side === 'right'
      ? 'animate-slide-in'
      : 'animate-slide-in-left'
    : '';

  return (
    <div className={`flex flex-col ${alignClass} gap-3 w-full max-w-[220px] ${slideClass}`}>
      {/* 아바타 */}
      <div
        className={`w-full aspect-square max-w-[160px] rounded-2xl border-2 border-gray-600
          ring-2 ${ringColor} flex items-center justify-center bg-gray-800 text-6xl
          transition-all duration-700`}
      >
        🤖
      </div>

      {/* 에이전트 정보 */}
      <div className={`flex flex-col ${alignClass} gap-1`}>
        <span className="text-base font-bold text-white truncate max-w-[200px]">{agent.name}</span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-semibold self-start ${
            PROVIDER_BADGE[agent.provider] ?? 'bg-gray-500/20 text-gray-400'
          } ${side === 'right' ? 'self-end' : ''}`}
        >
          {agent.provider}
        </span>
        <span className="text-xs text-gray-400 truncate max-w-[200px]">{agent.model_id}</span>
        <span className="text-sm font-mono font-bold text-yellow-400">ELO {agent.elo_rating}</span>
        <span className="text-xs text-gray-500">
          {agent.wins}승 {agent.losses}패 {agent.draws}무
        </span>
      </div>
    </div>
  );
}
