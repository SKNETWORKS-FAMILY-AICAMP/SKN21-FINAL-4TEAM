'use client';

import { useState } from 'react';
import { Gem, X } from 'lucide-react';
import { useCreditStore } from '@/stores/creditStore';
import { toast } from '@/stores/toastStore';

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

const PACKAGES = [
  { key: 'small', credits: 500, price: 1000, label: '소량' },
  { key: 'medium', credits: 3000, price: 5000, label: '적정량' },
  { key: 'large', credits: 10000, price: 15000, label: '대량' },
] as const;

export function PurchaseModal({ isOpen, onClose }: Props) {
  const { purchase } = useCreditStore();
  const [purchasing, setPurchasing] = useState<string | null>(null);

  if (!isOpen) return null;

  const handlePurchase = async (pkg: string) => {
    setPurchasing(pkg);
    try {
      const result = await purchase(pkg);
      toast.success(`${result.credits_added.toLocaleString()}석이 충전되었습니다!`);
      onClose();
    } catch {
      toast.error('구매에 실패했습니다');
    } finally {
      setPurchasing(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-bg-surface rounded-2xl p-6 w-[400px] max-w-[90vw] shadow-xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Gem size={20} className="text-primary" />
            대화석 구매
          </h2>
          <button onClick={onClose} className="text-text-muted hover:text-text bg-transparent border-none cursor-pointer">
            <X size={20} />
          </button>
        </div>

        <p className="text-sm text-text-secondary mb-4">
          대화석으로 채팅, 게시판, 리뷰 등 다양한 활동을 즐길 수 있습니다.
        </p>

        <div className="flex flex-col gap-3">
          {PACKAGES.map((pkg) => (
            <button
              key={pkg.key}
              onClick={() => handlePurchase(pkg.key)}
              disabled={purchasing !== null}
              className={`flex items-center justify-between p-4 rounded-xl border-2 border-border bg-bg transition-colors duration-200 cursor-pointer ${
                purchasing === pkg.key ? 'opacity-60' : 'hover:border-primary/50 hover:bg-primary/5'
              }`}
            >
              <div className="text-left">
                <div className="text-sm font-semibold text-text">{pkg.label}</div>
                <div className="text-xs text-text-secondary mt-0.5">
                  {pkg.credits.toLocaleString()}석
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-primary">
                  ₩{pkg.price.toLocaleString()}
                </div>
                <div className="text-[11px] text-text-muted">
                  {(pkg.price / pkg.credits).toFixed(1)}원/석
                </div>
              </div>
            </button>
          ))}
        </div>

        <p className="text-[11px] text-text-muted mt-4 text-center">
          프로토타입 단계에서는 실제 결제 없이 즉시 충전됩니다.
        </p>
      </div>
    </div>
  );
}
