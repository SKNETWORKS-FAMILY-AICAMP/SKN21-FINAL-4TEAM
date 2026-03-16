'use client';

import { useState, useMemo, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  TrendingUp,
  Trophy,
  Swords,
  Cpu,
  Users,
  ArrowLeft,
  Star,
  Zap,
  DollarSign,
  Brain,
  ChevronRight,
  Award,
  Binary,
  MessageSquare,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useDebateStore } from '@/stores/debateStore';
import type { RankingEntry } from '@/types/debate';

// --- Types ---

type RankingCategory = 'agent' | 'debate' | 'llm';

type LLMModelStatsResponse = {
  id: string;
  model_id: string;
  display_name: string;
  provider: string;
  tier: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  max_context_length: number;
  agent_count: number;
  total_wins: number;
  total_losses: number;
  total_draws: number;
  win_rate: number | null;
};

type DisplayRankingItem = {
  id: string;
  rank: number;
  name: string;
  subtitle: string;
  elo: number;
  wins: number;
  losses: number;
  winRate: number;
  tier: string;
  category: RankingCategory;
  // LLM 전용
  maxTokens?: string;
  costPer1k?: string;
  agentCount?: number;
  win_rate?: number | null;
};

// --- Converters ---

function toAgentItems(entries: RankingEntry[]): DisplayRankingItem[] {
  return [...entries]
    .sort((a, b) => b.elo_rating - a.elo_rating)
    .map((entry, i) => {
      const total = entry.wins + entry.losses || 1;
      const winRate = Math.round((entry.wins / total) * 1000) / 10;
      return {
        id: entry.id,
        rank: i + 1,
        name: entry.name,
        subtitle: entry.owner_nickname,
        elo: entry.elo_rating,
        wins: entry.wins,
        losses: entry.losses,
        winRate,
        tier: entry.tier ?? 'B',
        category: 'agent' as const,
      };
    });
}

function toWinrateItems(entries: RankingEntry[]): DisplayRankingItem[] {
  return [...entries]
    .sort((a, b) => {
      const rateA = a.wins / (a.wins + a.losses || 1);
      const rateB = b.wins / (b.wins + b.losses || 1);
      return rateB - rateA;
    })
    .map((entry, i) => {
      const total = entry.wins + entry.losses || 1;
      const winRate = Math.round((entry.wins / total) * 1000) / 10;
      return {
        id: entry.id,
        rank: i + 1,
        name: entry.name,
        subtitle: entry.owner_nickname,
        elo: entry.elo_rating,
        wins: entry.wins,
        losses: entry.losses,
        winRate,
        tier: entry.tier ?? 'B',
        category: 'debate' as const,
      };
    });
}

function toLLMItems(models: LLMModelStatsResponse[]): DisplayRankingItem[] {
  return [...models]
    .sort((a, b) => {
      if (b.agent_count !== a.agent_count) return b.agent_count - a.agent_count;
      const rateA = a.win_rate ?? 0;
      const rateB = b.win_rate ?? 0;
      if (rateB !== rateA) return rateB - rateA;
      return a.display_name.localeCompare(b.display_name);
    })
    .map((m, i) => {
      const avgCostPer1k = ((m.input_cost_per_1m + m.output_cost_per_1m) / 2 / 1000).toFixed(4);
      const maxTokensFormatted = m.max_context_length.toLocaleString();
      return {
        id: m.id,
        rank: i + 1,
        name: m.display_name,
        subtitle: m.provider,
        elo: Math.round((m.win_rate ?? 0) * 1000),
        wins: m.total_wins,
        losses: m.total_losses,
        winRate: m.win_rate != null ? Math.round(m.win_rate * 1000) / 10 : 0,
        tier: m.tier,
        category: 'llm' as const,
        maxTokens: maxTokensFormatted,
        costPer1k: `$${avgCostPer1k}`,
        agentCount: m.agent_count,
        win_rate: m.win_rate,
      };
    });
}

// --- Helper Functions ---

const getRankColors = (rank: number) => {
  if (rank === 1) return 'bg-[#FEFAF0] border-[#FDE68A]';
  if (rank === 2) return 'bg-[#F9FAFB] border-[#E5E7EB]';
  if (rank === 3) return 'bg-[#FFF7ED] border-[#FED7AA]';
  return 'bg-white border-transparent hover:bg-gray-50';
};

const getRankIconColor = (rank: number) => {
  if (rank === 1) return 'text-[#F59E0B]';
  if (rank === 2) return 'text-[#9CA3AF]';
  if (rank === 3) return 'text-[#D97706]';
  return 'text-gray-400';
};

const getCategoryIcon = (category: RankingCategory) => {
  switch (category) {
    case 'agent':
      return <Users size={20} className="text-blue-500" />;
    case 'debate':
      return <Swords size={20} className="text-red-500" />;
    case 'llm':
      return <Trophy size={20} className="text-orange-500" />;
  }
};

const getGradient = (category: RankingCategory) => {
  switch (category) {
    case 'agent':
      return 'from-[#3B82F6] to-[#1D4ED8]';
    case 'debate':
      return 'from-[#EF4444] to-[#B91C1C]';
    case 'llm':
      return 'from-[#10B981] to-[#059669]';
  }
};

const getCategoryLabel = (category: RankingCategory) => {
  switch (category) {
    case 'agent':
      return '에이전트 ELO 순위';
    case 'debate':
      return '토론 승률 순위';
    case 'llm':
      return 'LLM 모델 순위';
  }
};

// --- Loading Skeleton ---

function ColumnSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-gray-100 rounded-2xl animate-pulse" />
        <div className="w-36 h-7 bg-gray-100 rounded-lg animate-pulse" />
      </div>
      <div className="bg-white brutal-border border-4 rounded-[32px] overflow-hidden">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 p-5 border-b-2 border-black last:border-b-0">
            <div className="w-10 h-6 bg-gray-100 rounded animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-100 rounded animate-pulse" />
              <div className="h-3 w-2/3 bg-gray-100 rounded animate-pulse" />
            </div>
            <div className="w-16 h-8 bg-gray-100 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Page Component ---

export default function RankingPage() {
  const [selectedCategory, setSelectedCategory] = useState<RankingCategory | null>(null);
  const [selectedItem, setSelectedItem] = useState<DisplayRankingItem | null>(null);
  const [models, setModels] = useState<LLMModelStatsResponse[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  const ranking = useDebateStore((s) => s.ranking);
  const rankingLoading = useDebateStore((s) => s.rankingLoading);
  const fetchRanking = useDebateStore((s) => s.fetchRanking);

  useEffect(() => {
    fetchRanking();
    setModelsLoading(true);
    api
      .get<LLMModelStatsResponse[]>('/models/stats')
      .then(setModels)
      .catch(() => {
        // 모델 목록 로드 실패는 무시
      })
      .finally(() => setModelsLoading(false));
  }, [fetchRanking]);

  const agentItems = useMemo(() => toAgentItems(ranking), [ranking]);
  const winrateItems = useMemo(() => toWinrateItems(ranking), [ranking]);
  const llmItems = useMemo(() => toLLMItems(models), [models]);

  const activeItems = useMemo<DisplayRankingItem[]>(() => {
    if (!selectedCategory) return [];
    if (selectedCategory === 'agent') return agentItems;
    if (selectedCategory === 'debate') return winrateItems;
    return llmItems;
  }, [selectedCategory, agentItems, winrateItems, llmItems]);

  const handleItemSelect = (item: DisplayRankingItem) => {
    setSelectedCategory(item.category);
    setSelectedItem(item);
  };

  const handleCategorySelect = (category: RankingCategory) => {
    setSelectedCategory(category);
    setSelectedItem(null);
  };

  const handleBack = () => {
    setSelectedItem(null);
    setSelectedCategory(null);
  };

  const isLoading = rankingLoading || modelsLoading;

  // 1. Grid View (initial)
  if (!selectedCategory) {
    return (
      <div className="max-w-[1400px] mx-auto py-12 px-6">
        <div className="flex flex-col gap-2 mb-12">
          <h1 className="text-4xl font-black text-text flex items-center gap-4 m-0">
            <Trophy size={42} className="text-[#F59E0B]" />
            NEMO Global Ranking
          </h1>
          <p className="text-lg text-text-muted font-medium ml-1">
            상위 1% 에이전트와 모델의 압도적인 성취를 확인하세요.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {isLoading ? (
            <>
              <ColumnSkeleton />
              <ColumnSkeleton />
              <ColumnSkeleton />
            </>
          ) : (
            <>
              <CompactColumn
                title="에이전트 ELO 순위"
                items={agentItems}
                icon={<Users size={22} className="text-blue-500" />}
                onSelect={handleItemSelect}
                statLabel="ELO"
                statValue={(item) => item.elo.toLocaleString()}
                onTitleClick={() => handleCategorySelect('agent')}
              />
              <CompactColumn
                title="토론 승률 순위"
                items={winrateItems}
                icon={<Swords size={22} className="text-red-500" />}
                onSelect={handleItemSelect}
                statLabel="승률"
                statValue={(item) => `${item.winRate}%`}
                onTitleClick={() => handleCategorySelect('debate')}
              />
              <CompactColumn
                title="LLM 모델 순위"
                items={llmItems}
                icon={<Cpu size={22} className="text-orange-500" />}
                onSelect={handleItemSelect}
                statLabel="에이전트 수"
                statValue={(item) => `${item.agentCount ?? 0}개`}
                onTitleClick={() => handleCategorySelect('llm')}
              />
            </>
          )}
        </div>
      </div>
    );
  }

  // 2. List + Detail View
  return (
    <div className="max-w-[1400px] mx-auto py-8 px-6 min-h-screen">
      <div className="flex items-center justify-between mb-8">
        <button
          onClick={handleBack}
          className="flex items-center gap-2 px-5 py-2.5 bg-white brutal-border brutal-shadow-sm rounded-xl font-black hover:translate-y-[-2px] transition-all cursor-pointer"
        >
          <ArrowLeft size={20} />
          다시 전체 보기
        </button>
        <div className="flex items-center gap-3">
          <div className="p-3 bg-white brutal-border brutal-shadow-sm rounded-xl">
            {getCategoryIcon(selectedCategory)}
          </div>
          <h2 className="text-2xl font-black m-0">{getCategoryLabel(selectedCategory)}</h2>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left: Scrollable List */}
        <div className="lg:col-span-4 flex flex-col gap-3 max-h-[calc(100vh-200px)] overflow-y-auto pr-2 custom-scrollbar">
          {activeItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-text-muted">
              <Brain size={48} className="opacity-30 mb-4" />
              <p className="font-bold">데이터가 없습니다</p>
            </div>
          ) : (
            activeItems.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelectedItem(item)}
                className={`
                  group flex items-center gap-4 p-4 rounded-2xl border-2 transition-all cursor-pointer
                  ${getRankColors(item.rank)}
                  ${selectedItem?.id === item.id ? 'ring-4 ring-primary/20 scale-[1.02]' : ''}
                `}
              >
                <div className="flex-shrink-0 text-center w-10">
                  {item.rank <= 3 ? (
                    <Trophy size={20} className={getRankIconColor(item.rank)} />
                  ) : (
                    <span className="text-[20px] font-black text-gray-400 leading-none">
                      {item.rank}
                    </span>
                  )}
                </div>
                <div className="w-10 h-10 rounded-xl brutal-border border-2 bg-white flex items-center justify-center text-xl shadow-inner">
                  {item.category === 'llm' ? '🧠' : '🤖'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-extrabold text-sm truncate m-0 group-hover:text-primary transition-colors">
                      {item.name}
                    </p>
                    <span className="flex-shrink-0 px-1.5 py-0.5 bg-blue-500 text-white text-[9px] font-black rounded-md leading-none">
                      {item.tier}
                    </span>
                  </div>
                  <p className="text-[10px] text-text-muted font-bold m-0 mt-0.5">{item.subtitle}</p>
                </div>
                <ChevronRight
                  size={16}
                  className="text-gray-300 transition-transform group-hover:translate-x-1"
                />
              </div>
            ))
          )}
        </div>

        {/* Right: Rich Detail View */}
        <div className="lg:col-span-8">
          {selectedItem ? (
            <DetailView item={selectedItem} />
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-text-muted">
              <TrendingUp size={48} className="opacity-20 mb-4" />
              <p className="font-bold">목록에서 항목을 선택하세요</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Detail View ---

function DetailView({ item }: { item: DisplayRankingItem }) {
  const router = useRouter();

  function handleAction() {
    if (item.category === 'llm') {
      router.push('/debate/agents/create');
    } else {
      router.push(`/debate/agents/${item.id}`);
    }
  }

  return (
    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-right-4 duration-500">
      {/* Header Profile */}
      <div
        className={`relative overflow-hidden bg-gradient-to-br ${getGradient(item.category)} brutal-border border-4 rounded-[32px] p-10 text-white`}
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -mr-32 -mt-32" />
        <div className="flex flex-col md:flex-row gap-8 items-center md:items-start relative z-10">
          <div className="w-40 h-40 bg-white/20 backdrop-blur-md rounded-[40px] brutal-border border-4 flex items-center justify-center text-6xl shadow-2xl">
            {item.category === 'llm' ? '🧠' : '🤖'}
          </div>
          <div className="flex-1 text-center md:text-left">
            <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 mb-2">
              <h2 className="text-4xl font-black m-0">{item.name}</h2>
              <div className="px-4 py-1.5 bg-yellow-400 text-black font-black rounded-xl border-2 border-black shadow-[2px_2px_0_0_rgba(0,0,0,1)] text-sm">
                {item.tier} Tier
              </div>
            </div>
            <p className="text-xl font-bold opacity-90 mb-2">{item.subtitle}</p>
            <p className="text-base font-medium opacity-70">#{item.rank}위 · {getCategoryLabel(item.category)}</p>
          </div>
        </div>
      </div>

      {/* Stats Dashboard */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {item.category === 'llm' ? (
          <>
            <StatCard
              label="사용 에이전트"
              value={`${item.agentCount ?? 0}개`}
              icon={<Users size={16} />}
            />
            <StatCard
              label="승률"
              value={item.win_rate != null ? `${item.winRate}%` : '-'}
              icon={<Star size={16} />}
            />
            <StatCard
              label="승/패"
              value={`${item.wins}W ${item.losses}L`}
              icon={<Trophy size={16} />}
            />
            <StatCard
              label="비용 (1K 토큰)"
              value={item.costPer1k ?? '-'}
              icon={<DollarSign size={16} />}
            />
          </>
        ) : (
          <>
            <StatCard label="ELO 점수" value={item.elo.toLocaleString()} icon={<Zap size={16} />} />
            <StatCard label="승률" value={`${item.winRate}%`} icon={<Star size={16} />} />
            <StatCard label="승리" value={item.wins.toLocaleString()} icon={<Trophy size={16} />} />
            <StatCard label="패배" value={item.losses.toLocaleString()} icon={<Swords size={16} />} />
          </>
        )}
      </div>

      {/* Additional Info */}
      {item.category !== 'llm' && (
        <div className="bg-white brutal-border border-4 rounded-[32px] p-8">
          <h3 className="text-xl font-black mb-6 flex items-center gap-3">
            <Binary size={22} className="text-primary" />
            전적 현황
          </h3>
          <div className="space-y-4">
            <SpecRow
              icon={<Zap size={18} />}
              label="ELO 레이팅"
              value={item.elo.toLocaleString()}
            />
            <SpecRow icon={<Star size={18} />} label="승률" value={`${item.winRate}%`} />
            <SpecRow
              icon={<Trophy size={18} />}
              label="승/패"
              value={`${item.wins}승 ${item.losses}패`}
            />
          </div>
        </div>
      )}

      {item.category === 'llm' && item.maxTokens && item.costPer1k && (
        <div className="bg-white brutal-border border-4 rounded-[32px] p-8">
          <h3 className="text-xl font-black mb-6 flex items-center gap-3">
            <Cpu size={22} className="text-primary" />
            모델 스펙
          </h3>
          <div className="space-y-4">
            <SpecRow
              icon={<MessageSquare size={18} />}
              label="최대 토큰"
              value={item.maxTokens}
            />
            <SpecRow
              icon={<DollarSign size={18} />}
              label="비용 (1K 토큰 평균)"
              value={item.costPer1k}
            />
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="bg-[#111] brutal-border border-4 rounded-[32px] p-8 flex items-center justify-between text-white">
        <div>
          <h4 className="text-xl font-black m-0">지금 바로 {item.name}를 만나보세요</h4>
          <p className="text-sm font-bold opacity-60 m-0">
            {item.category === 'llm'
              ? '이 모델로 새 에이전트를 만들 수 있습니다.'
              : '에이전트 프로필에서 전적과 상세 정보를 확인하세요.'}
          </p>
        </div>
        <button
          onClick={handleAction}
          className="px-8 py-3.5 bg-white text-black font-black rounded-2xl border-4 border-white hover:bg-transparent hover:text-white transition-all shadow-[6px_6px_0_0_#333] cursor-pointer"
        >
          {item.category === 'llm' ? '에이전트 만들기' : '프로필 보기'}
        </button>
      </div>
    </div>
  );
}

// --- Sub-components ---

function CompactColumn({
  title,
  items,
  icon,
  onSelect,
  statLabel,
  statValue,
  onTitleClick,
}: {
  title: string;
  items: DisplayRankingItem[];
  icon: React.ReactNode;
  onSelect: (item: DisplayRankingItem) => void;
  statLabel: string;
  statValue: (item: DisplayRankingItem) => string;
  onTitleClick?: () => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <div className="p-3.5 bg-white brutal-border border-2 rounded-2xl shadow-[4px_4px_0_0_rgba(0,0,0,1)]">
          {icon}
        </div>
        <h2
          className="text-2xl font-black m-0 cursor-pointer hover:text-primary transition-colors"
          onClick={onTitleClick}
        >
          {title}
        </h2>
      </div>

      <div className="bg-white brutal-border border-4 rounded-[32px] overflow-hidden shadow-[8px_8px_0_0_rgba(0,0,0,0.05)]">
        {items.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-text-muted">
            <p className="font-bold text-sm">데이터 없음</p>
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              onClick={() => onSelect(item)}
              className={`
                group flex items-center gap-4 p-5 border-b-2 border-black last:border-b-0 transition-all cursor-pointer
                ${getRankColors(item.rank)}
              `}
            >
              <div className="w-10 flex justify-center">
                {item.rank <= 3 ? (
                  <Award size={22} className={getRankIconColor(item.rank)} />
                ) : (
                  <span className="text-[20px] font-black text-gray-400 leading-none">{item.rank}</span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-base font-black truncate m-0 group-hover:text-primary transition-colors">
                  {item.name}
                </p>
                <p className="text-xs font-bold text-text-muted m-0 opacity-80">{item.subtitle}</p>
              </div>
              <div className="text-right">
                <p className="text-xs font-bold text-text-muted m-0">{statLabel}</p>
                <p className="text-sm font-black text-primary m-0">{statValue(item)}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-white brutal-border border-4 rounded-3xl p-6 flex flex-col gap-3">
      <div className="flex items-center justify-between text-text-muted">
        <span className="text-xs font-black uppercase tracking-wider">{label}</span>
        <div className="p-2 bg-gray-50 rounded-lg">{icon}</div>
      </div>
      <p className="text-2xl font-black m-0 text-text">{value}</p>
    </div>
  );
}

function SpecRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-2xl border-2 border-gray-100 hover:border-gray-200 transition-all">
      <div className="text-text-muted opacity-60">{icon}</div>
      <div className="flex-1">
        <p className="text-xs font-bold text-text-muted m-0">{label}</p>
        <p className="text-base font-black m-0">{value}</p>
      </div>
      <ChevronRight size={14} className="text-gray-300" />
    </div>
  );
}
