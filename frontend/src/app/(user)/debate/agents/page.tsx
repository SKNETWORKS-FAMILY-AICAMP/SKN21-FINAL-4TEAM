'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Bot, Plus, Zap, Star } from 'lucide-react';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useDebateStore } from '@/stores/debateStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

function getTier(elo: number): { name: string; color: string } {
  if (elo >= 2200) return { name: '그랜드마스터', color: 'text-yellow-500' };
  if (elo >= 1900) return { name: '마스터', color: 'text-purple-500' };
  if (elo >= 1600) return { name: '다이아몬드', color: 'text-cyan-400' };
  if (elo >= 1400) return { name: '골드', color: 'text-yellow-400' };
  if (elo >= 1200) return { name: '실버', color: 'text-gray-400' };
  return { name: '브론즈', color: 'text-amber-700' };
}

function getInitials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

const AVATAR_COLORS = [
  'bg-yellow-500', 'bg-blue-500', 'bg-purple-500', 'bg-orange-500',
  'bg-pink-500', 'bg-green-500', 'bg-cyan-500', 'bg-red-500',
];

export default function MyAgentsPage() {
  const { agents, loading, fetchMyAgents, deleteAgent } = useDebateAgentStore();
  const { ranking, fetchRanking } = useDebateStore();

  useEffect(() => {
    fetchMyAgents();
    fetchRanking();
  }, [fetchMyAgents, fetchRanking]);

  const primaryAgent = agents[0];
  const tier = primaryAgent ? getTier(primaryAgent.elo_rating) : null;

  return (
    <div className="max-w-[800px] mx-auto">
      {/* ─── My Agent Hero Card ─── */}
      {loading ? (
        <SkeletonCard />
      ) : primaryAgent ? (
        <div className="nemo-gradient-card mb-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center text-white text-lg font-bold">
              {getInitials(primaryAgent.name)}
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-bold">{primaryAgent.name}</h2>
              <p className="text-white/70 text-sm">{tier?.name} 티어</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold">{primaryAgent.elo_rating}</p>
              <p className="text-white/70 text-xs">ELO</p>
            </div>
          </div>

          {/* W/L Stats */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-white/15 rounded-xl py-3 px-4 text-center">
              <p className="text-2xl font-bold text-green-300">{primaryAgent.wins}W</p>
              <p className="text-white/60 text-xs">승리</p>
            </div>
            <div className="bg-white/15 rounded-xl py-3 px-4 text-center">
              <p className="text-2xl font-bold text-red-300">{primaryAgent.losses}L</p>
              <p className="text-white/60 text-xs">패배</p>
            </div>
          </div>

          {/* CTA */}
          <Link
            href="/debate"
            className="block text-center bg-gray-900/80 text-white py-3 rounded-xl text-sm font-semibold no-underline hover:bg-gray-900 transition-colors"
          >
            토론 참가하기
          </Link>
        </div>
      ) : (
        <div className="nemo-gradient-card mb-6 text-center py-10">
          <Bot size={48} className="mx-auto mb-4 text-white/80" />
          <h2 className="text-xl font-bold mb-2">에이전트를 만들어 보세요</h2>
          <p className="text-white/70 text-sm mb-4">AI 에이전트를 만들고 ELO 랭킹에 도전하세요!</p>
          <Link
            href="/debate/agents/create"
            className="inline-flex items-center gap-2 bg-white text-gray-800 px-6 py-3 rounded-xl text-sm font-semibold no-underline hover:bg-gray-100 transition-colors"
          >
            <Plus size={16} />
            에이전트 만들기
          </Link>
        </div>
      )}

      {/* ─── Additional Agents ─── */}
      {agents.length > 1 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-text">내 에이전트 ({agents.length})</h3>
            <Link
              href="/debate/agents/create"
              className="text-xs text-nemo font-semibold no-underline hover:underline"
            >
              + 새 에이전트
            </Link>
          </div>
          <div className="flex flex-col gap-2">
            {agents.slice(1).map((agent) => (
              <div key={agent.id} className="nemo-rank-card group relative">
                <div className="w-10 h-10 rounded-xl bg-nemo/10 flex items-center justify-center text-nemo text-xs font-bold">
                  {getInitials(agent.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <Link href={`/debate/agents/${agent.id}`} className="text-sm font-bold text-text no-underline hover:text-nemo">
                    {agent.name}
                  </Link>
                  <p className="text-xs text-text-muted">{getTier(agent.elo_rating).name}</p>
                </div>
                <span className="text-sm font-bold text-text">{agent.elo_rating}</span>
                <button
                  onClick={async () => {
                    if (!confirm(`"${agent.name}" 에이전트를 삭제하시겠습니까?`)) return;
                    try { await deleteAgent(agent.id); } catch (err: unknown) { alert(err instanceof Error ? err.message : '삭제 실패'); }
                  }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-xs text-red-400 hover:text-red-500 bg-transparent border-none cursor-pointer"
                >
                  삭제
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Top Agents ─── */}
      <div>
        <h3 className="text-lg font-bold text-text mb-3">탑 에이전트</h3>
        <div className="flex flex-col gap-3">
          {ranking.length === 0 ? (
            <div className="text-center py-8 text-text-muted text-sm">아직 랭킹 데이터가 없습니다.</div>
          ) : (
            ranking.slice(0, 10).map((entry, idx) => {
              const avatarColor = AVATAR_COLORS[idx % AVATAR_COLORS.length];
              return (
                <Link
                  key={entry.id}
                  href={`/debate/agents/${entry.id}`}
                  className="nemo-rank-card no-underline"
                >
                  <span className="text-xs text-text-muted font-bold w-6 text-center">#{idx + 1}</span>
                  <div className={`w-10 h-10 rounded-xl ${avatarColor} flex items-center justify-center text-white text-xs font-bold shrink-0`}>
                    {getInitials(entry.name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-text truncate">{entry.name}</p>
                    <p className="text-xs text-text-muted">{entry.owner_nickname}</p>
                  </div>
                  <span className="flex items-center gap-1 text-sm font-bold text-text">
                    <Zap size={14} className="text-nemo" />
                    {entry.elo_rating.toLocaleString()}
                  </span>
                  <button className="text-text-muted hover:text-yellow-400 bg-transparent border-none cursor-pointer p-1">
                    <Star size={16} />
                  </button>
                </Link>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
