'use client';

import Link from 'next/link';
import { MessageSquare, Pin, Bot } from 'lucide-react';
import type { Post } from '@/stores/communityStore';
import { PersonaAvatar } from './PersonaAvatar';
import { ReactionButton } from './ReactionButton';

type Props = {
  post: Post;
};

export function PostCard({ post }: Props) {
  const timeAgo = formatTimeAgo(post.created_at);

  return (
    <div className="card p-4 hover:bg-bg-hover/50 transition-colors duration-200">
      <Link href={`/community/post/${post.id}`} className="no-underline text-text block">
        <div className="flex items-start gap-3">
          <PersonaAvatar type={post.author.type} displayName={post.author.display_name} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-semibold text-text">{post.author.display_name}</span>
              {post.is_ai_generated && (
                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-semibold">
                  <Bot size={10} />
                  AI
                </span>
              )}
              {post.is_pinned && <Pin size={12} className="text-warning" />}
              <span className="text-xs text-text-muted">{timeAgo}</span>
            </div>

            {post.title && (
              <h3 className="text-[15px] font-semibold text-text mb-1 line-clamp-1">
                {post.title}
              </h3>
            )}
            <p className="text-sm text-text-secondary line-clamp-2 mb-2">{post.content}</p>
          </div>
        </div>
      </Link>

      <div className="flex items-center gap-3 mt-2 pl-12">
        <ReactionButton postId={post.id} count={post.reaction_count} myReaction={post.my_reaction} />
        <div className="flex items-center gap-1 text-xs text-text-muted">
          <MessageSquare size={12} />
          <span>{post.comment_count}</span>
        </div>
      </div>
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
