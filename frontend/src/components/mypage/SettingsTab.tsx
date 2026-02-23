/** 마이페이지 설정 탭. 성인인증 상태/요청 + LLM 모델 선택. */
'use client';

import { useEffect, useState } from 'react';
import { ShieldCheck, Bot, Gem } from 'lucide-react';
import { api } from '@/lib/api';
import { useUserStore } from '@/stores/userStore';
import { AdultVerifyModal } from '@/components/auth/AdultVerifyModal';
import { toast } from '@/stores/toastStore';

type LLMModel = {
  id: string;
  display_name: string;
  provider: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  max_context_length: number;
  is_adult_only: boolean;
  is_active: boolean;
  tier?: string;
  credit_per_1k_tokens: number;
};

export function SettingsTab() {
  const { user, setUser, isAdultVerified } = useUserStore();
  const [models, setModels] = useState<LLMModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<LLMModel[]>('/models').then(setModels).catch(() => {});
    if (user?.preferredLlmModelId) {
      setSelectedModel(user.preferredLlmModelId);
    }
  }, [user]);

  const handleModelSelect = async (modelId: string) => {
    setSaving(true);
    try {
      await api.put('/models/preferred', { model_id: modelId });
      setSelectedModel(modelId);
      if (user) {
        setUser({ ...user, preferredLlmModelId: modelId });
      }
      toast.success('모델이 변경되었습니다');
    } catch {
      toast.error('모델 변경에 실패했습니다');
    } finally {
      setSaving(false);
    }
  };

  const handleVerified = () => {
    if (user) {
      setUser({
        ...user,
        ageGroup: 'adult_verified',
        adultVerifiedAt: new Date().toISOString(),
      });
    }
    setShowVerifyModal(false);
  };

  return (
    <>
      <section className="card mb-5 p-6">
        <h2 className="section-title flex items-center gap-2">
          <ShieldCheck size={20} className="text-warning" />
          성인인증
        </h2>
        {isAdultVerified() ? (
          <div className="inline-block py-2 px-4 rounded-lg bg-success text-white font-semibold text-sm">
            인증 완료
          </div>
        ) : (
          <div>
            <p className="text-text-secondary text-sm mb-4">
              18+ 콘텐츠 이용을 위해 성인인증이 필요합니다.
            </p>
            <button
              onClick={() => setShowVerifyModal(true)}
              className="py-2.5 px-5 border-none rounded-lg bg-warning text-white text-sm font-semibold cursor-pointer"
            >
              성인인증 하기
            </button>
          </div>
        )}
      </section>

      <section className="card p-6">
        <h2 className="section-title flex items-center gap-2">
          <Bot size={20} className="text-primary" />
          LLM 모델 선택
        </h2>
        <p className="text-text-secondary text-sm mb-4">
          대화에 사용할 AI 모델을 선택하세요. 모델에 따라 비용이 다릅니다.
        </p>
        <div className="flex flex-col gap-3">
          {models
            .filter((m) => m.is_active)
            .map((model) => {
              const locked = model.is_adult_only && !isAdultVerified();
              const isSelected = selectedModel === model.id;
              return (
                <div
                  key={model.id}
                  onClick={() => !locked && handleModelSelect(model.id)}
                  className={`p-4 rounded-xl border-2 transition-colors duration-200 relative ${
                    isSelected
                      ? 'border-primary bg-primary/10'
                      : 'border-border bg-bg-surface'
                  } ${locked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[15px] font-semibold">{model.display_name}</span>
                    <span className="text-xs text-text-muted uppercase">{model.provider}</span>
                  </div>
                  <div className="flex gap-4 text-[13px] text-text-secondary mb-1">
                    <span>입력: ${model.input_cost_per_1m}/1M</span>
                    <span>출력: ${model.output_cost_per_1m}/1M</span>
                  </div>
                  <div className="text-xs text-text-muted">
                    컨텍스트: {(model.max_context_length / 1000).toFixed(0)}K
                    {model.is_adult_only && ' | 성인전용'}
                    {' | '}
                    <Gem size={10} className="inline" />
                    {' '}{model.credit_per_1k_tokens}석/1K토큰
                  </div>
                  {isSelected && (
                    <div className="absolute top-3 right-3 px-2.5 py-0.5 rounded-badge bg-primary text-white text-[11px] font-semibold">
                      선택됨
                    </div>
                  )}
                </div>
              );
            })}
        </div>
      </section>

      <AdultVerifyModal
        isOpen={showVerifyModal}
        onClose={() => setShowVerifyModal(false)}
        onVerified={handleVerified}
      />
    </>
  );
}
