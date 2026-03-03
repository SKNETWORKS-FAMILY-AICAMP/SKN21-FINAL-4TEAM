'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Bot, TrendingUp, Trophy, Clock, Edit, Globe, EyeOff } from 'lucide-react';
import { api } from '@/lib/api';
import type { DebateAgent, AgentVersion } from '@/stores/debateAgentStore';
import type { DebateMatch } from '@/stores/debateStore';
import { AgentConnectionGuide } from '@/components/debate/AgentConnectionGuide';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { getTimeAgo } from '@/lib/format';

type H2HEntry = {
  opponent_id: string;
  opponent_name: string;
  opponent_image_url: string | null;
  total_matches: number;
  wins: number;
  losses: number;
  draws: number;
};

export default function AgentProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<DebateAgent | null>(null);
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [matches, setMatches] = useState<DebateMatch[]>([]);
  const [h2h, setH2h] = useState<H2HEntry[]>([]);
  const [error, setError] = useState('');
  const [publishing, setPublishing] = useState(false);

  useEffect(() => {
    api
      .get<DebateAgent>(`/agents/${id}`)
      .then(setAgent)
      .catch(() => setError('에이전트 정보를 불러오지 못했습니다.'));
    api.get<AgentVersion[]>(`/agents/${id}/versions`).then(setVersions).catch(() => {});
    api
      .get<{ items: DebateMatch[] }>(`/matches?agent_id=${id}&limit=10`)
      .then((r) => setMatches(r.items))
      .catch(() => {});
    api.get<H2HEntry[]>(`/agents/${id}/head-to-head`).then(setH2h).catch(() => {});
  }, [id]);

  const handleTogglePublic = async () => {
    if (!agent || publishing) return;
    const next = !agent.is_profile_public;
    setPublishing(true);
    try {
      await api.put(`/agents/${agent.id}`, { is_profile_public: next });
      setAgent({ ...agent, is_profile_public: next });
    } catch {
      /* 실패 시 원상복구 없이 다음 시도 가능 */
    } finally {
      setPublishing(false);
    }
  };

  if (error) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

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
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0 overflow-hidden">
              {agent.image_url ? (
                <img src={agent.image_url} alt={agent.name} className="w-full h-full object-cover" />
              ) : (
                <Bot size={26} />
              )}
            </div>
            <div>
              <h1 className="text-lg font-bold text-text">{agent.name}</h1>
              <span className="text-xs text-text-muted">
                {agent.provider} / {agent.model_id}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleTogglePublic}
              disabled={publishing}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors ${
                agent.is_profile_public
                  ? 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20'
                  : 'bg-bg-surface border-border text-text-muted hover:bg-border/20'
              }`}
            >
              {agent.is_profile_public ? (
                <>
                  <Globe size={13} />
                  갤러리 공개
                </>
              ) : (
                <>
                  <EyeOff size={13} />
                  갤러리 비공개
                </>
              )}
            </button>
            <Link
              href={`/debate/agents/${agent.id}/edit`}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-lg text-xs font-semibold text-text hover:bg-border/20 transition-colors no-underline"
            >
              <Edit size={13} />
              수정
            </Link>
          </div>
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

      {/* 로컬 에이전트 WebSocket 연결 가이드 */}
      {agent.provider === 'local' && (
        <div className="mb-4">
          <AgentConnectionGuide agentId={agent.id} isConnected={agent.is_connected} />
        </div>
      )}

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

      {/* H2H 전적 */}
      {h2h.length > 0 && (
        <>
          <h3 className="text-sm font-bold text-text mb-2">상대별 전적 (H2H)</h3>
          <div className="flex flex-col gap-2 mb-6">
            {h2h.map((entry) => (
              <div
                key={entry.opponent_id}
                className="bg-bg-surface border border-border rounded-lg p-3 flex items-center justify-between"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-bg-hover border border-border flex items-center justify-center overflow-hidden shrink-0">
                    {entry.opponent_image_url ? (
                      <img
                        src={entry.opponent_image_url}
                        alt={entry.opponent_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <Bot size={14} className="text-text-muted" />
                    )}
                  </div>
                  <Link
                    href={`/debate/agents/${entry.opponent_id}`}
                    className="text-sm font-medium text-text hover:text-primary no-underline transition-colors truncate"
                  >
                    {entry.opponent_name}
                  </Link>
                </div>
                <div className="text-xs font-mono shrink-0 ml-3">
                  <span className="text-green-500">{entry.wins}W</span>
                  <span className="text-text-muted mx-1">{entry.draws}D</span>
                  <span className="text-red-400">{entry.losses}L</span>
                  <span className="text-text-muted ml-1.5 text-[11px]">/{entry.total_matches}전</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

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
