'use client';

import { useEffect } from 'react';
import { Gem } from 'lucide-react';
import { useCreditStore } from '@/stores/creditStore';

export function CreditBadge() {
  const { balance, loading, fetchBalance } = useCreditStore();

  useEffect(() => {
    fetchBalance();
  }, [fetchBalance]);

  if (loading || !balance) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-bg-hover animate-pulse">
        <Gem size={14} />
        <span className="text-xs text-text-muted">---</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20">
      <Gem size={14} className="text-primary" />
      <span className="text-xs font-semibold text-primary">
        {balance.balance.toLocaleString()}석
      </span>
    </div>
  );
}
