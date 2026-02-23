'use client';

import type { Comment } from '@/stores/communityStore';
import { PersonaAvatar } from './PersonaAvatar';
import { ReactionButton } from './ReactionButton';

type Props = {
  comments: Comment[];
  depth?: number;
  onReply?: (commentId: string) => void;
};

export function CommentTree({ comments, depth = 0, onReply }: Props) {
  return (
    <div className={depth > 0 ? 'ml-8 border-l-2 border-border/50 pl-4' : ''}>
      {comments.map((comment) => (
        <div key={comment.id} className="py-3">
          <div className="flex items-start gap-2.5">
            <PersonaAvatar
              type={comment.author.type}
              displayName={comment.author.display_name}
              size="sm"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-semibold text-text">
                  {comment.author.display_name}
                </span>
                {comment.is_ai_generated && (
                  <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-semibold">
                    AI
                  </span>
                )}
                <span className="text-xs text-text-muted">
                  {formatTimeAgo(comment.created_at)}
                </span>
              </div>
              <p className="text-sm text-text-secondary mb-1.5">{comment.content}</p>
              <div className="flex items-center gap-2">
                <ReactionButton
                  commentId={comment.id}
                  count={comment.reaction_count}
                  myReaction={comment.my_reaction}
                />
                {depth < 3 && onReply && (
                  <button
                    onClick={() => onReply(comment.id)}
                    className="text-xs text-text-muted hover:text-primary bg-transparent border-none cursor-pointer"
                  >
                    답글
                  </button>
                )}
              </div>
            </div>
          </div>

          {comment.children.length > 0 && (
            <CommentTree comments={comment.children} depth={depth + 1} onReply={onReply} />
          )}
        </div>
      ))}
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}일 전`;
  return new Date(dateStr).toLocaleDateString('ko-KR');
}
