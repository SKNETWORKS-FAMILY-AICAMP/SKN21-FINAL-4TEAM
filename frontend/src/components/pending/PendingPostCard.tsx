'use client';

import { Check, X, Clock, FileText, MessageSquare } from 'lucide-react';
import type { PendingPost } from '@/stores/pendingPostStore';

type Props = {
  pending: PendingPost;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
};

export function PendingPostCard({ pending, onApprove, onReject }: Props) {
  const isPost = pending.content_type === 'post';
  const Icon = isPost ? FileText : MessageSquare;

  return (
    <div className="bg-bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-primary" />
        <span className="text-xs font-semibold text-primary uppercase">
          {isPost ? '게시물' : '댓글'}
        </span>
        <span className="text-xs text-text-muted">
          {pending.persona_display_name || '캐릭터'}
        </span>
        <span className="ml-auto text-xs text-text-muted flex items-center gap-1">
          <Clock size={10} />
          {new Date(pending.created_at).toLocaleString('ko-KR')}
        </span>
      </div>

      {pending.title && (
        <h3 className="text-sm font-bold text-text mb-1">{pending.title}</h3>
      )}

      <div className="bg-bg rounded-lg p-3 mb-3 border border-border/50">
        <p className="text-sm text-text-secondary whitespace-pre-wrap">{pending.content}</p>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">
          토큰: {pending.input_tokens + pending.output_tokens} | 비용: ${pending.cost.toFixed(4)}
        </span>

        {pending.status === 'pending' ? (
          <div className="flex gap-2">
            <button
              onClick={() => onReject(pending.id)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-danger bg-danger/10 border-none cursor-pointer hover:bg-danger/20 transition-colors"
            >
              <X size={12} />
              거절
            </button>
            <button
              onClick={() => onApprove(pending.id)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-primary border-none cursor-pointer hover:opacity-90 transition-opacity"
            >
              <Check size={12} />
              승인
            </button>
          </div>
        ) : (
          <span
            className={`text-xs font-semibold px-2 py-1 rounded ${
              pending.status === 'approved'
                ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700'
            }`}
          >
            {pending.status === 'approved' ? '승인됨' : '거절됨'}
          </span>
        )}
      </div>
    </div>
  );
}
