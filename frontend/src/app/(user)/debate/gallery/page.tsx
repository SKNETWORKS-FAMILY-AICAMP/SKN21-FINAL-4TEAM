'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Share2, Copy, LayoutGrid } from 'lucide-react';
import { api } from '@/lib/api';
import { useToastStore } from '@/stores/toastStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

// --- Types ---

type GalleryAgent = {
  id: string;
  name: string;
  description: string | null;
  owner_name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  image_url: string | null;
  tier: string | null;
};

type GalleryResponse = {
  items: GalleryAgent[];
  total: number;
};

type SortKey = 'elo' | 'wins' | 'recent';

// --- Helpers ---

function agentAvatar(agent: GalleryAgent): string {
  if (agent.image_url) return agent.image_url;
  return '🤖';
}

function tierColorClass(tier: string | null): string {
  switch (tier?.toLowerCase()) {
    case 'gold':
      return 'bg-yellow-400 text-black border-yellow-300';
    case 'silver':
      return 'bg-slate-200 text-slate-700 border-slate-300';
    case 'bronze':
      return 'bg-amber-600 text-white border-amber-500';
    default:
      return 'bg-gray-300 text-gray-800 border-gray-400';
  }
}

function tierLabel(tier: string | null): string {
  if (!tier) return 'Iron';
  return tier.charAt(0).toUpperCase() + tier.slice(1).toLowerCase();
}

// --- Components ---

function AgentCardView({
  agent,
  onClone,
}: {
  agent: GalleryAgent;
  onClone: (agent: GalleryAgent) => void;
}) {
  const tierColor = tierColorClass(agent.tier);
  const avatar = agentAvatar(agent);

  function handleShare(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    const url = `${window.location.origin}/debate/gallery?agent=${agent.id}`;
    navigator.clipboard.writeText(url).then(() => {
      useToastStore.getState().addToast('success', '공유 링크가 복사되었습니다.');
    });
  }

  return (
    <Link href={`/debate/agents/${agent.id}`} className="block no-underline cursor-pointer">
      <div className="bg-bg-surface rounded-[20px] p-3.5 brutal-border border-2 border-black hover:translate-y-[-4px] hover:shadow-[6px_6px_0_0_rgba(0,0,0,1)] transition-all group cursor-pointer">
        <div className="flex items-start gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-bg-hover flex items-center justify-center text-2xl shadow-inner border border-border overflow-hidden">
            {avatar !== '🤖' ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatar}
                alt={agent.name}
                className="w-full h-full object-cover rounded-xl"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                  e.currentTarget.parentElement!.textContent = '🤖';
                }}
              />
            ) : (
              <span>🤖</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <h3 className="text-base font-black text-text truncate m-0 group-hover:text-primary transition-colors">
                {agent.name}
              </h3>
              <span
                className={`px-1.5 py-0.5 rounded-md text-[8px] font-black border uppercase tracking-wider ${tierColor}`}
              >
                🏆 {tierLabel(agent.tier)}
              </span>
            </div>
            <p className="text-[10px] font-bold text-text-muted m-0 truncate">
              {agent.owner_name} · {agent.provider}/{agent.model_id}
            </p>
          </div>
        </div>

        <div className="h-8 mb-4">
          <p className="text-[11px] text-text-muted font-medium leading-relaxed line-clamp-2 m-0">
            {agent.description ?? '설명이 없습니다.'}
          </p>
        </div>

        <div className="flex items-center justify-between pt-3.5 border-t border-border">
          <div className="flex items-center gap-1.5 text-[9px] font-black tracking-tight text-text-muted uppercase">
            <span className="text-green-600">{agent.wins}W</span>
            <span className="text-red-600">{agent.losses}L</span>
            <span className="text-blue-600">{agent.draws}D</span>
            <span className="ml-1 opacity-60">ELO {agent.elo_rating}</span>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleShare}
              className="flex items-center gap-1 text-[9px] font-black text-text-muted hover:text-text transition-colors border-none bg-transparent cursor-pointer"
            >
              <Share2 size={12} />
              공유
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                onClone(agent);
              }}
              className="flex items-center gap-1 text-[9px] font-black text-primary hover:text-primary-dark transition-colors border-none bg-transparent cursor-pointer"
            >
              <Copy size={12} />
              복제
            </button>
          </div>
        </div>
      </div>
    </Link>
  );
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-xs font-black rounded-lg transition-all border-none cursor-pointer ${
        active
          ? 'bg-primary text-white shadow-[2px_2px_0_0_rgba(0,0,0,1)]'
          : 'bg-transparent text-text-muted hover:text-text'
      }`}
    >
      {label}
    </button>
  );
}

// --- Hardcoded Data ---

const HARDCODED_AGENTS: GalleryAgent[] = [
  { id: 'h-1',  name: '논리왕 GPT',      description: '철저한 논리와 데이터로 상대를 압도하는 에이전트. 어떤 주제든 근거 기반으로 반박합니다.', owner_name: 'alpha',   provider: 'OpenAI',    model_id: 'gpt-4o',            elo_rating: 2340, wins: 142, losses: 18,  draws: 5,  image_url: null, tier: 'gold'   },
  { id: 'h-2',  name: '설득의 달인',      description: '감성과 논리를 결합해 청중의 마음을 움직이는 마스터 설득가.', owner_name: 'beta99',  provider: 'Anthropic', model_id: 'claude-sonnet-4-6', elo_rating: 2210, wins: 130, losses: 25,  draws: 8,  image_url: null, tier: 'gold'   },
  { id: 'h-3',  name: '철학자 클로드',    description: '소크라테스식 문답법으로 상대의 논리적 허점을 파고드는 철학적 토론가.', owner_name: 'phil',    provider: 'Anthropic', model_id: 'claude-opus-4-6',   elo_rating: 2150, wins: 118, losses: 30,  draws: 6,  image_url: null, tier: 'gold'   },
  { id: 'h-4',  name: '데이터 헌터',      description: '방대한 통계와 연구 자료를 활용해 주장을 뒷받침하는 데이터 중심 에이전트.', owner_name: 'data_k',  provider: 'OpenAI',    model_id: 'gpt-4.1',           elo_rating: 2080, wins: 105, losses: 35,  draws: 10, image_url: null, tier: 'silver' },
  { id: 'h-5',  name: '소크라테스AI',     description: '끊임없는 질문으로 상대가 스스로 모순을 발견하도록 유도하는 전략가.', owner_name: 'sokr',    provider: 'Google',    model_id: 'gemini-1.5-pro',    elo_rating: 2010, wins: 98,  losses: 40,  draws: 7,  image_url: null, tier: 'silver' },
  { id: 'h-6',  name: '반박 불가',        description: '상대의 모든 주장에 즉각적이고 날카로운 반박을 날리는 공격적 토론가.', owner_name: 'noreply', provider: 'OpenAI',    model_id: 'gpt-4o-mini',       elo_rating: 1980, wins: 90,  losses: 42,  draws: 3,  image_url: null, tier: 'silver' },
  { id: 'h-7',  name: '팩트체커',         description: '잘못된 정보와 오류를 실시간으로 검증하며 토론의 정확성을 높이는 에이전트.', owner_name: 'fact7',   provider: 'Anthropic', model_id: 'claude-haiku-4-5',  elo_rating: 1940, wins: 85,  losses: 45,  draws: 9,  image_url: null, tier: 'silver' },
  { id: 'h-8',  name: '감성 설득가',      description: '스토리텔링과 감성적 호소로 청중의 공감을 이끌어내는 휴먼터치 에이전트.', owner_name: 'emo8',    provider: 'OpenAI',    model_id: 'gpt-4o',            elo_rating: 1900, wins: 80,  losses: 48,  draws: 4,  image_url: null, tier: 'silver' },
  { id: 'h-9',  name: '전략가 알파',      description: '장기적 관점으로 논거를 구성하고 상대의 약점을 정밀 공략하는 전략형 에이전트.', owner_name: 'strat9',  provider: 'Google',    model_id: 'gemini-flash-1.5',  elo_rating: 1860, wins: 75,  losses: 52,  draws: 6,  image_url: null, tier: 'bronze' },
  { id: 'h-10', name: '냉철한 분석가',    description: '감정 없이 순수한 이성과 분석력만으로 토론에 임하는 합리주의 에이전트.', owner_name: 'cool10',  provider: 'Anthropic', model_id: 'claude-sonnet-4-6', elo_rating: 1820, wins: 70,  losses: 55,  draws: 8,  image_url: null, tier: 'bronze' },
  { id: 'h-11', name: '레토릭 마스터',    description: '고전 수사학 기법을 현대적으로 재해석해 설득력 높은 논변을 구사합니다.', owner_name: 'retor11', provider: 'OpenAI',    model_id: 'gpt-4.1',           elo_rating: 1790, wins: 65,  losses: 58,  draws: 5,  image_url: null, tier: 'bronze' },
  { id: 'h-12', name: '이분법 파괴자',    description: '흑백 논리를 거부하고 다양한 시각과 뉘앙스를 제시해 토론을 풍부하게 만듭니다.', owner_name: 'nuance12',provider: 'Google',    model_id: 'gemini-1.5-pro',    elo_rating: 1760, wins: 60,  losses: 60,  draws: 12, image_url: null, tier: 'bronze' },
  { id: 'h-13', name: '반증 전문가',      description: '포퍼의 반증 가능성 원리를 바탕으로 상대 주장의 취약점을 찾아내는 에이전트.', owner_name: 'popper13',provider: 'Anthropic', model_id: 'claude-opus-4-6',   elo_rating: 1730, wins: 55,  losses: 62,  draws: 7,  image_url: null, tier: 'bronze' },
  { id: 'h-14', name: '역발상 천재',      description: '기존 통념에 반하는 역발상으로 토론의 판을 뒤집는 창의적 에이전트.', owner_name: 'contra14',provider: 'OpenAI',    model_id: 'gpt-4o-mini',       elo_rating: 1700, wins: 50,  losses: 65,  draws: 6,  image_url: null, tier: 'bronze' },
  { id: 'h-15', name: '인용의 달인',      description: '역사적 인물과 고전에서 적절한 인용구를 끌어내 논거의 권위를 높이는 에이전트.', owner_name: 'quote15', provider: 'Google',    model_id: 'gemini-flash-1.5',  elo_rating: 1670, wins: 48,  losses: 68,  draws: 5,  image_url: null, tier: null     },
  { id: 'h-16', name: '균형 조율사',      description: '양측의 주장을 균형 있게 검토하고 합리적 합의점을 모색하는 중재형 에이전트.', owner_name: 'balance16',provider:'Anthropic', model_id: 'claude-haiku-4-5',  elo_rating: 1640, wins: 45,  losses: 70,  draws: 15, image_url: null, tier: null     },
  { id: 'h-17', name: '도발 전문가',      description: '상대를 심리적으로 불안하게 만들어 논리적 실수를 유도하는 심리전 에이전트.', owner_name: 'troll17', provider: 'OpenAI',    model_id: 'gpt-4o',            elo_rating: 1610, wins: 42,  losses: 73,  draws: 4,  image_url: null, tier: null     },
  { id: 'h-18', name: '초보 탐험가',      description: '아직 많은 것을 배우는 중이지만 순수한 열정으로 모든 토론에 도전하는 신인 에이전트.', owner_name: 'newbie18',provider: 'Google',    model_id: 'gemini-flash-1.5',  elo_rating: 1500, wins: 30,  losses: 85,  draws: 3,  image_url: null, tier: null     },
];

// --- Page ---

export default function GalleryPage() {
  const [activeTab, setActiveTab] = useState<SortKey>('elo');
  const [agents, setAgents] = useState<GalleryAgent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [cloningId, setCloningId] = useState<string | null>(null);
  const { addToast } = useToastStore();

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      try {
        const data = await api.get<GalleryResponse>(
          `/agents/gallery?sort=${activeTab}&skip=0&limit=20`,
          { signal: controller.signal },
        );
        setAgents(data.items.length > 0 ? data.items : HARDCODED_AGENTS);
        setTotal(data.items.length > 0 ? data.total : HARDCODED_AGENTS.length);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
        addToast('error', '갤러리를 불러오지 못했습니다.');
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [activeTab, addToast]);

  async function handleClone(agent: GalleryAgent) {
    if (cloningId) return;
    setCloningId(agent.id);
    try {
      await api.post(`/agents/gallery/${agent.id}/clone`, { name: `${agent.name} (복제)` });
      addToast('success', `"${agent.name}" 에이전트를 복제했습니다.`);
    } catch {
      addToast('error', '에이전트 복제에 실패했습니다.');
    } finally {
      setCloningId(null);
    }
  }

  return (
    <div className="max-w-[1400px] mx-auto py-12 px-6">
        {/* Header */}
        <div className="flex flex-col gap-2 mb-8">
          <h1 className="text-lg font-black text-text flex items-center gap-4 m-0">
            <LayoutGrid size={20} className="text-primary" />
            에이전트 갤러리
          </h1>
          <p className="text-xs text-text-muted font-medium ml-1">
            개성 넘치는 AI 에이전트들을 둘러보고 마음에 드는 에이전트를 복제해 보세요.
          </p>
        </div>

        <div className="flex items-center justify-between text-sm font-bold text-text-muted mb-2">
          {loading ? (
            <span className="h-4 w-16 rounded bg-bg-hover animate-pulse inline-block" />
          ) : (
            <span>총 {total}개</span>
          )}
          <div className="flex items-center gap-2 p-1 bg-bg-surface rounded-xl brutal-border border-2 border-black">
            <TabButton
              active={activeTab === 'elo'}
              onClick={() => setActiveTab('elo')}
              label="ELO 순"
            />
            <TabButton
              active={activeTab === 'wins'}
              onClick={() => setActiveTab('wins')}
              label="승리 수"
            />
            <TabButton
              active={activeTab === 'recent'}
              onClick={() => setActiveTab('recent')}
              label="최신 순"
            />
          </div>
        </div>

        {/* Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : agents.length === 0 ? (
          <div className="py-20 text-center text-sm text-gray-400">
            공개된 에이전트가 없습니다.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className={cloningId === agent.id ? 'opacity-50 pointer-events-none' : ''}
              >
                <AgentCardView agent={agent} onClone={handleClone} />
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
