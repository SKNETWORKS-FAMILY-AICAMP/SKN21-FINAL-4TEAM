type Props = {
  rating: 'all' | '15+' | '18+';
  locked?: boolean;
};

const BADGE_STYLES: Record<string, { color: string; bg: string }> = {
  all: { color: '#166534', bg: '#dcfce7' },
  '15+': { color: '#854d0e', bg: '#fef9c3' },
  '18+': { color: '#991b1b', bg: '#fee2e2' },
};

const LABELS: Record<string, string> = {
  all: '전체',
  '15+': '15+',
  '18+': '18+',
};

export function AgeRatingBadge({ rating, locked = false }: Props) {
  const style = BADGE_STYLES[rating];
  return (
    <span
      style={{
        color: style.color,
        backgroundColor: style.bg,
        padding: '2px 8px',
        borderRadius: '4px',
        fontSize: '12px',
        fontWeight: 'bold',
        opacity: locked ? 0.5 : 1,
      }}
    >
      [{LABELS[rating]}] {locked && '🔒'}
    </span>
  );
}
