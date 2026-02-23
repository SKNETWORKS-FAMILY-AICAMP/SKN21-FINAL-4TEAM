'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Bot, Plus } from 'lucide-react';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { AgentCard } from '@/components/debate/AgentCard';
import { SkeletonCard } from '@/components/ui/Skeleton';

export default function MyAgentsPage() {
  const { agents, loading, fetchMyAgents } = useDebateAgentStore();

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
          agents.map((agent) => <AgentCard key={agent.id} agent={agent} />)
        )}
      </div>
    </div>
  );
}
