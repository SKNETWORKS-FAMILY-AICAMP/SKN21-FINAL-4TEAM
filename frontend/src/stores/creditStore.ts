import { create } from 'zustand';
import { api } from '@/lib/api';

type CreditBalance = {
  balance: number;
  daily_credits: number;
  granted_today: boolean;
  plan_key: string;
};

type CreditHistoryItem = {
  id: number;
  amount: number;
  balance_after: number;
  tx_type: string;
  description: string | null;
  created_at: string;
};

type CreditCost = {
  action: string;
  model_tier: string;
  cost: number;
};

type PurchaseResult = {
  credits_added: number;
  price_krw: number;
  new_balance: number;
};

type CreditState = {
  balance: CreditBalance | null;
  loading: boolean;
  fetchBalance: () => Promise<void>;
  purchase: (pkg: string) => Promise<PurchaseResult>;
};

export const useCreditStore = create<CreditState>((set) => ({
  balance: null,
  loading: false,
  fetchBalance: async () => {
    set({ loading: true });
    try {
      const data = await api.get<CreditBalance>('/credits/balance');
      set({ balance: data });
    } catch (err) {
      console.error('Failed to fetch credit balance:', err);
    } finally {
      set({ loading: false });
    }
  },
  purchase: async (pkg: string) => {
    const result = await api.post<PurchaseResult>('/credits/purchase', { package: pkg });
    set((s) => ({
      balance: s.balance ? { ...s.balance, balance: result.new_balance } : s.balance,
    }));
    return result;
  },
}));

export type { CreditBalance, CreditHistoryItem, CreditCost, PurchaseResult };
