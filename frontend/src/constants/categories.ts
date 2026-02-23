export const CATEGORIES = [
  { id: 'romance', label: '로맨스' },
  { id: 'action', label: '액션' },
  { id: 'fantasy', label: '판타지' },
  { id: 'daily', label: '일상/힐링' },
  { id: 'horror', label: '공포/스릴러' },
  { id: 'comedy', label: '코미디' },
  { id: 'drama', label: '드라마' },
  { id: 'scifi', label: 'SF' },
] as const;

export type CategoryId = (typeof CATEGORIES)[number]['id'];
