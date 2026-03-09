'use client';

import Link from 'next/link';
import { MessageSquare, Users, Clock, Shield, CalendarClock, Wrench, Lock, TrendingUp } from 'lucide-react';
import type { DebateTopic } from '@/stores/debateStore';
import { getTimeAgo } from '@/lib/format';

type Props = {
  topic: DebateTopic;
  currentUserId?: string | null;
  onEdit?: (topic: DebateTopic) => void;
  onDelete?: (topicId: string) => void;
};

const STATUS_CONFIG: Record<string, { label: string; dotColor: string; bgColor: string; textColor: string }> = {
  open: { label: 'LIVE', dotColor: 'bg-red-500', bgColor: 'bg-red-500/10', textColor: 'text-red-500' },
  in_progress: { label: '대기중', dotColor: '', bgColor: 'bg-nemo/10', textColor: 'text-nemo' },
  scheduled: { label: '예정', dotColor: '', bgColor: 'bg-gray-500/10', textColor: 'text-gray-500' },
  closed: { label: '종료', dotColor: '', bgColor: 'bg-gray-400/10', textColor: 'text-gray-400' },
};

/* topic.description에서 카테고리 추출 시도 (fallback: topic.mode) */
const MODE_LABELS: Record<string, string> = {
  debate: 'AI·기술',
  persuasion: '경제·사회',
  cross_exam: '정치·외교',
};

function formatScheduleTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function getEndCountdown(iso: string): string | null {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return null;
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}시간 ${m}분 남음`;
  if (m > 0) return `${m}분 남음`;
  return '곧 종료';
}

export function TopicCard({ topic, currentUserId, onEdit, onDelete }: Props) {
  const config = STATUS_CONFIG[topic.status] ?? STATUS_CONFIG.closed;
  const countdown = topic.scheduled_end_at ? getEndCountdown(topic.scheduled_end_at) : null;
  const categoryLabel = MODE_LABELS[topic.mode] || 'AI·기술';

  // 간단한 참여 성장률 시뮬레이션 (실제로는 API에서)
  const growthPercent = topic.queue_count > 0 ? `+${Math.min(topic.queue_count * 3, 99)}%` : null;

  return (
    <Link
      href={`/debate/topics/${topic.id}`}
      className="nemo-topic-card block no-underline"
    >
      {/* Top row: status badge + category */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${config.bgColor} ${config.textColor}`}>
            {config.dotColor && <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor} animate-pulse`} />}
            {config.label}
          </span>
          {topic.is_admin_topic && (
            <span title="관리자 주제" className="shrink-0">
              <Shield size={13} className="text-primary" />
            </span>
          )}
          {topic.is_password_protected && (
            <span title="비밀번호 방" className="shrink-0">
              <Lock size={11} className="text-yellow-400" />
            </span>
          )}
        </div>
        <span className="text-xs text-text-muted">{categoryLabel}</span>
      </div>

      {/* Title */}
      <h3 className="text-sm font-bold text-text mb-3 leading-relaxed line-clamp-2">{topic.title}</h3>

      {/* Bottom row: stats */}
      <div className="flex items-center gap-4 text-xs text-text-muted">
        <span className="flex items-center gap-1">
          <Users size={13} />
          {topic.queue_count > 0 ? topic.queue_count.toLocaleString() : '0'}
        </span>

        {countdown && (
          <span className="flex items-center gap-1">
            <Clock size={13} />
            {countdown}
          </span>
        )}

        {topic.scheduled_start_at && topic.status === 'scheduled' && (
          <span className="flex items-center gap-1">
            <CalendarClock size={13} />
            {formatScheduleTime(topic.scheduled_start_at)}
          </span>
        )}

        {!countdown && !topic.scheduled_start_at && (
          <span className="flex items-center gap-1">
            <Clock size={13} />
            {getTimeAgo(topic.created_at)}
          </span>
        )}

        {growthPercent && (
          <span className="flex items-center gap-1 ml-auto text-nemo font-medium">
            <TrendingUp size={13} />
            {growthPercent}
          </span>
        )}
      </div>

      {/* Owner actions */}
      {currentUserId && topic.created_by === currentUserId && (
        <div className="mt-3 pt-2 border-t border-border flex gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); e.preventDefault(); onEdit?.(topic); }}
            className="text-xs text-text-muted hover:text-nemo bg-transparent border-none cursor-pointer px-2 py-1 rounded"
          >
            수정
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); e.preventDefault(); onDelete?.(topic.id); }}
            className="text-xs text-text-muted hover:text-red-400 bg-transparent border-none cursor-pointer px-2 py-1 rounded"
          >
            삭제
          </button>
        </div>
      )}
    </Link>
  );
}
