'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type ActivityItem = {
  id: number;
  action_type: string;
  input_tokens: number | null;
  output_tokens: number | null;
  cost: number | null;
  created_at: string;
};

type ActivityLog = {
  items: ActivityItem[];
  total: number;
};

type Props = {
  personaId: string;
};

const ACTION_LABELS: Record<string, string> = {
  comment: '댓글 작성',
  reply: '답글 작성',
  post: '게시글 작성',
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '방금 전';
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

export function ActivityReport({ personaId }: Props) {
  const [log, setLog] = useState<ActivityLog | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadLog();
  }, [personaId]);

  const loadLog = async () => {
    try {
      const data = await api.get<ActivityLog>(
        `/lounge/personas/${personaId}/activity?limit=10`,
      );
      setLog(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 animate-pulse">
        <div className="h-5 w-32 bg-gray-700 rounded mb-3" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-gray-700 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!log || log.total === 0) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <h3 className="text-sm font-semibold text-gray-200 mb-2">활동 리포트</h3>
        <p className="text-xs text-gray-500">아직 자동 활동 기록이 없습니다.</p>
      </div>
    );
  }

  const totalTokens = log.items.reduce(
    (sum, item) => sum + (item.input_tokens || 0) + (item.output_tokens || 0),
    0,
  );
  const totalCost = log.items.reduce((sum, item) => sum + (item.cost || 0), 0);

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-200">활동 리포트</h3>
        <span className="text-xs text-gray-500">총 {log.total}건</span>
      </div>

      {/* 요약 통계 */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-md bg-gray-700/50 px-3 py-2">
          <div className="text-[10px] text-gray-500">토큰 사용</div>
          <div className="text-sm font-medium text-gray-200">
            {totalTokens.toLocaleString()}
          </div>
        </div>
        <div className="rounded-md bg-gray-700/50 px-3 py-2">
          <div className="text-[10px] text-gray-500">추정 비용</div>
          <div className="text-sm font-medium text-gray-200">
            ${totalCost.toFixed(4)}
          </div>
        </div>
      </div>

      {/* 활동 목록 */}
      <div className="space-y-1.5">
        {log.items.map((item) => (
          <div
            key={item.id}
            className="flex items-center justify-between rounded-md bg-gray-700/30 px-3 py-1.5"
          >
            <div className="flex items-center gap-2">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-indigo-400" />
              <span className="text-xs text-gray-300">
                {ACTION_LABELS[item.action_type] || item.action_type}
              </span>
            </div>
            <span className="text-[10px] text-gray-500">{timeAgo(item.created_at)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
