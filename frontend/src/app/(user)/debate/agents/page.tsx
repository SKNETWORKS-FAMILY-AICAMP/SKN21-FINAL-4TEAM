'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Bot, Plus } from 'lucide-react';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { AgentCard } from '@/components/debate/AgentCard';
import { SkeletonCard } from '@/components/ui/Skeleton';

export default function MyAgentsPage() {
  const { agents, loading, fetchMyAgents, deleteAgent } = useDebateAgentStore();

  useEffect(() => {
    fetchMyAgents();
  }, [fetchMyAgents]);

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-5">
        <h1 className="page-title flex items-center gap-2">
          <Bot size={24} className="text-primary" />
          내 에이전트
        </h1>
        <Link
          href="/debate/agents/create"
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white text-xs font-semibold rounded-lg no-underline hover:bg-primary/90 transition-colors"
        >
          <Plus size={14} />
          새 에이전트
        </Link>
      </div>

      <div className="flex flex-col gap-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
        ) : agents.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-text-muted text-sm mb-3">아직 에이전트가 없습니다.</p>
            <Link
              href="/debate/agents/create"
              className="text-sm text-primary font-semibold no-underline"
            >
              첫 에이전트 만들기 →
            </Link>
          </div>
        ) : (
          agents.map((agent) => (
            <div key={agent.id} className="relative group">
              <AgentCard agent={agent} />
              <button
                onClick={async () => {
                  if (!confirm(`"${agent.name}" 에이전트를 삭제하시겠습니까?`)) return;
                  try {
                    await deleteAgent(agent.id);
                  } catch (err: unknown) {
                    alert(err instanceof Error ? err.message : '삭제 실패');
                  }
                }}
                className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity
                  p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 text-xs"
                title="에이전트 삭제"
              >
                삭제
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
