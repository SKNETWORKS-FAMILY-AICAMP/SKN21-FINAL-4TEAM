'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { MessageSquare, Users, ArrowLeft } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useToastStore } from '@/stores/toastStore';
import { SkeletonCard } from '@/components/ui/Skeleton';
import type { DebateTopic, DebateMatch } from '@/stores/debateStore';

type ConflictInfo = {
  existingTopicId: string;
  existingTopicTitle: string;
};

type QueueStatusResponse = {
  status: 'not_in_queue' | 'queued' | 'matched';
  joined_at?: string;
  is_ready?: boolean;
  opponent_agent_id?: string | null;
  match_id?: string;
};

export default function TopicDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { joinQueue } = useDebateStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const addToast = useToastStore((s) => s.addToast);
  const [topic, setTopic] = useState<DebateTopic | null>(null);
  const [matches, setMatches] = useState<DebateMatch[]>([]);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [password, setPassword] = useState('');
  const [joining, setJoining] = useState(false);
  const [conflictInfo, setConflictInfo] = useState<ConflictInfo | null>(null);
  const [forceJoining, setForceJoining] = useState(false);
  const [agentQueueStatus, setAgentQueueStatus] = useState<QueueStatusResponse | null>(null);

  useEffect(() => {
    api.get<DebateTopic>(`/topics/${id}`).then(setTopic).catch(() => {});
    api
      .get<{ items: DebateMatch[] }>(`/matches?topic_id=${id}`)
      .then((r) => setMatches(r.items))
      .catch(() => {});
    fetchMyAgents();
  }, [id, fetchMyAgents]);

  const handleAgentChange = async (agentId: string) => {
    setSelectedAgent(agentId);
    setConflictInfo(null);
    setAgentQueueStatus(null);
    if (!agentId) return;
    try {
      const status = await api.get<QueueStatusResponse>(
        `/topics/${id}/queue/status?agent_id=${agentId}`,
      );
      setAgentQueueStatus(status);
    } catch {
      // 상태 조회 실패는 무음 처리 — 참가 시점에 에러 처리
    }
  };

  const handleForceJoin = async () => {
    if (!conflictInfo || !selectedAgent) return;
    setForceJoining(true);
    try {
      const { leaveQueue } = useDebateStore.getState();
      await leaveQueue(conflictInfo.existingTopicId, selectedAgent);
      setConflictInfo(null);
      await handleJoin();
    } catch {
      addToast('error', '대기 취소 중 오류가 발생했습니다.');
    } finally {
      setForceJoining(false);
    }
  };

  const handleJoin = async () => {
    if (!selectedAgent) return;
    setJoining(true);
    try {
      const result = await joinQueue(id, selectedAgent, password || undefined);
      if (result.status === 'matched' && result.match_id) {
        router.push(`/debate/matches/${result.match_id}`);
      } else {
        router.push(`/debate/waiting/${id}?agent=${selectedAgent}`);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = e.body as { message: string; existing_topic_id: string } | null;
        const existingTopicId = detail?.existing_topic_id ?? '';
        let existingTopicTitle = '다른 토픽';
        if (existingTopicId) {
          try {
            const t = await api.get<{ title: string }>(`/topics/${existingTopicId}`);
            existingTopicTitle = t.title;
          } catch {}
        }
        setConflictInfo({ existingTopicId, existingTopicTitle });
      } else {
        addToast('error', e instanceof ApiError ? e.message : '참가에 실패했습니다.');
      }
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
        <span>최대 {topic.max_turns}라운드 (총 {topic.max_turns * 2}번 발언)</span>
        <span>턴당 {topic.turn_token_limit} 토큰</span>
      </div>

      {/* 참가 폼 */}
      {topic.status === 'open' && agents.length > 0 && (
        <div className="bg-bg-surface border border-border rounded-xl p-4 mb-6">
          <h3 className="text-sm font-bold text-text mb-3">토론 참가</h3>
          <div className="flex gap-2">
            <div className="flex-1 flex flex-col">
              <select
                value={selectedAgent}
                onChange={(e) => handleAgentChange(e.target.value)}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
              >
                <option value="">에이전트 선택...</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} (ELO {a.elo_rating})
                  </option>
                ))}
              </select>
              {agentQueueStatus?.status === 'queued' && (
                <p className="text-xs text-yellow-500 mt-1">
                  이 에이전트는 현재 다른 토픽 대기 중입니다. 참가 시 기존 대기가 취소됩니다.
                </p>
              )}
              {agentQueueStatus?.status === 'matched' && agentQueueStatus.match_id && (
                <p className="text-xs text-blue-400 mt-1">
                  진행 중인 매치가 있습니다.{' '}
                  <button
                    onClick={() => router.push(`/debate/matches/${agentQueueStatus.match_id}`)}
                    className="underline"
                  >
                    매치 보기
                  </button>
                </p>
              )}
              {conflictInfo && (
                <div className="mt-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-sm">
                  <p className="text-text mb-2">
                    이미{' '}
                    <span className="font-semibold">"{conflictInfo.existingTopicTitle}"</span>에
                    대기 중입니다. 기존 대기를 취소하고 이 토픽에 참가할까요?
                  </p>
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setConflictInfo(null)}
                      className="px-3 py-1.5 text-xs text-text-muted border border-border rounded-lg"
                    >
                      취소
                    </button>
                    <button
                      onClick={handleForceJoin}
                      disabled={forceJoining}
                      className="px-3 py-1.5 text-xs bg-primary text-white rounded-lg disabled:opacity-50"
                    >
                      {forceJoining ? '처리 중...' : '기존 대기 취소 후 참가'}
                    </button>
                  </div>
                </div>
              )}
              {topic.is_password_protected && (
                <input
                  type="password"
                  placeholder="방 비밀번호"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full mt-2 px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
                />
              )}
            </div>
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
