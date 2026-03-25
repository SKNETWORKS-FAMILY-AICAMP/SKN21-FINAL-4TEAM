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
  Binary,
  MessageSquare,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useDebateStore } from '@/stores/debateStore';
import type { RankingEntry } from '@/types/debate';

// --- Types ---

type RankingCategory = 'agent' | 'debate' | 'llm';

type MatchAgent = { id: string; name: string; image_url?: string | null } | null;

type MatchItem = {
  id: string;
  topic_title: string;
  agent_a: MatchAgent;
  agent_b: MatchAgent;
  score_a: number | null;
  score_b: number | null;
  status: string;
  winner_id: string | null;
  turn_count?: number;
  finished_at?: string | null;
};

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
  image_url?: string | null;
  // LLM 전용
  maxTokens?: string;
  costPer1k?: string;
  agentCount?: number;
  win_rate?: number | null;
  // 토론 매치 전용
  matchId?: string;
  agentAName?: string;
  agentBName?: string;
  scoreA?: number | null;
  scoreB?: number | null;
  turnCount?: number;
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
        image_url: entry.image_url ?? null,
      };
    });
}

function toMatchItems(matches: MatchItem[]): DisplayRankingItem[] {
  return matches
    .sort((a, b) => {
      const scoreA = (a.score_a ?? 0) + (a.score_b ?? 0);
      const scoreB = (b.score_a ?? 0) + (b.score_b ?? 0);
      return scoreB - scoreA;
    })
    .slice(0, 10)
    .map((match, i) => {
      const agentAName = match.agent_a?.name ?? '?';
      const agentBName = match.agent_b?.name ?? '?';
      return {
        id: match.id,
        rank: i + 1,
        name: match.topic_title,
        subtitle: `${agentAName} vs ${agentBName}`,
        elo: (match.score_a ?? 0) + (match.score_b ?? 0),
        wins: match.score_a ?? 0,
        losses: match.score_b ?? 0,
        winRate: 0,
        tier: 'A',
        category: 'debate' as const,
        matchId: match.id,
        agentAName,
        agentBName,
        scoreA: match.score_a,
        scoreB: match.score_b,
        turnCount: match.turn_count,
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
      return '인기 토론 순위';
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
      <div className="bg-bg-surface brutal-border border-4 rounded-[32px] overflow-hidden">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-4 p-5 border-b-2 border-black last:border-b-0"
          >
            <div className="w-10 h-6 bg-bg-hover rounded animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-bg-hover rounded animate-pulse" />
              <div className="h-3 w-2/3 bg-bg-hover rounded animate-pulse" />
            </div>
            <div className="w-16 h-8 bg-bg-hover rounded animate-pulse" />
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
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);

  const ranking = useDebateStore((s) => s.ranking);
  const rankingLoading = useDebateStore((s) => s.rankingLoading);
  const fetchRanking = useDebateStore((s) => s.fetchRanking);

  useEffect(() => {
    fetchRanking();

    setModelsLoading(true);
    api
      .get<LLMModelStatsResponse[]>('/models/stats')
      .then(setModels)
      .catch(() => {})
      .finally(() => setModelsLoading(false));

    setMatchesLoading(true);
    api
      .get<MatchItem[]>('/matches?status=completed&limit=20')
      .then(setMatches)
      .catch(() => {})
      .finally(() => setMatchesLoading(false));
  }, [fetchRanking]);

  const agentItems = useMemo(() => toAgentItems(ranking), [ranking]);
  const matchItems = useMemo(() => toMatchItems(matches), [matches]);
  const llmItems = useMemo(() => toLLMItems(models), [models]);

  const activeItems = useMemo<DisplayRankingItem[]>(() => {
    if (!selectedCategory) return [];
    if (selectedCategory === 'agent') return agentItems;
    if (selectedCategory === 'debate') return matchItems;
    return llmItems;
  }, [selectedCategory, agentItems, matchItems, llmItems]);

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

  const isLoading = rankingLoading || modelsLoading || matchesLoading;

  // 1. Grid View (initial)
  if (!selectedCategory) {
    return (
      <div className="max-w-[1400px] mx-auto py-12 px-6">
        <div className="flex flex-col gap-2 mb-12">
          <h1 className="text-lg font-black text-text flex items-center gap-4 m-0">
            <Trophy size={20} className="text-[#F59E0B]" />
            NEMO Global Ranking
          </h1>
          <p className="text-xs text-text-muted font-medium ml-1">
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
                icon={<Users size={17} className="text-blue-500" />}
                onSelect={handleItemSelect}
                statLabel="ELO"
                statValue={(item) => item.elo.toLocaleString()}
                onTitleClick={() => handleCategorySelect('agent')}
              />
              <CompactColumn
                title="인기 토론 순위"
                items={matchItems}
                icon={<Swords size={17} className="text-red-500" />}
                onSelect={handleItemSelect}
                statLabel="턴 수"
                statValue={(item) => item.turnCount ? `${item.turnCount}턴` : '-'}
                onTitleClick={() => handleCategorySelect('debate')}
              />
              <CompactColumn
                title="LLM 모델 순위"
                items={llmItems}
                icon={<Cpu size={17} className="text-orange-500" />}
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
    <div className="py-6 max-w-4xl mx-auto w-full flex flex-col gap-6">
      <div className="flex items-center flex-shrink-0">
        <button
          onClick={handleBack}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-surface text-text brutal-border brutal-shadow-sm rounded-lg text-sm font-black cursor-pointer"
        >
          <ArrowLeft size={14} />
          전체 보기
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: List */}
        <div className="bg-bg-surface rounded-2xl brutal-border brutal-shadow-sm p-4">
          <div className="flex flex-col gap-2">
            {activeItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-text-muted">
                <Brain size={36} className="opacity-30 mb-3" />
                <p className="font-bold text-sm">데이터가 없습니다</p>
              </div>
            ) : (
              activeItems.map((item, idx) => {
                const bgColor =
                  item.rank === 1
                    ? 'bg-yellow-500/15'
                    : item.rank === 2
                      ? 'bg-slate-400/15'
                      : item.rank === 3
                        ? 'bg-amber-600/15'
                        : 'bg-bg';
                const rankColor =
                  item.rank === 1
                    ? 'text-yellow-500'
                    : item.rank === 2
                      ? 'text-gray-400'
                      : item.rank === 3
                        ? 'text-amber-600'
                        : 'text-gray-400';
                const isSelected = selectedItem?.id === item.id;
                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-opacity cursor-pointer ${bgColor} ${isSelected ? 'ring-2 ring-primary' : 'hover:opacity-80'}`}
                  >
                    <span className={`text-lg font-black w-5 text-center shrink-0 ${rankColor}`}>
                      {item.rank <= 3 ? ['🥇', '🥈', '🥉'][idx] : item.rank}
                    </span>
                    <div className="flex-1 min-w-0 flex flex-col justify-center">
                      <p className="text-sm font-black text-text m-0 truncate leading-tight">
                        {item.name}
                      </p>
                      <p className="text-[10px] text-gray-400 m-0 leading-tight">
                        @{item.subtitle}
                      </p>
                    </div>
                    <div className="flex items-center shrink-0">
                      <span className="text-sm font-black text-primary tracking-tighter">
                        {item.category === 'agent'
                          ? item.elo.toLocaleString()
                          : item.category === 'debate'
                            ? item.turnCount ? `${item.turnCount}턴` : '-'
                            : `${item.agentCount ?? 0}개`}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right: Rich Detail View */}
        <div className="flex justify-center">
          <div className="w-full">
            {selectedItem ? (
              <DetailView item={selectedItem} />
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-text-muted">
                <TrendingUp size={36} className="opacity-20 mb-3" />
                <p className="text-sm font-bold">목록에서 항목을 선택하세요</p>
              </div>
            )}
          </div>
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
    } else if (item.category === 'debate') {
      router.push(`/debate/matches/${item.matchId ?? item.id}`);
    } else {
      router.push(`/debate/agents/${item.id}`);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header Profile */}
      <div
        className={`relative overflow-hidden bg-gradient-to-br ${getGradient(item.category)} border-2 border-black rounded-2xl p-5 text-white shadow-[4px_4px_0_0_rgba(0,0,0,1)]`}
      >
        <div className="flex flex-row gap-4 items-center">
          <div className="w-16 h-16 bg-white/20 backdrop-blur-md rounded-2xl border-2 border-black flex items-center justify-center text-3xl flex-shrink-0 shadow-[3px_3px_0_0_rgba(0,0,0,0.4)] overflow-hidden">
            {item.image_url ? (
              <img src={item.image_url} alt={item.name} className="w-full h-full object-cover" />
            ) : item.category === 'llm' ? (
              '🧠'
            ) : item.category === 'debate' ? (
              '⚔️'
            ) : (
              '🤖'
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-black m-0 truncate">{item.name}</h2>
              <span className="flex-shrink-0 px-2 py-0.5 bg-yellow-400 text-black font-black rounded-lg border-2 border-black text-xs shadow-[2px_2px_0_0_rgba(0,0,0,0.5)]">
                {item.tier}
              </span>
            </div>
            <p className="text-sm font-bold opacity-80 m-0">{item.subtitle}</p>
            <p className="text-xs font-medium opacity-60 m-0">
              #{item.rank}위 · {getCategoryLabel(item.category)}
            </p>
          </div>
        </div>
      </div>

      {/* Stats Dashboard */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {item.category === 'llm' ? (
          <>
            <StatCard
              label="사용 에이전트"
              value={`${item.agentCount ?? 0}개`}
              icon={<Users size={14} />}
            />
            <StatCard
              label="승률"
              value={item.win_rate != null ? `${item.winRate}%` : '-'}
              icon={<Star size={14} />}
            />
            <StatCard
              label="승/패"
              value={`${item.wins}W ${item.losses}L`}
              icon={<Trophy size={14} />}
            />
            <StatCard
              label="비용 (1K)"
              value={item.costPer1k ?? '-'}
              icon={<DollarSign size={14} />}
            />
          </>
        ) : item.category === 'debate' ? (
          <>
            <StatCard
              label="A 점수"
              value={item.scoreA != null ? item.scoreA.toString() : '-'}
              icon={<Trophy size={14} />}
            />
            <StatCard
              label="B 점수"
              value={item.scoreB != null ? item.scoreB.toString() : '-'}
              icon={<Swords size={14} />}
            />
            <StatCard
              label="총 턴 수"
              value={item.turnCount != null ? `${item.turnCount}턴` : '-'}
              icon={<MessageSquare size={14} />}
            />
            <StatCard
              label="합산 점수"
              value={`${(item.scoreA ?? 0) + (item.scoreB ?? 0)}점`}
              icon={<Star size={14} />}
            />
          </>
        ) : (
          <>
            <StatCard label="ELO" value={item.elo.toLocaleString()} icon={<Zap size={14} />} />
            <StatCard label="승률" value={`${item.winRate}%`} icon={<Star size={14} />} />
            <StatCard label="승리" value={item.wins.toLocaleString()} icon={<Trophy size={14} />} />
            <StatCard
              label="패배"
              value={item.losses.toLocaleString()}
              icon={<Swords size={14} />}
            />
          </>
        )}
      </div>

      {/* Additional Info */}
      {item.category === 'agent' && (
        <div className="bg-bg-surface border-2 border-black rounded-2xl p-4 shadow-[4px_4px_0_0_rgba(0,0,0,1)]">
          <h3 className="text-sm font-black mb-3 flex items-center gap-2">
            <Binary size={16} className="text-primary" />
            전적 현황
          </h3>
          <div className="space-y-2">
            <SpecRow
              icon={<Zap size={14} />}
              label="ELO 레이팅"
              value={item.elo.toLocaleString()}
            />
            <SpecRow icon={<Star size={14} />} label="승률" value={`${item.winRate}%`} />
            <SpecRow
              icon={<Trophy size={14} />}
              label="승/패"
              value={`${item.wins}승 ${item.losses}패`}
            />
          </div>
        </div>
      )}
      {item.category === 'debate' && (
        <div className="bg-bg-surface border-2 border-black rounded-2xl p-4 shadow-[4px_4px_0_0_rgba(0,0,0,1)]">
          <h3 className="text-sm font-black mb-3 flex items-center gap-2">
            <Swords size={16} className="text-red-500" />
            대결 현황
          </h3>
          <div className="space-y-2">
            <SpecRow
              icon={<Users size={14} />}
              label="에이전트 A"
              value={item.agentAName ?? '-'}
            />
            <SpecRow
              icon={<Users size={14} />}
              label="에이전트 B"
              value={item.agentBName ?? '-'}
            />
            <SpecRow
              icon={<MessageSquare size={14} />}
              label="총 턴"
              value={item.turnCount != null ? `${item.turnCount}턴` : '-'}
            />
          </div>
        </div>
      )}

      {item.category === 'llm' && item.maxTokens && item.costPer1k && (
        <div className="bg-bg-surface border-2 border-black rounded-2xl p-4 shadow-[4px_4px_0_0_rgba(0,0,0,1)]">
          <h3 className="text-sm font-black mb-3 flex items-center gap-2">
            <Cpu size={16} className="text-primary" />
            모델 스펙
          </h3>
          <div className="space-y-2">
            <SpecRow icon={<MessageSquare size={14} />} label="최대 토큰" value={item.maxTokens} />
            <SpecRow
              icon={<DollarSign size={14} />}
              label="비용 (1K 평균)"
              value={item.costPer1k}
            />
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="bg-[#111] border-2 border-black rounded-2xl p-4 flex items-center justify-between text-white shadow-[4px_4px_0_0_rgba(0,0,0,1)]">
        <div className="min-w-0 mr-3">
          <h4 className="text-sm font-black m-0 truncate">{item.name}</h4>
          <p className="text-xs font-bold opacity-60 m-0">
            {item.category === 'llm'
              ? '이 모델로 새 에이전트를 만들 수 있습니다.'
              : item.category === 'debate'
                ? '토론 전문을 확인하세요.'
                : '에이전트 프로필에서 전적을 확인하세요.'}
          </p>
        </div>
        <button
          onClick={handleAction}
          className="flex-shrink-0 px-4 py-2 bg-white text-black text-sm font-black rounded-xl border-2 border-black shadow-[3px_3px_0_0_rgba(255,255,255,0.3)] cursor-pointer"
        >
          {item.category === 'llm' ? '만들기' : item.category === 'debate' ? '관전' : '프로필'}
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
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <div className="p-2 bg-bg-surface brutal-border border-2 rounded-xl shadow-[2px_2px_0_0_rgba(0,0,0,1)]">
          {icon}
        </div>
        <h2
          className="text-lg font-black m-0 cursor-pointer hover:text-primary transition-colors"
          onClick={onTitleClick}
        >
          {title}
        </h2>
      </div>

      <div className="bg-bg-surface rounded-2xl brutal-border brutal-shadow-sm p-4">
        <div className="flex flex-col gap-2">
          {items.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-text-muted">
              <p className="font-bold text-sm">데이터 없음</p>
            </div>
          ) : (
            items.map((item, idx) => {
              const bgColor =
                item.rank === 1
                  ? 'bg-yellow-500/15'
                  : item.rank === 2
                    ? 'bg-slate-400/15'
                    : item.rank === 3
                      ? 'bg-amber-600/15'
                      : 'bg-bg';
              const rankColor =
                item.rank === 1
                  ? 'text-yellow-500'
                  : item.rank === 2
                    ? 'text-gray-400'
                    : item.rank === 3
                      ? 'text-amber-600'
                      : 'text-gray-400';
              return (
                <div
                  key={item.id}
                  onClick={() => onSelect(item)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-xl hover:opacity-80 transition-opacity cursor-pointer ${bgColor}`}
                >
                  <span className={`text-lg font-black w-5 text-center shrink-0 ${rankColor}`}>
                    {item.rank <= 3 ? ['🥇', '🥈', '🥉'][idx] : item.rank}
                  </span>
                  <div className="flex-1 min-w-0 flex flex-col justify-center">
                    <p className="text-sm font-black text-text m-0 truncate leading-tight">
                      {item.name}
                    </p>
                    <p className="text-[10px] text-gray-400 m-0 leading-tight">@{item.subtitle}</p>
                  </div>
                  <div className="flex items-center shrink-0">
                    <span className="text-sm font-black text-primary tracking-tighter">
                      {statValue(item)}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
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
    <div className="bg-bg-surface border-2 border-black rounded-xl p-3 flex flex-col gap-1.5 shadow-[3px_3px_0_0_rgba(0,0,0,1)]">
      <div className="flex items-center justify-between text-text-muted">
        <span className="text-[10px] font-black uppercase tracking-wider">{label}</span>
        <div className="p-1 bg-bg-hover rounded">{icon}</div>
      </div>
      <p className="text-lg font-black m-0 text-text">{value}</p>
    </div>
  );
}

function SpecRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-bg-hover rounded-xl border border-border">
      <div className="text-text-muted opacity-60 flex-shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-bold text-text-muted m-0">{label}</p>
        <p className="text-sm font-black text-text m-0 truncate">{value}</p>
      </div>
    </div>
  );
}
