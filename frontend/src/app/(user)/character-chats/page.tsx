'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { MessageCircle, Inbox, Send, Check, X, Clock } from 'lucide-react';
import { useCharacterChatStore } from '@/stores/characterChatStore';
import type { ChatSession } from '@/stores/characterChatStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

type Tab = 'incoming' | 'outgoing';

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: '대기 중', color: 'text-yellow-600 bg-yellow-100' },
  active: { label: '진행 중', color: 'text-primary bg-primary/10' },
  completed: { label: '완료', color: 'text-green-600 bg-green-100' },
  rejected: { label: '거절됨', color: 'text-red-600 bg-red-100' },
  cancelled: { label: '취소됨', color: 'text-text-muted bg-bg-hover' },
};

export default function CharacterChatsPage() {
  const { incoming, outgoing, loading, fetchIncoming, fetchOutgoing, respondToRequest } =
    useCharacterChatStore();
  const [tab, setTab] = useState<Tab>('incoming');

  useEffect(() => {
    fetchIncoming();
    fetchOutgoing();
  }, [fetchIncoming, fetchOutgoing]);

  const sessions = tab === 'incoming' ? incoming : outgoing;

  const handleRespond = async (sessionId: string, accept: boolean) => {
    await respondToRequest(sessionId, accept);
    fetchIncoming();
    fetchOutgoing();
  };

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <h1 className="page-title flex items-center gap-2">
        <MessageCircle size={24} className="text-primary" />
        캐릭터 대화 요청
      </h1>

      {/* 탭 */}
      <div className="flex gap-1 mb-4 border-b border-border">
        <TabButton active={tab === 'incoming'} onClick={() => setTab('incoming')}>
          <Inbox size={14} />
          수신 ({incoming?.total ?? 0})
        </TabButton>
        <TabButton active={tab === 'outgoing'} onClick={() => setTab('outgoing')}>
          <Send size={14} />
          발신 ({outgoing?.total ?? 0})
        </TabButton>
      </div>

      {/* 세션 목록 */}
      <div className="flex flex-col gap-2">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
        ) : sessions?.items.length === 0 ? (
          <div className="text-center py-12 text-text-muted text-sm">
            {tab === 'incoming' ? '수신된 대화 요청이 없습니다.' : '발신한 대화 요청이 없습니다.'}
          </div>
        ) : (
          sessions?.items.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              isIncoming={tab === 'incoming'}
              onRespond={handleRespond}
            />
          ))
        )}
      </div>
    </div>
  );
}

function SessionCard({
  session,
  isIncoming,
  onRespond,
}: {
  session: ChatSession;
  isIncoming: boolean;
  onRespond: (id: string, accept: boolean) => void;
}) {
  const status = STATUS_LABELS[session.status] || STATUS_LABELS.pending;

  return (
    <div className="bg-bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-text">
            {session.requester.display_name || '???'}
          </span>
          <span className="text-text-muted text-xs">↔</span>
          <span className="text-sm font-bold text-text">
            {session.responder.display_name || '???'}
          </span>
        </div>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${status.color}`}>
          {status.label}
        </span>
      </div>

      <div className="flex items-center gap-4 text-xs text-text-muted mb-3">
        <span>턴: {session.current_turn}/{session.max_turns}</span>
        <span>{session.age_rating}</span>
        <span className="flex items-center gap-1">
          <Clock size={10} />
          {new Date(session.requested_at).toLocaleDateString('ko-KR')}
        </span>
      </div>

      <div className="flex gap-2">
        {session.status === 'active' || session.status === 'completed' ? (
          <Link
            href={`/character-chats/${session.id}`}
            className="flex-1 text-center px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary/10 text-primary no-underline hover:bg-primary/20 transition-colors"
          >
            대화 보기
          </Link>
        ) : null}

        {isIncoming && session.status === 'pending' && (
          <>
            <button
              onClick={() => onRespond(session.id, false)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-danger bg-danger/10 border-none cursor-pointer"
            >
              <X size={12} />
              거절
            </button>
            <button
              onClick={() => onRespond(session.id, true)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-primary border-none cursor-pointer"
            >
              <Check size={12} />
              수락
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-semibold bg-transparent border-none cursor-pointer transition-colors ${
        active
          ? 'text-primary border-b-2 border-primary -mb-px'
          : 'text-text-muted hover:text-text'
      }`}
    >
      {children}
    </button>
  );
}
