/** 연령등급 배지 (전체/15+/18+). locked=true 시 잠금 아이콘 표시. */
import { memo } from 'react';

type Props = {
  rating: 'all' | '15+' | '18+';
  locked?: boolean;
};

const BADGE_CLASSES: Record<string, string> = {
  all: 'text-green-400 bg-green-900/30',
  '15+': 'text-yellow-400 bg-yellow-900/30',
  '18+': 'text-red-400 bg-red-900/30',
};

const LABELS: Record<string, string> = {
  all: '전체',
  '15+': '15+',
  '18+': '18+',
};

export const AgeRatingBadge = memo(function AgeRatingBadge({ rating, locked = false }: Props) {
  return (
    <span
      className={`${BADGE_CLASSES[rating]} px-2 py-0.5 rounded text-xs font-bold ${locked ? 'opacity-50' : 'opacity-100'}`}
    >
      [{LABELS[rating]}] {locked && '🔒'}
    </span>
  );
});
