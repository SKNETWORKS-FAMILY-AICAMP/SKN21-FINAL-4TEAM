'use client';

import { useEffect, useState } from 'react';
import { BarChart3, MessageCircle, Heart } from 'lucide-react';
import { api } from '@/lib/api';

type PersonaStat = {
  persona_id: string;
  display_name: string;
  chat_count: number;
  like_count: number;
  age_rating: string;
  visibility: string;
  moderation_status: string;
  created_at: string;
};

export function CreatorTab() {
  const [stats, setStats] = useState<PersonaStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<{ personas: PersonaStat[]; total: number }>('/personas/my/stats')
      .then((res) => setStats(res.personas ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const totalChats = stats.reduce((sum, s) => sum + s.chat_count, 0);
  const totalLikes = stats.reduce((sum, s) => sum + s.like_count, 0);

  return (
    <div>
      {/* Summary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
        <div className="bg-bg-hover rounded-xl p-4 text-center">
          <BarChart3 size={20} className="text-primary mx-auto mb-1" />
          <div className="text-xl font-bold text-text">{stats.length}</div>
          <div className="text-xs text-text-muted">내 캐릭터</div>
        </div>
        <div className="bg-bg-hover rounded-xl p-4 text-center">
          <MessageCircle size={20} className="text-success mx-auto mb-1" />
          <div className="text-xl font-bold text-text">{totalChats}</div>
          <div className="text-xs text-text-muted">총 대화</div>
        </div>
        <div className="bg-bg-hover rounded-xl p-4 text-center">
          <Heart size={20} className="text-red-400 mx-auto mb-1" />
          <div className="text-xl font-bold text-text">{totalLikes}</div>
          <div className="text-xs text-text-muted">총 좋아요</div>
        </div>
      </div>

      {/* Per-persona stats */}
      <h3 className="text-sm font-semibold text-text mb-3">캐릭터별 통계</h3>
      <div className="flex flex-col gap-3">
        {stats.map((s) => (
          <div
            key={s.persona_id}
            className="flex items-center justify-between p-4 rounded-xl border border-border bg-bg-surface"
          >
            <div>
              <h4 className="m-0 text-sm font-semibold text-text">{s.display_name || '이름 없음'}</h4>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-xs text-text-muted flex items-center gap-1">
                  <MessageCircle size={11} /> {s.chat_count}
                </span>
                <span className="text-xs text-text-muted flex items-center gap-1">
                  <Heart size={11} /> {s.like_count}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  s.moderation_status === 'approved' ? 'bg-green-100 text-green-700' :
                  s.moderation_status === 'blocked' ? 'bg-red-100 text-red-700' :
                  'bg-yellow-100 text-yellow-700'
                }`}>
                  {s.moderation_status === 'approved' ? '승인' : s.moderation_status === 'blocked' ? '차단' : '심사중'}
                </span>
              </div>
            </div>
            <span className="text-xs text-text-muted">
              {new Date(s.created_at).toLocaleDateString('ko-KR')}
            </span>
          </div>
        ))}
        {stats.length === 0 && !loading && (
          <p className="text-sm text-text-muted text-center py-8">만든 캐릭터가 없습니다</p>
        )}
      </div>
    </div>
  );
}
