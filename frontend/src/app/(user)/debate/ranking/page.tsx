'use client';

import { TrendingUp } from 'lucide-react';
import { RankingTable } from '@/components/debate/RankingTable';

export default function RankingPage() {
  return (
    <div className="max-w-[800px] mx-auto py-6 px-4">
      <h1 className="page-title flex items-center gap-2 mb-5">
        <TrendingUp size={24} className="text-primary" />
        ELO 랭킹
      </h1>
      <RankingTable />
    </div>
  );
}
