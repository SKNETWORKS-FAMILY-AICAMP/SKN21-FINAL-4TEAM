/** 캐릭터 라운지 참여 설정. 활동 수준(조용/보통/활발) + 관심 태그 관리. */
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useToastStore } from '@/stores/toastStore';

type LoungeConfig = {
  persona_id: string;
  is_active: boolean;
  activity_level: string;
  interest_tags: string[];
  daily_action_limit: number;
  actions_today: number;
};

type Props = {
  personaId: string;
};

const ACTIVITY_LEVELS = [
  { value: 'quiet', label: '조용', desc: '가끔 반응 (확률 20%)' },
  { value: 'normal', label: '보통', desc: '적절히 반응 (확률 50%)' },
  { value: 'active', label: '활발', desc: '적극 반응 + 자발적 글 작성 (확률 80%)' },
];

export function PersonaLoungeSettings({ personaId }: Props) {
  const [config, setConfig] = useState<LoungeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const { addToast } = useToastStore();

  useEffect(() => {
    loadConfig();
  }, [personaId]);

  const loadConfig = async () => {
    try {
      const data = await api.get<LoungeConfig>(`/lounge/personas/${personaId}/config`);
      setConfig(data);
    } catch {
      // 설정이 없으면 기본값으로 생성됨
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async () => {
    if (!config) return;
    try {
      const endpoint = config.is_active ? 'deactivate' : 'activate';
      const data = await api.post<LoungeConfig>(`/lounge/personas/${personaId}/${endpoint}`);
      setConfig(data);
      addToast('success', config.is_active ? '라운지 참여를 중단했습니다' : '라운지 참여를 시작했습니다');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '변경에 실패했습니다';
      addToast('error', message);
    }
  };

  const handleLevelChange = async (level: string) => {
    if (!config) return;
    setSaving(true);
    try {
      const data = await api.put<LoungeConfig>(`/lounge/personas/${personaId}/config`, {
        activity_level: level,
        interest_tags: config.interest_tags,
      });
      setConfig(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '변경에 실패했습니다';
      addToast('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleAddTag = async () => {
    if (!config || !tagInput.trim()) return;
    const newTags = [...config.interest_tags, tagInput.trim()];
    setSaving(true);
    try {
      const data = await api.put<LoungeConfig>(`/lounge/personas/${personaId}/config`, {
        activity_level: config.activity_level,
        interest_tags: newTags,
      });
      setConfig(data);
      setTagInput('');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '변경에 실패했습니다';
      addToast('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveTag = async (tag: string) => {
    if (!config) return;
    const newTags = config.interest_tags.filter((t) => t !== tag);
    setSaving(true);
    try {
      const data = await api.put<LoungeConfig>(`/lounge/personas/${personaId}/config`, {
        activity_level: config.activity_level,
        interest_tags: newTags,
      });
      setConfig(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '변경에 실패했습니다';
      addToast('error', message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 animate-pulse">
        <div className="h-5 w-40 bg-gray-700 rounded mb-4" />
        <div className="h-10 w-full bg-gray-700 rounded" />
      </div>
    );
  }

  if (!config) return null;

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-200">캐릭터 라운지 참여</h3>
        <button
          onClick={handleToggle}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            config.is_active ? 'bg-indigo-600' : 'bg-gray-600'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              config.is_active ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {config.is_active && (
        <>
          <p className="text-xs text-gray-400">
            이 캐릭터가 커뮤니티 게시판에서 자동으로 게시글에 반응하고 댓글을 남깁니다.
            오늘 활동: {config.actions_today}/{config.daily_action_limit}회
          </p>

          {/* 활동 레벨 */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-300">활동 수준</label>
            <div className="grid grid-cols-3 gap-2">
              {ACTIVITY_LEVELS.map((level) => (
                <button
                  key={level.value}
                  onClick={() => handleLevelChange(level.value)}
                  disabled={saving}
                  className={`rounded-md border px-3 py-2 text-xs transition-colors ${
                    config.activity_level === level.value
                      ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300'
                      : 'border-gray-600 bg-gray-700/50 text-gray-400 hover:border-gray-500'
                  }`}
                >
                  <div className="font-medium">{level.label}</div>
                  <div className="mt-0.5 text-[10px] opacity-70">{level.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 관심 태그 */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-300">관심 태그</label>
            <div className="flex flex-wrap gap-1.5">
              {config.interest_tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 rounded-full bg-gray-700 px-2.5 py-0.5 text-xs text-gray-300"
                >
                  {tag}
                  <button
                    onClick={() => handleRemoveTag(tag)}
                    className="text-gray-500 hover:text-gray-300"
                  >
                    &times;
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
                placeholder="태그 추가 (예: 웹툰, 리뷰)"
                className="flex-1 rounded-md border border-gray-600 bg-gray-700/50 px-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
              />
              <button
                onClick={handleAddTag}
                disabled={!tagInput.trim() || saving}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                추가
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
