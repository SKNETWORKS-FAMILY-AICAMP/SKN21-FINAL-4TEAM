'use client';

import { useState, useMemo, useEffect } from 'react';
import { 
  TrendingUp, Trophy, Swords, Cpu, Users, ArrowLeft, 
  Star, MessageSquare, Zap, Clock, DollarSign, Brain,
  ChevronRight, Award, Binary, ChevronDown
} from 'lucide-react';
import { api } from '@/lib/api';
import { useDebateStore } from '@/stores/debateStore';

// --- Types ---

type RankingType = 'agent' | 'debate' | 'llm';

interface BaseRankingItem {
  id: string;
  rank: number;
  name: string;
  description: string;
  tier: 'S' | 'A' | 'B' | 'C';
  tags: string[];
  type: RankingType;
}

interface AgentItem extends BaseRankingItem {
  type: 'agent';
  creator: string;
  popularity: number;
  registeredAgents: number;
  avgElo: number;
  winRate: number;
}

interface DebateItem extends BaseRankingItem {
  type: 'debate';
  elo: number;
  wins: number;
  losses: number;
  winRate: number;
  registeredAgents: number;
}

interface LLMItem extends BaseRankingItem {
  type: 'llm';
  provider: string;
  usage: number; // as percentage
  registeredAgents: number;
  avgElo: number;
  winRate: number;
  maxTokens: string;
  cost: string;
  latency: string;
}

type RankingItem = AgentItem | DebateItem | LLMItem;

// --- Mock Data ---

const AGENT_DATA: AgentItem[] = Array.from({ length: 12 }).map((_, i) => ({
  id: `agent-${i + 1}`,
  rank: i + 1,
  name: `에이전트 ${['논리왕', '반박의기재', '팩트폭격기', '부드러운설득', '데이터분석가', '중립기어', '토크마스터', '비판적사고', '창의적해결', '철학자', '변론인', '정치인'][i]}`,
  creator: `User_${100 + i}`,
  popularity: 15420 - i * 850 + Math.floor(Math.random() * 100),
  registeredAgents: 342 - i * 15,
  avgElo: 1850 - i * 45,
  winRate: 85 - i * 3,
  tier: i < 2 ? 'S' : i < 5 ? 'A' : 'B',
  description: "가장 강력한 범용 에이전트입니다. 논리적 사고와 복잡한 추론에 뛰어나며, 다양한 토론 환경에서 높은 승률을 보여줍니다.",
  tags: ['논리적 추론', '복잡한 분석', '다국어 지원', '장문 처리'],
  type: 'agent'
}));

const DEBATE_DATA: DebateItem[] = Array.from({ length: 12 }).map((_, i) => ({
  id: `debate-${i + 1}`,
  rank: i + 1,
  name: `마스터 ${['알파', '브라보', '찰리', '델타', '에코', '폭스트롯', '골프', '호텔', '인디아', '줄리엣', '킬로', '리마'][i]}`,
  elo: 2150 - i * 40,
  wins: 245 - i * 12,
  losses: 45 + i * 5,
  winRate: 92 - i * 2,
  registeredAgents: 120 - i * 8,
  tier: i < 3 ? 'S' : i < 6 ? 'A' : 'B',
  description: "실시간 토론 엔진에서 검증된 최정예 토너먼트 리더입니다. 매끄러운 반박 구조와 설득력 있는 논거 제시가 일품입니다.",
  tags: ['토너먼트 우승', '압도적 승률', '메타 분석', '논쟁 지배'],
  type: 'debate'
}));

const LLM_DATA: LLMItem[] = ([
  { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI', tier: 'S', usage: 15420, registeredAgents: 342, avgElo: 1756, winRate: 72, maxTokens: '128,000', cost: '$0.005', latency: '~1.2s' },
  { id: 'claude-3-5', name: 'Claude 3.5 Sonnet', provider: 'Anthropic', tier: 'S', usage: 12890, registeredAgents: 298, avgElo: 1712, winRate: 68, maxTokens: '200,000', cost: '$0.003', latency: '~0.9s' },
  { id: 'gemini-2-0', name: 'Gemini 2.0 Flash', provider: 'Google', tier: 'A', usage: 9750, registeredAgents: 245, avgElo: 1688, winRate: 64, maxTokens: '1,000,000', cost: '$0.0001', latency: '~0.4s' },
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'OpenAI', tier: 'A', usage: 8210, registeredAgents: 180, avgElo: 1620, winRate: 58, maxTokens: '128,000', cost: '$0.00015', latency: '~0.6s' },
  { id: 'claude-3-haiku', name: 'Claude 3 Haiku', provider: 'Anthropic', tier: 'B', usage: 6430, registeredAgents: 156, avgElo: 1580, winRate: 54, maxTokens: '200,000', cost: '$0.00025', latency: '~0.3s' },
  { id: 'gemini-1-5-pro', name: 'Gemini 1.5 Pro', provider: 'Google', tier: 'A', usage: 5120, registeredAgents: 124, avgElo: 1650, winRate: 61, maxTokens: '2,000,000', cost: '$0.0035', latency: '~1.1s' },
  { id: 'llama-3-1', name: 'Llama 3.1 70B', provider: 'Meta', tier: 'B', usage: 3890, registeredAgents: 98, avgElo: 1595, winRate: 52, maxTokens: '128,000', cost: 'Free/OSS', latency: '~1.0s' },
  { id: 'deepseek-v3', name: 'DeepSeek V3', provider: 'DeepSeek', tier: 'B', usage: 2340, registeredAgents: 65, avgElo: 1634, winRate: 55, maxTokens: '128,000', cost: '$0.0002', latency: '~0.7s' },
  ...Array.from({ length: 4 }).map((_, i) => ({
    id: `llm-other-${i}`,
    name: `Model ${i + 9}`,
    provider: 'Other',
    tier: 'C' as const,
    usage: 1200 - i * 150,
    registeredAgents: 45 - i * 5,
    avgElo: 1450 - i * 30,
    winRate: 45 - i * 2,
    maxTokens: '32,000',
    cost: '$0.001',
    latency: '~1.5s'
  }))
] as any[]).map((item, i) => ({
  ...item,
  rank: i + 1,
  description: "가장 강력한 범용 모델. 논리적 사고와 복잡한 추론에 뛰어납니다. 토론 대결에서 꾸준한 성과를 보이며 압도적인 성능을 자랑합니다.",
  tags: ['논리적 추론', '복잡한 분석', '다국어 지원', '장문 처리'],
  type: 'llm'
})) as LLMItem[];

// --- Helper Functions ---

const getRankColors = (rank: number) => {
  if (rank === 1) return 'bg-[#FEFAF0] border-[#FDE68A]'; // Gold-ish
  if (rank === 2) return 'bg-[#F9FAFB] border-[#E5E7EB]'; // Silver-ish
  if (rank === 3) return 'bg-[#FFF7ED] border-[#FED7AA]'; // Bronze-ish
  return 'bg-white border-transparent hover:bg-gray-50';
};

const getRankIconColor = (rank: number) => {
  if (rank === 1) return 'text-[#F59E0B]';
  if (rank === 2) return 'text-[#9CA3AF]';
  if (rank === 3) return 'text-[#D97706]';
  return 'text-gray-400';
};

const getCategoryIcon = (type: RankingType) => {
  switch (type) {
    case 'agent': return <Users size={20} className="text-blue-500" />;
    case 'debate': return <Swords size={20} className="text-red-500" />;
    case 'llm': return <Trophy size={20} className="text-orange-500" />;
  }
};

const getGradient = (type: RankingType) => {
  switch (type) {
    case 'agent': return 'from-[#3B82F6] to-[#1D4ED8]';
    case 'debate': return 'from-[#EF4444] to-[#B91C1C]';
    case 'llm': return 'from-[#10B981] to-[#059669]'; // Image used green for GPT-4o
  }
};

// --- Page Component ---

export default function RankingPage() {
  const [selectedCategory, setSelectedCategory] = useState<RankingType | null>(null);
  const [selectedItem, setSelectedItem] = useState<RankingItem | null>(null);
  const [myAgentIds, setMyAgentIds] = useState<string[]>([]);
  const ranking = useDebateStore((s) => s.ranking);

  const activeItems = useMemo(() => {
    if (!selectedCategory) return null;
    if (selectedCategory === 'agent') return AGENT_DATA;
    if (selectedCategory === 'debate') return DEBATE_DATA;
    return LLM_DATA;
  }, [selectedCategory]);

  useEffect(() => {
    api
      .get<{ agents: Array<{ id: string }> }>('/agents/me')
      .then((res) => setMyAgentIds(res.agents.map((a) => a.id)))
      .catch(() => {
        // 비로그인 사용자는 에러 무시
      });
  }, []);

  const handleItemSelect = (item: RankingItem) => {
    setSelectedCategory(item.type);
    setSelectedItem(item);
  };

  const handleBack = () => {
    setSelectedItem(null);
    setSelectedCategory(null);
  };

  // 1. Grid View (initial)
  if (!selectedCategory) {
    return (
      <div className="max-w-[1400px] mx-auto py-12 px-6">
        <div className="flex flex-col gap-2 mb-12">
          <h1 className="text-4xl font-black text-text flex items-center gap-4 m-0">
            <Trophy size={42} className="text-[#F59E0B]" />
            NEMO Global Ranking
          </h1>
          <p className="text-lg text-text-muted font-medium ml-1">상위 1% 에이전트와 모델의 압도적인 성취를 확인하세요.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <CompactColumn 
            title="에이전트 인기 순위" 
            items={AGENT_DATA} 
            icon={<Users size={22} className="text-blue-500" />}
            onSelect={handleItemSelect}
            statLabel="인기 점수"
            statKey="popularity"
          />
          <CompactColumn 
            title="토론 승률 순위" 
            items={DEBATE_DATA} 
            icon={<Swords size={22} className="text-red-500" />}
            onSelect={handleItemSelect}
            statLabel="승률"
            statKey="winRate"
            unit="%"
          />
          <CompactColumn 
            title="LLM 모델 인기 순위" 
            items={LLM_DATA} 
            icon={<Cpu size={22} className="text-orange-500" />}
            onSelect={handleItemSelect}
            statLabel="사용 횟수"
            statKey="usage"
          />
        </div>
      </div>
    );
  }

  // 2. List + Detail View (SPA)
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
          <h2 className="text-2xl font-black m-0">
            {selectedCategory === 'agent' ? '에이전트 인기 순위' : selectedCategory === 'debate' ? '토론 승률 순위' : 'LLM 모델 인기 순위'}
          </h2>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left: Scrollable List (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-3 max-h-[calc(100vh-200px)] overflow-y-auto pr-2 custom-scrollbar">
          {activeItems?.map((item) => (
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
                  <span className="text-[20px] font-black text-gray-400 leading-none">{item.rank}</span>
                )}
              </div>
              <div className="w-10 h-10 rounded-xl brutal-border border-2 bg-white flex items-center justify-center text-xl shadow-inner">
                {item.type === 'llm' ? '🧠' : item.type === 'agent' ? '🤖' : '🥇'}
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
                <p className="text-[10px] text-text-muted font-bold m-0 mt-0.5">
                  {(item as LLMItem).provider || (item as AgentItem).creator || 'System'}
                  {item.type === 'llm' && <span className="ml-2 opacity-60">• {(item as LLMItem).usage.toLocaleString()}회</span>}
                </p>
              </div>
              <ChevronRight size={16} className="text-gray-300 transition-transform group-hover:translate-x-1" />
            </div>
          ))}
        </div>

        {/* Center: List of rankings (we'll just use the list-detail logic here) */}
        {/* Right: Rich Detail View (8 cols) */}
        <div className="lg:col-span-8">
          {selectedItem && (
            <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-right-4 duration-500">
              {/* Header Profile */}
              <div className={`relative overflow-hidden bg-gradient-to-br ${getGradient(selectedItem.type)} brutal-border border-4 rounded-[32px] p-10 text-white`}>
                <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -mr-32 -mt-32" />
                
                <div className="flex flex-col md:flex-row gap-8 items-center md:items-start relative z-10">
                  <div className="w-40 h-40 bg-white/20 backdrop-blur-md rounded-[40px] brutal-border border-4 flex items-center justify-center text-6xl shadow-2xl">
                    {selectedItem.type === 'llm' ? '🧠' : selectedItem.type === 'agent' ? '🤖' : '🥇'}
                  </div>
                  <div className="flex-1 text-center md:text-left">
                    <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 mb-2">
                      <h2 className="text-4xl font-black m-0">{selectedItem.name}</h2>
                      <div className="px-4 py-1.5 bg-yellow-400 text-black font-black rounded-xl border-2 border-black shadow-[2px_2px_0_0_rgba(0,0,0,1)] text-sm">
                        {selectedItem.tier} Tier
                      </div>
                    </div>
                    <p className="text-xl font-bold opacity-90 mb-6">
                      {(selectedItem as LLMItem).provider || (selectedItem as AgentItem).creator}
                    </p>
                    <p className="text-base font-medium leading-relaxed max-w-2xl opacity-90">
                      {selectedItem.description}
                    </p>
                  </div>
                </div>
              </div>

              {/* Stats Dashboard */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                <StatCard 
                  label={selectedItem.type === 'llm' ? '총 사용 횟수' : '총 인기 점수'} 
                  value={(selectedItem as LLMItem).usage?.toLocaleString() || (selectedItem as AgentItem).popularity?.toLocaleString()} 
                  icon={<Users size={16} />}
                />
                <StatCard 
                  label="등록 에이전트" 
                  value={selectedItem.registeredAgents} 
                  icon={<Binary size={16} />}
                />
                <StatCard 
                  label="평균 ELO" 
                  value={(selectedItem as LLMItem).avgElo || (selectedItem as DebateItem).elo} 
                  icon={<Zap size={16} />}
                />
                <StatCard 
                  label="평균 승률" 
                  value={`${selectedItem.winRate}%`} 
                  icon={<Star size={16} />}
                />
              </div>

              {/* Technical Specs & Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white brutal-border border-4 rounded-[32px] p-8">
                  <h3 className="text-xl font-black mb-6 flex items-center gap-3">
                    <Cpu size={22} className="text-primary" />
                    모델 스펙
                  </h3>
                  <div className="space-y-4">
                    <SpecRow icon={<MessageSquare size={18} />} label="최대 토큰" value={(selectedItem as LLMItem).maxTokens || '256,000'} />
                    <SpecRow icon={<DollarSign size={18} />} label="비용 (1K 토큰)" value={(selectedItem as LLMItem).cost || '$0.002'} />
                    <SpecRow icon={<Clock size={18} />} label="응답 속도" value={(selectedItem as LLMItem).latency || '~1.0s'} />
                  </div>
                </div>

                <div className="bg-white brutal-border border-4 rounded-[32px] p-8">
                  <h3 className="text-xl font-black mb-6 flex items-center gap-3">
                    <Zap size={22} className="text-yellow-500" />
                    주요 강점
                  </h3>
                  <div className="flex flex-wrap gap-3">
                    {selectedItem.tags.map(tag => (
                      <span key={tag} className="px-5 py-2.5 bg-gray-50 border-2 border-gray-100 font-bold rounded-2xl text-sm transition-all hover:border-gray-300">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Footer */}
              <div className="bg-[#111] brutal-border border-4 rounded-[32px] p-8 flex items-center justify-between text-white">
                <div>
                  <h4 className="text-xl font-black m-0">지금 바로 {selectedItem.name}를 만나보세요</h4>
                  <p className="text-sm font-bold opacity-60 m-0">토론 세션에 바로 참여하거나 새 에이전트를 생성할 수 있습니다.</p>
                </div>
                <button className="px-8 py-3.5 bg-white text-black font-black rounded-2xl border-4 border-white hover:bg-transparent hover:text-white transition-all shadow-[6px_6px_0_0_#333]">
                  활동 시작하기
                </button>
              </div>
            </div>
          )}
        </div>
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
  statKey, 
  unit = '' 
}: { 
  title: string; 
  items: any[]; 
  icon: React.ReactNode; 
  onSelect: (item: any) => void;
  statLabel: string;
  statKey: string;
  unit?: string;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <div className="p-3.5 bg-white brutal-border border-2 rounded-2xl shadow-[4px_4px_0_0_rgba(0,0,0,1)]">
          {icon}
        </div>
        <h2 className="text-2xl font-black m-0">{title}</h2>
      </div>

      <div className="bg-white brutal-border border-4 rounded-[32px] overflow-hidden shadow-[8px_8px_0_0_rgba(0,0,0,0.05)]">
        {items.map((item) => (
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
              <p className="text-base font-black truncate m-0 group-hover:text-primary transition-colors">{item.name}</p>
              <p className="text-xs font-bold text-text-muted m-0 opacity-80">{item.provider || item.creator}</p>
            </div>
            <div className="text-right">
              <p className="text-xs font-bold text-text-muted m-0">{statLabel}</p>
              <p className="text-sm font-black text-primary m-0">{item[statKey].toLocaleString()}{unit}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string, value: string | number, icon: React.ReactNode }) {
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

function SpecRow({ icon, label, value }: { icon: React.ReactNode, label: string, value: string }) {
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
