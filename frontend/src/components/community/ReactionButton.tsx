'use client';

import { useState } from 'react';
import { Heart } from 'lucide-react';
import { api } from '@/lib/api';

type Props = {
  postId?: string;
  commentId?: string;
  count: number;
  myReaction: string | null;
  onUpdate?: (toggled: boolean, newCount: number) => void;
};

export function ReactionButton({ postId, commentId, count, myReaction, onUpdate }: Props) {
  const [reactionCount, setReactionCount] = useState(count);
  const [active, setActive] = useState(myReaction !== null);
  const [loading, setLoading] = useState(false);

  const handleToggle = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const url = postId
        ? `/board/posts/${postId}/reactions`
        : `/board/comments/${commentId}/reactions`;
      const result = await api.post<{ toggled: boolean; new_count: number }>(url, {
        reaction_type: 'like',
      });
      setActive(result.toggled);
      setReactionCount(result.new_count);
      onUpdate?.(result.toggled, result.new_count);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleToggle}
      disabled={loading}
      className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs border transition-colors duration-200 cursor-pointer ${
        active
          ? 'bg-danger/10 border-danger/30 text-danger'
          : 'bg-transparent border-border text-text-muted hover:border-danger/30 hover:text-danger'
      }`}
    >
      <Heart size={12} fill={active ? 'currentColor' : 'none'} />
      <span>{reactionCount}</span>
    </button>
  );
}
