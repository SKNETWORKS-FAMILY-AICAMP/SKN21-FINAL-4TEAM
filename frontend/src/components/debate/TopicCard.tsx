'use client';

import Link from 'next/link';
import { MessageSquare, Users, Clock, Shield, CalendarClock, Wrench, Lock } from 'lucide-react';
import type { DebateTopic } from '@/stores/debateStore';
import { getTimeAgo } from '@/lib/format';

type Props = {
  topic: DebateTopic;
  currentUserId?: string | null;
  onEdit?: (topic: DebateTopic) => void;
  onDelete?: (topicId: string) => void;
};

const STATUS_STYLES: Record<string, string> = {
  scheduled: 'bg-blue-500/10 text-blue-400',
  open: 'bg-green-500/10 text-green-500',
  in_progress: 'bg-yellow-500/10 text-yellow-500',
  closed: 'bg-text-muted/10 text-text-muted',
};

const STATUS_LABELS: Record<string, string> = {
  scheduled: '예정',
  open: '참가 가능',
  in_progress: '진행 중',
  closed: '종료',
};

const STATUS_ACCENT: Record<string, string> = {
  scheduled: 'bg-blue-500',
  open: 'bg-green-500',
  in_progress: 'bg-yellow-500',
  closed: 'bg-gray-500',
};

const MODE_LABELS: Record<string, string> = {
  debate: '토론',
  persuasion: '설득',
  cross_exam: '교차 심문',
};

function formatScheduleTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('ko-KR', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getEndCountdown(iso: string): string | null {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return null;
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}시간 ${m}분 후 종료`;
  if (m > 0) return `${m}분 후 종료`;
  return '곧 종료';
}

export function TopicCard({ topic, currentUserId, onEdit, onDelete }: Props) {
  const countdown = topic.scheduled_end_at ? getEndCountdown(topic.scheduled_end_at) : null;
  const statusColor = STATUS_ACCENT[topic.status] ?? 'bg-gray-500';

  return (
    <Link
      href={`/debate/topics/${topic.id}`}
      className="group block bg-bg-surface border border-border rounded-xl overflow-hidden hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5 transition-all no-underline"
    >
      <div className="flex">
        {/* 좌측 상태 액센트 바 */}
        <div className={`w-1 shrink-0 ${statusColor}`} />

        <div className="flex-1 p-4 min-w-0">
          {/* 헤더 */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
              {topic.is_admin_topic && (
                <Shield size={13} className="text-primary shrink-0" />
              )}
              {topic.is_password_protected && (
                <Lock size={11} className="text-yellow-400 shrink-0" />
              )}
              <h3 className="text-sm font-bold text-text truncate group-hover:text-primary transition-colors">
                {topic.title}
              </h3>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {currentUserId && topic.created_by === currentUserId && (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      onEdit?.(topic);
                    }}
                    className="text-[11px] text-gray-500 hover:text-primary px-1.5 py-0.5 rounded transition-colors"
                  >
                    수정
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      onDelete?.(topic.id);
                    }}
                    className="text-[11px] text-gray-500 hover:text-red-400 px-1.5 py-0.5 rounded transition-colors"
                  >
                    삭제
                  </button>
                </>
              )}
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-semibold whitespace-nowrap ${
                  STATUS_STYLES[topic.status] || STATUS_STYLES.closed
                }`}
              >
                {STATUS_LABELS[topic.status] || topic.status}
              </span>
            </div>
          </div>

          {/* 설명 */}
          {topic.description && (
            <p className="text-xs text-text-secondary mb-2 line-clamp-2 leading-relaxed">
              {topic.description}
            </p>
          )}

          {/* 메타 정보 */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
            <span className="px-2 py-0.5 rounded-md bg-primary/10 text-primary font-semibold">
              {MODE_LABELS[topic.mode] || topic.mode}
            </span>
            <span
              className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded-md font-medium ${
                topic.tools_enabled
                  ? 'bg-emerald-500/10 text-emerald-500'
                  : 'bg-red-500/10 text-red-400'
              }`}
            >
              <Wrench size={10} />
              {topic.tools_enabled ? '툴허용' : '툴금지'}
            </span>
            <span className="flex items-center gap-1">
              <Users size={11} />
              {topic.queue_count}명 대기
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare size={11} />
              매치 {topic.match_count}
            </span>
            {topic.creator_nickname && (
              <span className="text-text-muted/70">by {topic.creator_nickname}</span>
            )}

            {/* 우측 정렬 시간 정보 */}
            {countdown && (topic.status === 'open' || topic.status === 'in_progress') && (
              <span className="flex items-center gap-1 text-orange-400 font-medium ml-auto">
                <CalendarClock size={11} />
                {countdown}
              </span>
            )}
            {topic.status === 'scheduled' && topic.scheduled_start_at && (
              <span className="flex items-center gap-1 text-blue-400 ml-auto">
                <CalendarClock size={11} />
                {formatScheduleTime(topic.scheduled_start_at)} 시작
              </span>
            )}
            {!countdown && topic.status !== 'scheduled' && (
              <span className="flex items-center gap-1 ml-auto">
                <Clock size={11} />
                {getTimeAgo(topic.created_at)}
              </span>
            )}
          </div>

          {/* 관리자 배지 */}
          {topic.is_admin_topic && (
            <div className="mt-2 pt-2 border-t border-border flex items-center gap-1 text-[10px] text-primary/70">
              <Shield size={10} />
              <span>플랫폼 공식 주제</span>
              {topic.scheduled_end_at && topic.status !== 'closed' && (
                <span className="ml-auto text-text-muted">
                  ~{formatScheduleTime(topic.scheduled_end_at)}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
