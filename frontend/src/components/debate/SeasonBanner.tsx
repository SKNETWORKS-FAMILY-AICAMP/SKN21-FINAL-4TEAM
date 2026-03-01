'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Calendar } from 'lucide-react';

type Season = {
  id: string;
  season_number: number;
  title: string;
  start_at: string;
  end_at: string;
  status: string;
};

export function SeasonBanner() {
  const [season, setSeason] = useState<Season | null>(null);

  useEffect(() => {
    api
      .get<{ season: Season | null }>('/agents/season/current')
      .then((data) => setSeason(data.season))
      .catch(() => {});
  }, []);

  if (!season) return null;

  const endDate = new Date(season.end_at);
  const daysLeft = Math.max(0, Math.ceil((endDate.getTime() - Date.now()) / 86400000));

  return (
    <Link
      href={`/debate/seasons/${season.id}`}
      className="flex items-center gap-3 bg-primary/10 border border-primary/30 rounded-xl px-4 py-3 mb-4 hover:bg-primary/15 transition-colors"
    >
      <Calendar size={16} className="text-primary shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-text">
          시즌 {season.season_number}: {season.title}
        </div>
        <div className="text-xs text-text-muted">
          종료까지 {daysLeft}일 남음 · {endDate.toLocaleDateString('ko-KR')}
        </div>
      </div>
      <span className="text-xs text-primary shrink-0">순위 보기 →</span>
    </Link>
  );
}
