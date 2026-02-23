'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Heart, MessageCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { useUserStore } from '@/stores/userStore';
import { AgeRatingBadge } from '@/components/persona/AgeRatingBadge';
import { CATEGORIES } from '@/constants/categories';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { toast } from '@/stores/toastStore';

type FavoriteItem = {
  id: string;
  persona_id: string;
  created_at: string;
  persona_display_name: string;
  persona_description: string | null;
  persona_age_rating: 'all' | '15+' | '18+';
  persona_background_image_url: string | null;
  persona_chat_count: number;
  persona_like_count: number;
  persona_tags: string[] | null;
  persona_category: string | null;
};

export default function FavoritesPage() {
  const router = useRouter();
  const { isAdultVerified } = useUserStore();
  const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ items: FavoriteItem[]; total: number }>('/favorites')
      .then((res) => setFavorites(res.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleRemoveFavorite = async (personaId: string) => {
    if (removing) return;
    setRemoving(personaId);
    try {
      await api.delete(`/favorites/${personaId}`);
      setFavorites((prev) => prev.filter((f) => f.persona_id !== personaId));
      toast.success('즐겨찾기에서 제거됨');
    } catch {
      toast.error('제거 실패');
    } finally {
      setRemoving(null);
    }
  };

  const handleStartChat = async (personaId: string) => {
    try {
      const session = await api.post<{ id: string }>('/chat/sessions', { persona_id: personaId });
      router.push(`/chat/${session.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '세션 생성 실패';
      toast.error(message);
    }
  };

  return (
    <div className="max-w-[1000px] mx-auto py-6 px-4">
      <h1 className="m-0 text-2xl text-text mb-6 flex items-center gap-2">
        <Heart size={24} className="text-danger" />
        즐겨찾기
      </h1>

      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {!loading && favorites.length === 0 && (
        <EmptyState
          icon={<Heart size={48} />}
          title="즐겨찾기가 비어있습니다"
          description="마음에 드는 캐릭터에 하트를 눌러보세요"
        />
      )}

      {!loading && favorites.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {favorites.map((fav) => {
            const locked = fav.persona_age_rating === '18+' && !isAdultVerified();
            return (
              <div
                key={fav.id}
                className={`bg-bg-surface rounded-xl overflow-hidden border border-border transition-all duration-200 hover:border-primary hover:shadow-glow group ${
                  locked ? 'opacity-60' : ''
                }`}
              >
                {/* 배경 이미지 영역 */}
                <div
                  className="h-[120px] bg-gradient-to-br from-primary/20 to-secondary/20 bg-cover bg-center relative"
                  style={
                    fav.persona_background_image_url
                      ? { backgroundImage: `url(${fav.persona_background_image_url})` }
                      : undefined
                  }
                >
                  <div className="absolute top-3 right-3">
                    <AgeRatingBadge rating={fav.persona_age_rating} locked={locked} />
                  </div>
                </div>

                <div className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="m-0 text-[15px] font-semibold text-text">
                      {fav.persona_display_name}
                    </h3>
                    <button
                      onClick={() => handleRemoveFavorite(fav.persona_id)}
                      disabled={removing === fav.persona_id}
                      className={`p-1.5 rounded-lg border-none cursor-pointer transition-colors duration-200 ${
                        removing === fav.persona_id
                          ? 'opacity-50 pointer-events-none'
                          : 'hover:bg-bg-hover'
                      } text-danger bg-transparent`}
                      title="즐겨찾기 해제"
                    >
                      <Heart size={16} fill="currentColor" />
                    </button>
                  </div>

                  {fav.persona_description && (
                    <p className="text-[13px] text-text-secondary leading-relaxed mb-3 line-clamp-2">
                      {fav.persona_description}
                    </p>
                  )}

                  <div className="flex gap-1 mb-2 flex-wrap">
                    {fav.persona_category && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
                        {CATEGORIES.find(c => c.id === fav.persona_category)?.label ?? fav.persona_category}
                      </span>
                    )}
                    {fav.persona_tags?.slice(0, 3).map(tag => (
                      <span key={tag} className="text-[11px] px-1.5 py-0.5 rounded bg-bg-hover text-text-muted">#{tag}</span>
                    ))}
                  </div>

                  <div className="flex items-center gap-3 mb-3 text-xs text-text-muted">
                    <span className="flex items-center gap-1">
                      <MessageCircle size={12} />{fav.persona_chat_count}
                    </span>
                    <span className="flex items-center gap-1 text-danger">
                      <Heart size={12} fill="currentColor" />{fav.persona_like_count}
                    </span>
                  </div>

                  <button
                    onClick={() => handleStartChat(fav.persona_id)}
                    disabled={locked}
                    className={`flex items-center gap-1.5 py-2 px-4 border-none rounded-lg bg-primary text-white text-[13px] font-semibold w-full justify-center ${
                      locked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-primary-dark'
                    }`}
                  >
                    <MessageCircle size={14} />
                    {locked ? '성인인증 필요' : '대화하기'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
