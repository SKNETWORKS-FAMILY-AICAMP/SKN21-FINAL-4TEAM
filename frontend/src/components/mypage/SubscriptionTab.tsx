/** 마이페이지 구독 탭. 구독 플랜 목록, 현재 구독 정보, 구독 취소. */
'use client';

import { useEffect, useState } from 'react';
import { Crown, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';
import { useCreditStore } from '@/stores/creditStore';
import { SubscriptionCard } from '@/components/subscription/SubscriptionCard';
import { SkeletonStat } from '@/components/ui/Skeleton';

type Plan = {
  plan_key: string;
  display_name: string;
  price_krw: number;
  daily_credits: number;
  max_lounge_personas: number;
  max_agent_actions: number;
  features: Record<string, boolean> | null;
};

type MySubscription = {
  status: string;
  plan_key?: string;
  plan?: Plan;
  expires_at?: string | null;
  cancelled_at?: string | null;
};

export function SubscriptionTab() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [mySub, setMySub] = useState<MySubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const { fetchBalance } = useCreditStore();

  useEffect(() => {
    Promise.all([
      api.get<Plan[]>('/subscriptions/plans'),
      api.get<MySubscription>('/subscriptions/me'),
    ])
      .then(([p, s]) => {
        setPlans(p);
        setMySub(s);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const currentPlanKey = mySub?.plan?.plan_key ?? mySub?.plan_key ?? 'free';

  const handleSubscribe = async (planKey: string) => {
    setActionLoading(true);
    try {
      await api.post('/subscriptions/subscribe', { plan_key: planKey });
      const updated = await api.get<MySubscription>('/subscriptions/me');
      setMySub(updated);
      await fetchBalance();
      toast.success('구독이 시작되었습니다!');
    } catch {
      toast.error('구독 변경에 실패했습니다');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    setActionLoading(true);
    try {
      await api.post('/subscriptions/cancel');
      const updated = await api.get<MySubscription>('/subscriptions/me');
      setMySub(updated);
      toast.info('구독이 해지되었습니다. 기간 만료까지 이용 가능합니다.');
    } catch {
      toast.error('구독 해지에 실패했습니다');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <SkeletonStat key={i} />
        ))}
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center gap-2 mb-4">
        <Crown size={24} className="text-warning" />
        <h2 className="section-title m-0">구독 플랜</h2>
      </div>

      <p className="text-sm text-text-secondary mb-6">
        플랜에 따라 일일 대화석 충전량과 캐릭터 라운지 기능이 달라집니다.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {plans.map((plan) => (
          <SubscriptionCard
            key={plan.plan_key}
            plan={plan}
            isCurrent={currentPlanKey === plan.plan_key}
            onSelect={handleSubscribe}
            loading={actionLoading}
          />
        ))}
      </div>

      {mySub?.status === 'active' && currentPlanKey !== 'free' && (
        <div className="card p-5">
          <div className="flex items-start gap-3">
            <AlertCircle size={18} className="text-text-muted mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-text-secondary mb-2">
                현재 <strong>{mySub.plan?.display_name ?? '프리미엄'}</strong> 플랜을 이용 중입니다.
                {mySub.expires_at && (
                  <> 만료일: {new Date(mySub.expires_at).toLocaleDateString('ko-KR')}</>
                )}
              </p>
              <button
                onClick={handleCancel}
                disabled={actionLoading}
                className="text-sm text-danger bg-transparent border-none cursor-pointer hover:underline"
              >
                구독 해지
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
