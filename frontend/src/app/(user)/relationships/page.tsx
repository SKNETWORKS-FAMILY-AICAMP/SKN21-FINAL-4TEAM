'use client';

import { useEffect, useState } from 'react';
import { Heart } from 'lucide-react';
import { api } from '@/lib/api';
import { EmptyState } from '@/components/ui/EmptyState';

type Relationship = {
  id: string;
  persona_id: string;
  affection_level: number;
  relationship_stage: string;
  interaction_count: number;
  last_interaction_at: string | null;
};

const STAGE_LABELS: Record<string, string> = {
  stranger: '낯선 사이',
  acquaintance: '아는 사이',
  friend: '친구',
  close_friend: '절친',
  crush: '썸',
  lover: '연인',
  soulmate: '소울메이트',
};

const STAGE_COLORS: Record<string, string> = {
  stranger: 'bg-gray-400',
  acquaintance: 'bg-blue-400',
  friend: 'bg-green-400',
  close_friend: 'bg-emerald-400',
  crush: 'bg-pink-400',
  lover: 'bg-red-400',
  soulmate: 'bg-amber-400',
};

export default function RelationshipsPage() {
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Relationship[]>('/relationships/')
      .then(setRelationships)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-[1000px] mx-auto py-6 px-4">
      <h1 className="m-0 text-2xl text-text mb-6 flex items-center gap-2">
        <Heart size={24} className="text-pink-400" />
        관계도
      </h1>

      {!loading && relationships.length === 0 && (
        <EmptyState
          icon={<Heart size={48} />}
          title="아직 관계가 없습니다"
          description="캐릭터와 대화하면 관계가 쌓여요"
        />
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
        {relationships.map((rel) => {
          const pct = (rel.affection_level / 1000) * 100;
          const label = STAGE_LABELS[rel.relationship_stage] || rel.relationship_stage;
          const barColor = STAGE_COLORS[rel.relationship_stage] || 'bg-primary';

          return (
            <div
              key={rel.id}
              className="bg-bg-surface rounded-xl p-5 border border-border hover:border-primary/30 transition-colors"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="m-0 text-sm font-semibold text-text">{rel.persona_id.slice(0, 8)}...</h3>
                <span className="text-xs font-medium text-primary">{label}</span>
              </div>

              <div className="mb-3">
                <div className="flex justify-between text-[11px] text-text-muted mb-1">
                  <span>호감도</span>
                  <span>{rel.affection_level}/1000</span>
                </div>
                <div className="w-full h-2 bg-bg-hover rounded-full overflow-hidden">
                  <div
                    className={`h-full ${barColor} rounded-full transition-all duration-500`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>

              <div className="flex justify-between text-[11px] text-text-muted">
                <span>대화 {rel.interaction_count}회</span>
                {rel.last_interaction_at && (
                  <span>최근: {new Date(rel.last_interaction_at).toLocaleDateString('ko-KR')}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
