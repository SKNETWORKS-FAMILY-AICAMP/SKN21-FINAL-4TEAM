'use client';

import { Heart, MessageCircle, Users, UserPlus, UserMinus } from 'lucide-react';
import { AgeRatingBadge } from '@/components/persona/AgeRatingBadge';
import type { CharacterPage } from '@/stores/characterPageStore';

type Props = {
  page: CharacterPage;
  onFollow: () => void;
  onUnfollow: () => void;
  onChatRequest: () => void;
};

export function CharacterProfileHeader({ page, onFollow, onUnfollow, onChatRequest }: Props) {
  return (
    <div className="relative">
      {/* 배경 이미지 */}
      {page.background_image_url && (
        <div
          className="h-48 bg-cover bg-center rounded-t-xl"
          style={{ backgroundImage: `url(${page.background_image_url})` }}
        />
      )}

      <div className="px-6 pb-6 pt-4">
        {/* 이름 + 배지 */}
        <div className="flex items-center gap-3 mb-2">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-2xl">
            {page.display_name?.charAt(0) || '?'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-text truncate">{page.display_name}</h1>
              <AgeRatingBadge rating={page.age_rating} />
            </div>
            {page.creator_name && (
              <span className="text-xs text-text-muted">@{page.creator_name}</span>
            )}
          </div>
        </div>

        {/* 바이오 */}
        {page.description && (
          <p className="text-sm text-text-secondary mb-3 line-clamp-3">{page.description}</p>
        )}

        {/* 카테고리 + 태그 */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {page.category && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-primary/10 text-primary font-medium">
              {page.category}
            </span>
          )}
          {page.tags?.map((tag) => (
            <span key={tag} className="px-2 py-0.5 rounded-full text-xs bg-bg-hover text-text-muted">
              #{tag}
            </span>
          ))}
        </div>

        {/* 통계 */}
        <div className="flex gap-6 mb-4 text-sm">
          <Stat icon={<MessageCircle size={14} />} value={page.stats.post_count} label="게시물" />
          <Stat icon={<Heart size={14} />} value={page.stats.like_count} label="좋아요" />
          <Stat icon={<Users size={14} />} value={page.stats.follower_count} label="팔로워" />
        </div>

        {/* 액션 버튼 */}
        <div className="flex gap-2">
          {page.is_following ? (
            <button
              onClick={onUnfollow}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-bg-hover text-text-secondary border border-border cursor-pointer hover:bg-danger/10 hover:text-danger hover:border-danger transition-colors"
            >
              <UserMinus size={16} />
              팔로잉
            </button>
          ) : (
            <button
              onClick={onFollow}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-primary text-white border-none cursor-pointer hover:opacity-90 transition-opacity"
            >
              <UserPlus size={16} />
              팔로우
            </button>
          )}
          <button
            onClick={onChatRequest}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-bg-hover text-text border border-border cursor-pointer hover:bg-primary/10 hover:text-primary hover:border-primary transition-colors"
          >
            <MessageCircle size={16} />
            1:1 대화 요청
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ icon, value, label }: { icon: React.ReactNode; value: number; label: string }) {
  return (
    <div className="flex items-center gap-1 text-text-secondary">
      {icon}
      <span className="font-bold text-text">{value}</span>
      <span>{label}</span>
    </div>
  );
}
