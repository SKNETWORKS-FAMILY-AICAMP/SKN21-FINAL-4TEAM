'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Play, CheckCircle } from 'lucide-react';
import { useCharacterChatStore } from '@/stores/characterChatStore';
import { AgeRatingBadge } from '@/components/persona/AgeRatingBadge';
import { SkeletonCard } from '@/components/ui/Skeleton';

export default function CharacterChatDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const { currentChat, loading, advancing, fetchChat, advanceChat } = useCharacterChatStore();

  useEffect(() => {
    if (sessionId) fetchChat(sessionId);
  }, [sessionId, fetchChat]);

  if (loading && !currentChat) {
    return (
      <div className="max-w-[600px] mx-auto py-6 px-4">
        <SkeletonCard />
      </div>
    );
  }

  if (!currentChat) {
    return (
      <div className="max-w-[600px] mx-auto py-6 px-4 text-center text-text-muted">
        대화를 찾을 수 없습니다.
      </div>
    );
  }

  const { session, messages } = currentChat;
  const isActive = session.status === 'active';
  const isCompleted = session.status === 'completed';
  const canAdvance = isActive && session.current_turn < session.max_turns;

  return (
    <div className="max-w-[600px] mx-auto py-6 px-4">
      {/* 헤더 */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4 bg-transparent border-none cursor-pointer"
      >
        <ArrowLeft size={16} />
        돌아가기
      </button>

      <div className="bg-bg-surface border border-border rounded-xl p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-text">
              {session.requester.display_name}
            </span>
            <span className="text-text-muted">×</span>
            <span className="text-base font-bold text-text">
              {session.responder.display_name}
            </span>
            <AgeRatingBadge rating={session.age_rating} />
          </div>
          {isCompleted && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <CheckCircle size={12} />
              완료
            </span>
          )}
        </div>
        <div className="text-xs text-text-muted">
          턴: {session.current_turn}/{session.max_turns}
        </div>
      </div>

      {/* 메시지 */}
      <div className="flex flex-col gap-3 mb-4">
        {messages.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-sm">
            아직 대화가 시작되지 않았습니다. &quot;다음 턴&quot;을 눌러 시작하세요.
          </div>
        ) : (
          messages.map((msg) => {
            const isRequester = msg.persona_id === session.requester.persona_id;
            return (
              <div
                key={msg.id}
                className={`flex ${isRequester ? 'justify-start' : 'justify-end'}`}
              >
                <div
                  className={`max-w-[80%] rounded-xl px-4 py-3 ${
                    isRequester
                      ? 'bg-bg-surface border border-border'
                      : 'bg-primary/10 border border-primary/20'
                  }`}
                >
                  <span className="text-xs font-semibold text-text-muted block mb-1">
                    {msg.persona_display_name}
                  </span>
                  <p className="text-sm text-text whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Advance 버튼 */}
      {canAdvance && (
        <button
          onClick={() => advanceChat(sessionId)}
          disabled={advancing}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold bg-primary text-white border-none cursor-pointer disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          <Play size={16} />
          {advancing ? '생성 중...' : '다음 턴'}
        </button>
      )}
    </div>
  );
}
