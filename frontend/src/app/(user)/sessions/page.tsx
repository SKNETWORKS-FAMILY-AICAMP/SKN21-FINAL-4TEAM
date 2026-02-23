'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { MessageSquare, Clock, Pin, Trash2, Archive } from 'lucide-react';
import { api } from '@/lib/api';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { AgeRatingBadge } from '@/components/persona/AgeRatingBadge';
import { CATEGORIES } from '@/constants/categories';

type Session = {
  id: string;
  persona_id: string;
  llm_model_id: string | null;
  status: string;
  started_at: string;
  last_active_at: string;
  title: string | null;
  is_pinned: boolean;
  persona_display_name: string | null;
  persona_background_image_url: string | null;
  persona_age_rating: string | null;
  persona_category: string | null;
};

function sortSessions(sessions: Session[]): Session[] {
  return [...sessions].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    return new Date(b.last_active_at).getTime() - new Date(a.last_active_at).getTime();
  });
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  return new Date(dateStr).toLocaleDateString('ko-KR');
}

export default function SessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<{ items: Session[]; total: number }>('/chat/sessions')
      .then((res) => setSessions(sortSessions(res.items ?? [])))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleNewSession = async () => {
    router.push('/personas');
  };

  const handlePin = async (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    try {
      await api.patch(`/chat/sessions/${session.id}`, { is_pinned: !session.is_pinned });
      setSessions((prev) =>
        sortSessions(
          prev.map((s) => (s.id === session.id ? { ...s, is_pinned: !s.is_pinned } : s)),
        ),
      );
    } catch {
      // silent fail
    }
  };

  const handleDelete = async (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    if (!window.confirm('이 대화를 삭제하시겠습니까?')) return;
    try {
      await api.delete(`/chat/sessions/${session.id}`);
      setSessions((prev) => prev.filter((s) => s.id !== session.id));
    } catch {
      // silent fail
    }
  };

  const handleArchive = async (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    try {
      await api.post(`/chat/sessions/${session.id}/archive`);
      setSessions((prev) =>
        sortSessions(
          prev.map((s) => (s.id === session.id ? { ...s, status: 'archived' } : s)),
        ),
      );
    } catch {
      // silent fail
    }
  };

  const getCategoryLabel = (category: string | null) => {
    if (!category) return null;
    return CATEGORIES.find((c) => c.id === category)?.label ?? category;
  };

  return (
    <div className="max-w-[800px] mx-auto py-6 px-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="m-0 text-2xl text-text">내 대화</h1>
        <button onClick={handleNewSession} className="btn-primary">
          + 새 대화
        </button>
      </div>

      {loading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {!loading && sessions.length === 0 && (
        <EmptyState
          icon={<MessageSquare size={48} />}
          title="진행 중인 대화가 없습니다"
          description="페르소나를 선택하고 대화를 시작해보세요"
          action={
            <button onClick={handleNewSession} className="btn-primary">
              새 대화 시작하기
            </button>
          }
        />
      )}

      <div className="flex flex-col gap-3">
        {sessions.map((session) => (
          <div
            key={session.id}
            className="card cursor-pointer transition-all duration-200 hover:shadow-bubble hover:border-primary/50 overflow-hidden"
            onClick={() => router.push(`/chat/${session.id}`)}
          >
            <div className="flex gap-3">
              {/* 페르소나 썸네일 */}
              <div
                className="w-14 h-14 rounded-xl shrink-0 bg-gradient-to-br from-primary/20 to-secondary/20 bg-cover bg-center"
                style={
                  session.persona_background_image_url
                    ? { backgroundImage: `url(${session.persona_background_image_url})` }
                    : undefined
                }
              />

              {/* 세션 정보 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  {session.is_pinned && <Pin size={12} className="text-primary shrink-0" />}
                  <span className="text-sm font-bold text-text truncate">
                    {session.persona_display_name || session.title || '알 수 없는 챗봇'}
                  </span>
                  {session.persona_age_rating && (
                    <AgeRatingBadge
                      rating={session.persona_age_rating as 'all' | '15+' | '18+'}
                      locked={false}
                    />
                  )}
                  <span
                    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-badge text-[10px] font-semibold text-white shrink-0 ${
                      session.status === 'active' ? 'bg-success' : 'bg-text-muted'
                    }`}
                  >
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full ${
                        session.status === 'active' ? 'bg-white animate-pulse' : 'bg-white/60'
                      }`}
                    />
                    {session.status === 'active'
                      ? '진행중'
                      : session.status === 'archived'
                        ? '보관'
                        : '종료'}
                  </span>
                </div>

                {/* 세션 제목 (페르소나 이름과 다를 때만 표시) */}
                {session.title &&
                  session.persona_display_name &&
                  session.title !== session.persona_display_name && (
                    <p className="m-0 text-xs text-text-secondary truncate mb-1">
                      {session.title}
                    </p>
                  )}

                <div className="flex items-center gap-2 text-[11px] text-text-muted">
                  {session.persona_category && (
                    <span className="px-1.5 py-0.5 rounded bg-bg-tag text-text-muted">
                      {getCategoryLabel(session.persona_category)}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Clock size={10} />
                    {formatRelativeTime(session.last_active_at)}
                  </span>
                </div>
              </div>

              {/* 액션 버튼 */}
              <div className="flex items-center gap-0.5 shrink-0">
                <button
                  onClick={(e) => handlePin(e, session)}
                  className={`p-1.5 rounded transition-colors bg-transparent border-none cursor-pointer ${
                    session.is_pinned
                      ? 'text-primary hover:text-primary/80'
                      : 'text-text-muted hover:text-text'
                  }`}
                  title={session.is_pinned ? '고정 해제' : '고정'}
                >
                  <Pin size={14} />
                </button>
                <button
                  onClick={(e) => handleArchive(e, session)}
                  className="p-1.5 rounded text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
                  title="보관"
                >
                  <Archive size={14} />
                </button>
                <button
                  onClick={(e) => handleDelete(e, session)}
                  className="p-1.5 rounded text-text-muted hover:text-danger transition-colors bg-transparent border-none cursor-pointer"
                  title="삭제"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
