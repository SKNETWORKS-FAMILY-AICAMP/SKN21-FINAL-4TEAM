'use client';

import { useEffect, useRef, useState } from 'react';
import { X, MessageCircle, Heart, User } from 'lucide-react';
import { api } from '@/lib/api';
import { AgeRatingBadge } from './AgeRatingBadge';
import { CATEGORIES } from '@/constants/categories';

type CreatorPersona = {
  id: string;
  display_name: string;
  description: string | null;
  category: string | null;
  age_rating: 'all' | '15+' | '18+';
  chat_count: number;
  like_count: number;
  background_image_url: string | null;
};

type CreatorData = {
  creator_nickname: string;
  creator_id: string;
  personas: CreatorPersona[];
  total: number;
};

type Props = {
  creatorId: string;
  onClose: () => void;
  onChat?: (personaId: string) => void;
};

export function CreatorPopup({ creatorId, onClose, onChat }: Props) {
  const [data, setData] = useState<CreatorData | null>(null);
  const [loading, setLoading] = useState(true);
  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get<CreatorData>(`/personas/creator/${creatorId}`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [creatorId]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === backdropRef.current) onClose();
  };

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdrop}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in"
    >
      <div className="bg-bg-surface rounded-2xl w-full max-w-[400px] max-h-[80vh] overflow-hidden shadow-card border border-border">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
              <User size={20} className="text-primary" />
            </div>
            <div>
              <h3 className="m-0 text-base font-semibold text-text">
                {loading ? '...' : data?.creator_nickname ?? '알 수 없음'}
              </h3>
              <p className="m-0 text-xs text-text-muted">
                {loading ? '' : `작품 ${data?.total ?? 0}개`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-bg-hover flex items-center justify-center border-none cursor-pointer text-text-muted hover:text-text transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto p-4 max-h-[60vh]">
          {loading && (
            <div className="flex justify-center py-8">
              <span className="inline-block w-6 h-6 border-2 border-text-muted border-t-primary rounded-full animate-spin" />
            </div>
          )}

          {!loading && (!data || data.personas.length === 0) && (
            <p className="text-center text-text-muted text-sm py-8">공개된 작품이 없습니다</p>
          )}

          {!loading && data && data.personas.length > 0 && (
            <div className="flex flex-col gap-3">
              {data.personas.map((p) => (
                <div
                  key={p.id}
                  className="flex gap-3 p-3 rounded-xl bg-bg-hover/50 hover:bg-bg-hover transition-colors cursor-pointer"
                  onClick={() => onChat?.(p.id)}
                >
                  <div
                    className="w-16 h-16 rounded-lg bg-gradient-to-br from-primary/20 to-secondary/20 bg-cover bg-center shrink-0"
                    style={
                      p.background_image_url
                        ? { backgroundImage: `url(${p.background_image_url})` }
                        : undefined
                    }
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <h4 className="m-0 text-sm font-semibold text-text truncate">
                        {p.display_name}
                      </h4>
                      <AgeRatingBadge rating={p.age_rating} locked={false} />
                    </div>
                    <p className="m-0 text-xs text-text-secondary line-clamp-2 mb-1.5">
                      {p.description || '설명 없음'}
                    </p>
                    <div className="flex items-center gap-3 text-[11px] text-text-muted">
                      {p.category && (
                        <span>{CATEGORIES.find((c) => c.id === p.category)?.label ?? p.category}</span>
                      )}
                      <span className="flex items-center gap-0.5">
                        <MessageCircle size={10} />{p.chat_count}
                      </span>
                      <span className="flex items-center gap-0.5">
                        <Heart size={10} />{p.like_count}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
