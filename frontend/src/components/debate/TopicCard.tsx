'use client';

import Link from 'next/link';
import { MessageSquare, Users, Clock } from 'lucide-react';
import type { DebateTopic } from '@/stores/debateStore';
import { getTimeAgo } from '@/lib/format';

type Props = { topic: DebateTopic };

const STATUS_STYLES: Record<string, string> = {
  open: 'bg-green-500/10 text-green-500',
  in_progress: 'bg-yellow-500/10 text-yellow-500',
  closed: 'bg-text-muted/10 text-text-muted',
};

const STATUS_LABELS: Record<string, string> = {
  open: '참가 가능',
  in_progress: '진행 중',
  closed: '종료',
};

const MODE_LABELS: Record<string, string> = {
  debate: '토론',
  persuasion: '설득',
  cross_exam: '교차 심문',
};

export function TopicCard({ topic }: Props) {
  return (
    <Link
      href={`/debate/topics/${topic.id}`}
      className="block bg-bg-surface border border-border rounded-xl p-4 hover:border-primary/30 transition-colors no-underline"
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-sm font-bold text-text flex-1 mr-2">{topic.title}</h3>
        <span
          className={`text-[11px] px-2 py-0.5 rounded-full font-semibold whitespace-nowrap ${
            STATUS_STYLES[topic.status] || STATUS_STYLES.closed
          }`}
        >
          {STATUS_LABELS[topic.status] || topic.status}
        </span>
      </div>

      {topic.description && (
        <p className="text-xs text-text-secondary mb-3 line-clamp-2">{topic.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-text-muted">
        <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
          {MODE_LABELS[topic.mode] || topic.mode}
        </span>
        <span className="flex items-center gap-1">
          <Users size={12} />
          대기 {topic.queue_count}명
        </span>
        <span className="flex items-center gap-1">
          <MessageSquare size={12} />
          매치 {topic.match_count}
        </span>
        <span className="flex items-center gap-1">
          <Clock size={12} />
          {getTimeAgo(topic.created_at)}
        </span>
      </div>
    </Link>
  );
}
