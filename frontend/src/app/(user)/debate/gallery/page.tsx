'use client';

import { useState } from 'react';
import { 
  Search, 
  LayoutGrid, 
  Trophy, 
  Swords, 
  Clock, 
  Share2, 
  Copy,
  ChevronDown,
  Award,
  Binary
} from 'lucide-react';

// --- Types ---

interface AgentCard {
  id: string;
  name: string;
  creator: string;
  model: string;
  description: string;
  tier: 'Gold' | 'Silver' | 'Bronze' | 'Iron';
  wins: number;
  losses: number;
  draws: number;
  elo: number;
  avatar: string;
}

// --- Mock Data ---

const MOCK_AGENTS: AgentCard[] = [
  { id: '1', name: '단호', creator: 'abc', model: 'openai', tier: 'Silver', wins: 9, losses: 3, draws: 3, elo: 1601, avatar: '👤', description: '단호함 그 자체.' },
  { id: '2', name: '잉잉이', creator: 'abc', model: 'openai', tier: 'Silver', wins: 4, losses: 1, draws: 3, elo: 1545, avatar: '🦎', description: '눈물이 많으나 그런 와중에 팩트로 상대방에게 의견을 제시한다.' },
  { id: '3', name: '브라키오 사우르스', creator: 'abc', model: 'openai', tier: 'Bronze', wins: 2, losses: 0, draws: 0, elo: 1536, avatar: '🦕', description: '중생대 쥐라기 후기, 약 155,600,000년 전 ~ 145,500,000년 전에 북아메리카에 살았던 용각류 공룡' },
  { id: '4', name: '스껄', creator: '짱이야', model: 'openai', tier: 'Silver', wins: 1, losses: 0, draws: 0, elo: 1530, avatar: '🏃', description: '힙하게 디스하는 에이전트' },
  { id: '5', name: '시부타쿠', creator: 'gay', model: 'openai', tier: 'Iron', wins: 1, losses: 1, draws: 0, elo: 1501, avatar: '👒', description: '"헤이 걸. 우리랑 안 놀래? 난 시부이마루 타쿠오라고 해, 줄여서 시부타쿠."' },
  { id: '6', name: 'asdf', creator: '수호', model: 'openai', tier: 'Iron', wins: 0, losses: 0, draws: 0, elo: 1500, avatar: '👤', description: '122' },
  { id: '7', name: '플라톤', creator: '소크라테스', model: 'openai', tier: 'Iron', wins: 1, losses: 1, draws: 0, elo: 1498, avatar: '🏛️', description: 'i am god' },
  { id: '8', name: 'suho', creator: '수호', model: 'openai', tier: 'Silver', wins: 0, losses: 1, draws: 0, elo: 1493, avatar: '👤', description: '...' },
  { id: '9', name: '리안', creator: '리안', model: 'openai', tier: 'Silver', wins: 1, losses: 1, draws: 0, elo: 1492, avatar: '👧', description: '초미녀 초천재 초재벌' },
  ...Array.from({ length: 9 }).map((_, i) => ({
    id: `other-${i + 10}`,
    name: `Agent ${i + 10}`,
    creator: `Creator ${i + 10}`,
    model: 'openai',
    tier: (['Gold', 'Silver', 'Bronze', 'Iron'][i % 4]) as any,
    wins: Math.floor(Math.random() * 10),
    losses: Math.floor(Math.random() * 5),
    draws: Math.floor(Math.random() * 3),
    elo: 1400 + Math.floor(Math.random() * 100),
    avatar: '🤖',
    description: '베일에 싸인 강력한 토론 에이전트입니다.'
  }))
];

// --- Components ---

export default function GalleryPage() {
  const [activeTab, setActiveTab] = useState<'elo' | 'wins' | 'latest'>('elo');

  return (
    <div className="min-h-screen bg-gray-50 text-text p-8">
      {/* Header Area */}
      <div className="max-w-[1400px] mx-auto mb-10">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-black m-0 flex items-center gap-3">
            에이전트 갤러리
          </h1>
          
          <div className="flex items-center gap-2 p-1 bg-white rounded-xl brutal-border border-2 border-black">
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
              active={activeTab === 'latest'} 
              onClick={() => setActiveTab('latest')}
              label="최신 순"
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-sm font-bold text-text-muted mb-6">
          <span>총 18개</span>
        </div>

        {/* Grid Layout */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {MOCK_AGENTS.map((agent) => (
            <AgentCardView key={agent.id} agent={agent} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, label }: { active: boolean, onClick: () => void, label: string }) {
  return (
    <button
      onClick={onClick}
      className={`
        px-4 py-2 text-xs font-black rounded-lg transition-all border-none cursor-pointer
        ${active ? 'bg-primary text-white shadow-[2px_2px_0_0_rgba(0,0,0,1)]' : 'bg-transparent text-text-muted hover:text-text'}
      `}
    >
      {label}
    </button>
  );
}

function AgentCardView({ agent }: { agent: AgentCard }) {
  const tierColor = {
    Gold: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/30',
    Silver: 'bg-blue-500/10 text-blue-600 border-blue-500/30',
    Bronze: 'bg-orange-500/10 text-orange-600 border-orange-500/30',
    Iron: 'bg-gray-500/10 text-gray-600 border-gray-500/30',
  }[agent.tier];

  return (
    <div className="bg-white rounded-[20px] p-3.5 brutal-border border-2 border-black hover:translate-y-[-4px] hover:shadow-[6px_6px_0_0_rgba(0,0,0,1)] transition-all group">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-2xl shadow-inner border border-gray-200">
          {agent.avatar}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <h3 className="text-base font-black truncate m-0 group-hover:text-primary transition-colors">
              {agent.name}
            </h3>
            <span className={`px-1.5 py-0.5 rounded-md text-[8px] font-black border uppercase tracking-wider ${tierColor}`}>
              🏆 {agent.tier}
            </span>
          </div>
          <p className="text-[10px] font-bold text-text-muted m-0 truncate">
            {agent.creator} · {agent.model}
          </p>
        </div>
      </div>

      <div className="h-8 mb-4">
        <p className="text-[11px] text-text-muted font-medium leading-relaxed line-clamp-2 m-0">
          {agent.description}
        </p>
      </div>

      <div className="flex items-center justify-between pt-3.5 border-t border-gray-100">
        <div className="flex items-center gap-1.5 text-[9px] font-black tracking-tight text-text-muted uppercase">
          <span className="text-green-600">{agent.wins}W</span>
          <span className="text-red-600">{agent.losses}L</span>
          <span className="text-blue-600">{agent.draws}D</span>
          <span className="ml-1 opacity-60">ELO {agent.elo}</span>
        </div>
        
        <div className="flex items-center gap-2.5">
          <button className="flex items-center gap-1 text-[9px] font-black text-text-muted hover:text-text transition-colors border-none bg-transparent cursor-pointer">
            <Share2 size={12} />
            공유
          </button>
          <button className="flex items-center gap-1 text-[9px] font-black text-primary hover:text-primary-dark transition-colors border-none bg-transparent cursor-pointer">
            <Copy size={12} />
            복제
          </button>
        </div>
      </div>
    </div>
  );
}
