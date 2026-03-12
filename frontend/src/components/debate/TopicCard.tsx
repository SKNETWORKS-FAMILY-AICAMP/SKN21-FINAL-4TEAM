'use client';

import Link from 'next/link';
import { Users, Clock, Shield, CalendarClock, Lock } from 'lucide-react';
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
  const isLive = topic.status === 'in_progress';
  const countdown = topic.scheduled_end_at ? getEndCountdown(topic.scheduled_end_at) : null;

  return (
    <Link
      href={`/debate/topics/${topic.id}`}
      className="group block bg-bg-surface border border-border rounded-2xl p-5 hover:border-primary/50 hover:shadow-md transition-all no-underline"
    >
      {/* 상단: 상태 배지 + 모드 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {isLive ? (
            <span className="flex items-center gap-1 text-xs font-bold text-red-500 bg-red-500/10 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse inline-block" />
              LIVE
            </span>
          ) : (
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                STATUS_STYLES[topic.status] || STATUS_STYLES.closed
              }`}
            >
              {STATUS_LABELS[topic.status] || topic.status}
            </span>
          )}
          {topic.is_admin_topic && <Shield size={13} className="text-primary" />}
          {topic.is_password_protected && <Lock size={11} className="text-yellow-500" />}
        </div>
        <div className="flex items-center gap-1">
          {currentUserId && topic.created_by === currentUserId && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onEdit?.(topic);
                }}
                className="text-[11px] text-text-muted hover:text-primary px-1.5 py-0.5 rounded transition-colors"
              >
                수정
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onDelete?.(topic.id);
                }}
                className="text-[11px] text-text-muted hover:text-red-400 px-1.5 py-0.5 rounded transition-colors"
              >
                삭제
              </button>
            </>
          )}
          <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-primary/10 text-primary">
            {MODE_LABELS[topic.mode] || topic.mode}
          </span>
        </div>
      </div>

      {/* 제목 */}
      <h3 className="text-base font-bold text-text mb-1.5 group-hover:text-primary transition-colors leading-snug line-clamp-2">
        {topic.title}
      </h3>

      {/* 설명 */}
      {topic.description && (
        <p className="text-xs text-text-secondary mb-3 line-clamp-2 leading-relaxed">
          {topic.description}
        </p>
      )}

      {/* 하단: 대기 인원 + 방장 + 시간 */}
      <div className="flex items-center justify-between text-xs text-text-muted mt-auto pt-2 border-t border-border">
        <span className="flex items-center gap-1">
          <Users size={12} />
          {topic.queue_count}명 대기
        </span>
        <div className="flex items-center gap-3">
          {topic.creator_nickname && <span>방장: {topic.creator_nickname}</span>}
          {countdown && (topic.status === 'open' || topic.status === 'in_progress') && (
            <span className="text-orange-400 font-medium flex items-center gap-1">
              <CalendarClock size={11} />
              {countdown}
            </span>
          )}
          {topic.status === 'scheduled' && topic.scheduled_start_at && (
            <span className="text-blue-400 flex items-center gap-1">
              <CalendarClock size={11} />
              {formatScheduleTime(topic.scheduled_start_at)} 시작
            </span>
          )}
          {!countdown && topic.status !== 'scheduled' && (
            <span className="flex items-center gap-1">
              <Clock size={11} />
              {getTimeAgo(topic.created_at)}
            </span>
          )}
        </div>
      </div>

      {/* 관리자 배지 */}
      {topic.is_admin_topic && (
        <div className="mt-2 pt-2 border-t border-border flex items-center gap-1 text-[10px] text-primary/70">
          <Shield size={10} />
          <span>플랫폼 공식 주제</span>
          {topic.scheduled_end_at && topic.status !== 'closed' && (
            <span className="ml-auto">{formatScheduleTime(topic.scheduled_end_at)} 까지</span>
          )}
        </div>
      )}
    </Link>
  );
}
