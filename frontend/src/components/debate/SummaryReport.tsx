'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Loader2, FileText, Trophy, AlertTriangle } from 'lucide-react';

type SummaryData = {
  status: 'ready' | 'generating' | 'unavailable';
  key_arguments?: string[];
  winning_points?: string[];
  rule_violations?: string[];
  overall_summary?: string;
  generated_at?: string;
  model_used?: string;
};

type Props = { matchId: string };

export function SummaryReport({ matchId }: Props) {
  const [data, setData] = useState<SummaryData | null>(null);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    const fetchSummary = async () => {
      try {
        const result = await api.get<SummaryData>(`/matches/${matchId}/summary`);
        setData(result);
        if (result.status === 'ready' || result.status === 'unavailable') {
          if (interval) clearInterval(interval);
        }
      } catch {
        /* ignore */
      }
    };
    fetchSummary();
    interval = setInterval(fetchSummary, 5000);
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [matchId]);

  if (!data) return null;
  if (data.status === 'unavailable') return null;
  if (data.status === 'generating') {
    return (
      <div className="mt-6 bg-bg-surface border border-border rounded-2xl p-6">
        <div className="flex items-center gap-3 text-text-muted">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-sm">AI가 토론을 분석하고 있습니다...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6 bg-bg-surface border border-border rounded-2xl p-6 space-y-5">
      <div className="flex items-center gap-2">
        <FileText size={18} className="text-primary" />
        <h3 className="font-semibold text-text">AI 토론 요약 리포트</h3>
        {data.model_used && (
          <span className="text-xs text-text-muted ml-auto">{data.model_used}</span>
        )}
      </div>

      {data.overall_summary && (
        <p className="text-sm text-text leading-relaxed border-b border-border pb-4">
          {data.overall_summary}
        </p>
      )}

      {(data.key_arguments?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">
            핵심 논거
          </h4>
          <ul className="space-y-1">
            {data.key_arguments!.map((arg, i) => (
              <li key={i} className="text-sm text-text flex gap-2">
                <span className="text-primary shrink-0">•</span>
                {arg}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(data.winning_points?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Trophy size={12} className="text-yellow-400" /> 승부 포인트
          </h4>
          <ul className="space-y-1">
            {data.winning_points!.map((point, i) => (
              <li key={i} className="text-sm text-text flex gap-2">
                <span className="text-yellow-400 shrink-0">★</span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(data.rule_violations?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <AlertTriangle size={12} className="text-red-400" /> 규칙 위반
          </h4>
          <ul className="space-y-1">
            {data.rule_violations!.map((v, i) => (
              <li key={i} className="text-sm text-red-400/80 flex gap-2">
                <span className="shrink-0">!</span>
                {v}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
