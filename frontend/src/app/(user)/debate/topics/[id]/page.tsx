'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { MessageSquare, Users, ArrowLeft } from 'lucide-react';
import { api } from '@/lib/api';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useToastStore } from '@/stores/toastStore';
import { SkeletonCard } from '@/components/ui/Skeleton';
import type { DebateTopic, DebateMatch } from '@/stores/debateStore';

export default function TopicDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { joinQueue } = useDebateStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const addToast = useToastStore((s) => s.addToast);
  const [topic, setTopic] = useState<DebateTopic | null>(null);
  const [matches, setMatches] = useState<DebateMatch[]>([]);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [joining, setJoining] = useState(false);

  useEffect(() => {
    api.get<DebateTopic>(`/topics/${id}`).then(setTopic).catch(() => {});
    api
      .get<{ items: DebateMatch[] }>(`/matches?topic_id=${id}`)
      .then((r) => setMatches(r.items))
      .catch(() => {});
    fetchMyAgents();
  }, [id, fetchMyAgents]);

  const handleJoin = async () => {
    if (!selectedAgent) return;
    setJoining(true);
    try {
      const result = await joinQueue(id, selectedAgent);
      if (result.status === 'matched') {
        addToast('매치가 생성되었습니다!', 'success');
      } else {
        addToast('대기열에 등록되었습니다.', 'info');
      }
    } catch {
      addToast('참가에 실패했습니다.', 'error');
    } finally {
      setJoining(false);
    }
  };

  if (!topic) return <SkeletonCard />;

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <Link
        href="/debate"
        className="flex items-center gap-1 text-sm text-text-muted no-underline hover:text-text mb-4"
      >
        <ArrowLeft size={14} />
        토론 목록
      </Link>

      <h1 className="text-xl font-bold text-text mb-2">{topic.title}</h1>
      {topic.description && (
        <p className="text-sm text-text-secondary mb-4">{topic.description}</p>
      )}

      <div className="flex gap-3 text-xs text-text-muted mb-6">
        <span className="px-2 py-0.5 rounded bg-primary/10 text-primary font-medium">
          {topic.mode}
        </span>
        <span>최대 {topic.max_turns}턴</span>
        <span>턴당 {topic.turn_token_limit} 토큰</span>
      </div>

      {/* 참가 폼 */}
      {topic.status === 'open' && agents.length > 0 && (
        <div className="bg-bg-surface border border-border rounded-xl p-4 mb-6">
          <h3 className="text-sm font-bold text-text mb-3">토론 참가</h3>
          <div className="flex gap-2">
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="flex-1 px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
            >
              <option value="">에이전트 선택...</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} (ELO {a.elo_rating})
                </option>
              ))}
            </select>
            <button
              onClick={handleJoin}
              disabled={!selectedAgent || joining}
              className="px-4 py-2 bg-primary text-white text-sm font-semibold rounded-lg
                hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {joining ? '참가 중...' : '참가'}
            </button>
          </div>
        </div>
      )}

      {topic.status === 'open' && agents.length === 0 && (
        <div className="bg-bg-surface border border-border rounded-xl p-4 mb-6 text-center">
          <p className="text-sm text-text-muted mb-2">참가하려면 에이전트를 먼저 생성하세요.</p>
          <Link
            href="/debate/agents/create"
            className="text-sm text-primary font-semibold no-underline"
          >
            에이전트 만들기 →
          </Link>
        </div>
      )}

      {/* 완료된 매치 목록 */}
      <h3 className="text-sm font-bold text-text mb-3 flex items-center gap-1.5">
        <MessageSquare size={14} />
        매치 기록
      </h3>
      <div className="flex flex-col gap-2">
        {matches.length === 0 ? (
          <p className="text-xs text-text-muted text-center py-4">아직 매치가 없습니다.</p>
        ) : (
          matches.map((m) => (
            <Link
              key={m.id}
              href={`/debate/matches/${m.id}`}
              className="flex items-center justify-between bg-bg-surface border border-border rounded-lg p-3 no-underline hover:border-primary/30 transition-colors"
            >
              <div className="text-sm text-text">
                {m.agent_a.name} vs {m.agent_b.name}
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                    m.status === 'completed'
                      ? 'bg-green-500/10 text-green-500'
                      : m.status === 'in_progress'
                        ? 'bg-yellow-500/10 text-yellow-500'
                        : 'bg-text-muted/10 text-text-muted'
                  }`}
                >
                  {m.status}
                </span>
                {m.status === 'completed' && (
                  <span className="text-xs font-bold text-text">
                    {m.score_a} : {m.score_b}
                  </span>
                )}
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
