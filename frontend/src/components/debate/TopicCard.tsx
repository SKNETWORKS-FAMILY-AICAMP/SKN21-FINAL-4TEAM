'use client';

import Link from 'next/link';
import { MessageSquare, Users, Clock, Shield, CalendarClock, Wrench } from 'lucide-react';
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
  const countdown = topic.scheduled_end_at ? getEndCountdown(topic.scheduled_end_at) : null;

  return (
    <Link
      href={`/debate/topics/${topic.id}`}
      className="block bg-bg-surface border border-border rounded-xl p-4 hover:border-primary/30 transition-colors no-underline"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-1.5 flex-1 mr-2 min-w-0">
          {topic.is_admin_topic && (
            <span title="관리자 주제" className="shrink-0">
              <Shield size={13} className="text-primary" />
            </span>
          )}
          <h3 className="text-sm font-bold text-text truncate">{topic.title}</h3>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {currentUserId && topic.created_by === currentUserId && (
            <div className="flex gap-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onEdit?.(topic);
                }}
                className="text-xs text-gray-400 hover:text-primary px-2 py-1"
              >
                수정
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onDelete?.(topic.id);
                }}
                className="text-xs text-gray-400 hover:text-red-400 px-2 py-1"
              >
                삭제
              </button>
            </div>
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

      {topic.description && (
        <p className="text-xs text-text-secondary mb-1 line-clamp-2">{topic.description}</p>
      )}

      {topic.creator_nickname && (
        <span className="text-xs text-text-muted block mb-2">by {topic.creator_nickname}</span>
      )}

      <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
        <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
          {MODE_LABELS[topic.mode] || topic.mode}
        </span>
        {/* 툴 허용 여부 배지 */}
        <span
          title={topic.tools_enabled ? '툴 사용 허용' : '툴 사용 금지'}
          className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded font-medium ${
            topic.tools_enabled
              ? 'bg-emerald-500/10 text-emerald-500'
              : 'bg-red-500/10 text-red-400'
          }`}
        >
          <Wrench size={10} />
          {topic.tools_enabled ? '툴 허용' : '툴 금지'}
        </span>
        <span className="flex items-center gap-1">
          <Users size={12} />
          대기 {topic.queue_count}명
        </span>
        <span className="flex items-center gap-1">
          <MessageSquare size={12} />
          매치 {topic.match_count}
        </span>

        {/* 종료 카운트다운 */}
        {countdown && (topic.status === 'open' || topic.status === 'in_progress') && (
          <span className="flex items-center gap-1 text-orange-400 font-medium">
            <CalendarClock size={12} />
            {countdown}
          </span>
        )}

        {/* 예정 시작 시각 */}
        {topic.status === 'scheduled' && topic.scheduled_start_at && (
          <span className="flex items-center gap-1 text-blue-400">
            <CalendarClock size={12} />
            {formatScheduleTime(topic.scheduled_start_at)} 시작
          </span>
        )}

        <span className="flex items-center gap-1 ml-auto">
          <Clock size={12} />
          {getTimeAgo(topic.created_at)}
        </span>
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
    </Link>
  );
}
