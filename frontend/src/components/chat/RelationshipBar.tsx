'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Heart, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';

type RelationshipData = {
  affection_level: number;
  relationship_stage: string;
  interaction_count: number;
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

type DeltaPopup = {
  delta: number;
  emotion: string;
  id: number;
};

type Props = {
  personaId: string;
};

export function RelationshipBar({ personaId }: Props) {
  const [data, setData] = useState<RelationshipData | null>(null);
  const [popups, setPopups] = useState<DeltaPopup[]>([]);
  const prevRef = useRef<{ level: number; stage: string } | null>(null);
  const popupIdRef = useRef(0);
  const messages = useChatStore((s) => s.messages);
  const msgCountRef = useRef(0);

  const fetchData = useCallback(() => {
    api
      .get<RelationshipData>(`/relationships/${personaId}`)
      .then((newData) => {
        setData((prev) => {
          if (prev && prevRef.current) {
            const delta = newData.affection_level - prevRef.current.level;
            if (delta !== 0) {
              const lastMsg = messages[messages.length - 1];
              const emotion = lastMsg?.emotionSignal?.label || '';
              const id = ++popupIdRef.current;
              setPopups((p) => [...p, { delta, emotion, id }]);
              setTimeout(() => {
                setPopups((p) => p.filter((x) => x.id !== id));
              }, 3000);
            }
          }
          prevRef.current = { level: newData.affection_level, stage: newData.relationship_stage };
          return newData;
        });
      })
      .catch(() => {});
  }, [personaId, messages]);

  // 초기 로드
  useEffect(() => {
    fetchData();
  }, [personaId]);

  // 메시지가 추가될 때 (AI 응답 완료 후) 호감도 새로고침
  useEffect(() => {
    const assistantMsgs = messages.filter((m) => m.role === 'assistant' && m.content.length > 0);
    if (assistantMsgs.length > msgCountRef.current) {
      msgCountRef.current = assistantMsgs.length;
      // AI 응답 완료 후 약간 딜레이 후 갱신 (백엔드 커밋 대기)
      const timer = setTimeout(fetchData, 1500);
      return () => clearTimeout(timer);
    }
  }, [messages, fetchData]);

  if (!data) return null;

  const percentage = (data.affection_level / 1000) * 100;
  const stageLabel = STAGE_LABELS[data.relationship_stage] || data.relationship_stage;
  const barColor = STAGE_COLORS[data.relationship_stage] || 'bg-primary';

  return (
    <div className="relative">
      <div className="flex items-center gap-2.5 px-4 py-2.5 bg-black/40 backdrop-blur-sm rounded-xl min-w-[180px]">
        <Heart size={20} className="text-red-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-white/80">{stageLabel}</span>
            <span className="text-xs text-white/60 ml-2">{data.affection_level}</span>
          </div>
          <div className="w-full h-2.5 bg-white/20 rounded-full overflow-hidden">
            <div
              className={`h-full ${barColor} rounded-full transition-all duration-700`}
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Delta popups */}
      <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 pointer-events-none">
        {popups.map((popup) => (
          <div
            key={popup.id}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold whitespace-nowrap animate-slide-up ${
              popup.delta > 0
                ? 'bg-pink-500/90 text-white'
                : popup.delta < 0
                  ? 'bg-blue-500/90 text-white'
                  : 'bg-gray-500/90 text-white'
            }`}
          >
            {popup.delta > 0 ? (
              <TrendingUp size={12} />
            ) : popup.delta < 0 ? (
              <TrendingDown size={12} />
            ) : (
              <Minus size={12} />
            )}
            <span>{popup.delta > 0 ? '+' : ''}{popup.delta}</span>
            {popup.emotion && (
              <span className="opacity-80 text-[10px] font-normal ml-0.5">{popup.emotion}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
