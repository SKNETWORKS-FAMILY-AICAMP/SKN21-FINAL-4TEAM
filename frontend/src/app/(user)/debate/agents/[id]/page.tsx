'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Bot, TrendingUp, Trophy, Clock, Edit } from 'lucide-react';
import { api } from '@/lib/api';
import type { DebateAgent, AgentVersion } from '@/stores/debateAgentStore';
import type { DebateMatch } from '@/stores/debateStore';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { getTimeAgo } from '@/lib/format';

export default function AgentProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<DebateAgent | null>(null);
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [matches, setMatches] = useState<DebateMatch[]>([]);

  useEffect(() => {
    api.get<DebateAgent>(`/agents/${id}`).then(setAgent).catch(() => {});
    api.get<AgentVersion[]>(`/agents/${id}/versions`).then(setVersions).catch(() => {});
    api
      .get<{ items: DebateMatch[] }>(`/matches?agent_id=${id}&limit=10`)
      .then((r) => setMatches(r.items))
      .catch(() => {});
  }, [id]);

  if (!agent) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <SkeletonCard />
      </div>
    );
  }

  const totalGames = agent.wins + agent.losses + agent.draws;
  const winRate = totalGames > 0 ? Math.round((agent.wins / totalGames) * 100) : 0;

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <Link
        href="/debate/agents"
        className="flex items-center gap-1 text-sm text-text-muted no-underline hover:text-text mb-4"
      >
        <ArrowLeft size={14} />
        내 에이전트
      </Link>

      {/* 프로필 헤더 */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <Bot size={24} />
            </div>
            <div>
              <h1 className="text-lg font-bold text-text">{agent.name}</h1>
              <span className="text-xs text-text-muted">
                {agent.provider} / {agent.model_id}
              </span>
            </div>
          </div>
          <Link
            href={`/debate/agents/${agent.id}`}
            className="p-2 text-text-muted hover:text-text"
          >
            <Edit size={16} />
          </Link>
        </div>

        {agent.description && (
          <p className="text-sm text-text-secondary mt-3">{agent.description}</p>
        )}

        <div className="flex items-center gap-6 mt-4 text-sm">
          <span className="flex items-center gap-1.5">
            <TrendingUp size={14} className="text-primary" />
            <span className="font-bold text-text">{agent.elo_rating}</span>
            <span className="text-text-muted text-xs">ELO</span>
          </span>
          <span className="flex items-center gap-1.5">
            <Trophy size={14} className="text-primary" />
            <span className="text-text">
              {agent.wins}W {agent.losses}L {agent.draws}D
            </span>
          </span>
          <span className="font-bold text-primary">{winRate}%</span>
        </div>
      </div>

      {/* 버전 이력 */}
      <h3 className="text-sm font-bold text-text mb-2">프롬프트 버전 이력</h3>
      <div className="flex flex-col gap-2 mb-6">
        {versions.map((v) => (
          <div
            key={v.id}
            className="bg-bg-surface border border-border rounded-lg p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-primary">
                {v.version_tag || `v${v.version_number}`}
              </span>
              <span className="text-[11px] text-text-muted flex items-center gap-1">
                <Clock size={10} />
                {getTimeAgo(v.created_at)}
              </span>
            </div>
            <p className="text-xs text-text-secondary line-clamp-2 font-mono">
              {v.system_prompt}
            </p>
            <div className="text-[11px] text-text-muted mt-1">
              {v.wins}W {v.losses}L {v.draws}D
            </div>
          </div>
        ))}
      </div>

      {/* 최근 매치 */}
      <h3 className="text-sm font-bold text-text mb-2">최근 매치</h3>
      <div className="flex flex-col gap-2">
        {matches.length === 0 ? (
          <p className="text-xs text-text-muted text-center py-4">아직 매치 기록이 없습니다.</p>
        ) : (
          matches.map((m) => (
            <Link
              key={m.id}
              href={`/debate/matches/${m.id}`}
              className="flex items-center justify-between bg-bg-surface border border-border rounded-lg p-3 no-underline hover:border-primary/30 transition-colors"
            >
              <span className="text-sm text-text">
                {m.agent_a.name} vs {m.agent_b.name}
              </span>
              <span className="text-xs font-bold text-text">
                {m.score_a} : {m.score_b}
              </span>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
