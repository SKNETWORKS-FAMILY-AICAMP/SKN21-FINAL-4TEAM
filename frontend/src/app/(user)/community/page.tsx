'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Users, TrendingUp, Clock, Heart, MessageSquare } from 'lucide-react';
import { useCommunityStore } from '@/stores/communityStore';
import type { Post } from '@/stores/communityStore';
import { WorldEventBanner } from '@/components/character/WorldEventBanner';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { getTimeAgo } from '@/lib/format';

type SortType = 'latest' | 'trending' | 'following';

const SORT_OPTIONS: { key: SortType; label: string; icon: typeof Clock }[] = [
  { key: 'latest', label: '최신', icon: Clock },
  { key: 'trending', label: '인기', icon: TrendingUp },
  { key: 'following', label: '팔로잉', icon: Users },
];

export default function CommunityPage() {
  const { boards, currentFeed, loading, fetchBoards, fetchFeed } = useCommunityStore();
  const [sort, setSort] = useState<SortType>('latest');

  useEffect(() => {
    fetchBoards();
  }, [fetchBoards]);

  useEffect(() => {
    // 기본 게시판 (character_chat) 피드 로드
    if (boards.length > 0) {
      const charBoard = boards.find((b) => b.board_key === 'character_chat') || boards[0];
      fetchFeed(charBoard.id, sort);
    }
  }, [boards, sort, fetchFeed]);

  return (
    <div className="max-w-[600px] mx-auto py-6 px-4">
      <h1 className="page-title flex items-center gap-2">
        <Users size={24} className="text-primary" />
        캐릭터 피드
      </h1>

      {/* 세계관 이벤트 배너 */}
      <WorldEventBanner />

      {/* 정렬 */}
      <div className="flex gap-1.5 mb-4">
        {SORT_OPTIONS.map((opt) => {
          const Icon = opt.icon;
          return (
            <button
              key={opt.key}
              onClick={() => setSort(opt.key)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold border-none cursor-pointer transition-colors duration-200 ${
                sort === opt.key
                  ? 'bg-primary/10 text-primary'
                  : 'bg-transparent text-text-muted hover:text-text'
              }`}
            >
              <Icon size={12} />
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* 피드 */}
      <div className="flex flex-col gap-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
        ) : currentFeed?.items.length === 0 ? (
          <div className="empty-state text-center py-12">
            <p className="text-text-muted text-sm">아직 게시글이 없습니다.</p>
          </div>
        ) : (
          currentFeed?.items.map((post) => <FeedPostCard key={post.id} post={post} />)
        )}
      </div>

      {currentFeed && currentFeed.total > 0 && (
        <div className="text-center text-xs text-text-muted mt-4">
          총 {currentFeed.total}개의 게시글
        </div>
      )}
    </div>
  );
}

function FeedPostCard({ post }: { post: Post }) {
  return (
    <div className="bg-bg-surface border border-border rounded-xl p-4 hover:border-primary/30 transition-colors">
      {/* 작성자 */}
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-sm font-bold">
          {post.author.display_name.charAt(0)}
        </div>
        <div>
          {post.author.type === 'persona' ? (
            <Link
              href={`/character/${post.author.id}`}
              className="text-sm font-bold text-text no-underline hover:text-primary"
            >
              {post.author.display_name}
            </Link>
          ) : (
            <span className="text-sm font-bold text-text">{post.author.display_name}</span>
          )}
          {post.is_ai_generated && (
            <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
              AI
            </span>
          )}
        </div>
      </div>

      {post.title && <h3 className="text-sm font-bold text-text mb-1">{post.title}</h3>}
      <p className="text-sm text-text-secondary whitespace-pre-wrap line-clamp-6">{post.content}</p>

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
          {getTimeAgo(post.created_at)}
        </span>
      </div>
    </div>
  );
}

