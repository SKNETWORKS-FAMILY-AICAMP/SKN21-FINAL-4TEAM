'use client';

import { useCallback, useEffect, useRef } from 'react';
import { Clock, Heart, MessageSquare } from 'lucide-react';
import type { CharacterPost } from '@/stores/characterPageStore';
import { getTimeAgo } from '@/lib/format';

type Props = {
  posts: CharacterPost[];
  total: number;
  onLoadMore: () => void;
  loading?: boolean;
};

export function CharacterPostFeed({ posts, total, onLoadMore, loading }: Props) {
  const observerRef = useRef<HTMLDivElement>(null);

  // 무한 스크롤
  useEffect(() => {
    const el = observerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && posts.length < total && !loading) {
          onLoadMore();
        }
      },
      { threshold: 0.5 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [posts.length, total, loading, onLoadMore]);

  if (posts.length === 0) {
    return (
      <div className="text-center py-12 text-text-muted text-sm">
        아직 게시물이 없습니다.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {posts.map((post) => (
        <PostItem key={post.id} post={post} />
      ))}
      <div ref={observerRef} className="h-4" />
      {loading && (
        <div className="text-center py-4 text-text-muted text-sm">불러오는 중...</div>
      )}
    </div>
  );
}

function PostItem({ post }: { post: CharacterPost }) {
  const timeAgo = getTimeAgo(post.created_at);

  return (
    <div className="bg-bg-surface border border-border rounded-xl p-4 hover:border-primary/30 transition-colors">
      {post.title && <h3 className="text-sm font-bold text-text mb-1">{post.title}</h3>}
      <p className="text-sm text-text-secondary whitespace-pre-wrap line-clamp-6">
        {post.content}
      </p>
      <div className="flex items-center gap-4 mt-3 text-xs text-text-muted">
        <span className="flex items-center gap-1">
          <Heart size={12} />
          {post.reaction_count}
        </span>
        <span className="flex items-center gap-1">
          <MessageSquare size={12} />
          {post.comment_count}
        </span>
        <span className="flex items-center gap-1">
          <Clock size={12} />
          {timeAgo}
        </span>
      </div>
    </div>
  );
}

