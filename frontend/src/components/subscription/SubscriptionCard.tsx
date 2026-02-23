'use client';

import { Check } from 'lucide-react';

type Plan = {
  plan_key: string;
  display_name: string;
  price_krw: number;
  daily_credits: number;
  max_lounge_personas: number;
  max_agent_actions: number;
  features: Record<string, boolean> | null;
};

type Props = {
  plan: Plan;
  isCurrent: boolean;
  onSelect: (planKey: string) => void;
  loading: boolean;
};

export function SubscriptionCard({ plan, isCurrent, onSelect, loading }: Props) {
  const isPremium = plan.price_krw > 0;

  return (
    <div
      className={`rounded-2xl border-2 p-6 transition-colors duration-200 ${
        isCurrent
          ? 'border-primary bg-primary/5'
          : 'border-border bg-bg-surface'
      }`}
    >
      <div className="mb-4">
        <h3 className="text-lg font-bold text-text">{plan.display_name}</h3>
        <div className="mt-1">
          {plan.price_krw > 0 ? (
            <span className="text-2xl font-bold text-primary">
              ₩{plan.price_krw.toLocaleString()}
              <span className="text-sm font-normal text-text-muted">/월</span>
            </span>
          ) : (
            <span className="text-2xl font-bold text-success">무료</span>
          )}
        </div>
      </div>

      <ul className="flex flex-col gap-2 mb-6">
        <li className="flex items-center gap-2 text-sm text-text-secondary">
          <Check size={16} className="text-success flex-shrink-0" />
          일일 {plan.daily_credits}석 충전
        </li>
        <li className="flex items-center gap-2 text-sm text-text-secondary">
          <Check size={16} className="text-success flex-shrink-0" />
          라운지 캐릭터 {plan.max_lounge_personas}개
        </li>
        <li className="flex items-center gap-2 text-sm text-text-secondary">
          <Check size={16} className="text-success flex-shrink-0" />
          캐릭터 자동활동 {plan.max_agent_actions}회/일
        </li>
        {isPremium && plan.features?.notifications && (
          <li className="flex items-center gap-2 text-sm text-text-secondary">
            <Check size={16} className="text-success flex-shrink-0" />
            캐릭터 활동 알림
          </li>
        )}
        {isPremium && plan.features?.reports && (
          <li className="flex items-center gap-2 text-sm text-text-secondary">
            <Check size={16} className="text-success flex-shrink-0" />
            캐릭터 활동 리포트
          </li>
        )}
      </ul>

      {isCurrent ? (
        <div className="text-center py-2.5 rounded-lg bg-primary/10 text-primary text-sm font-semibold">
          현재 플랜
        </div>
      ) : (
        <button
          onClick={() => onSelect(plan.plan_key)}
          disabled={loading}
          className={`w-full py-2.5 rounded-lg text-sm font-semibold border-none cursor-pointer transition-colors duration-200 ${
            isPremium
              ? 'bg-primary text-white hover:bg-primary/90'
              : 'bg-bg-hover text-text hover:bg-bg-hover/80'
          } ${loading ? 'opacity-60 cursor-not-allowed' : ''}`}
        >
          {isPremium ? '구독하기' : '무료로 시작'}
        </button>
      )}
    </div>
  );
}
