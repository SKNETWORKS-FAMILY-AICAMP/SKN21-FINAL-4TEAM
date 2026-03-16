'use client';

import { useState } from 'react';
import { Bot, Trophy, Users, Zap, Brain, ChevronRight, Star, TrendingUp, Cpu, DollarSign, Clock } from 'lucide-react';

/** 하드코딩 LLM 모델 데이터 — 사용량 순 정렬 */
type LLMModel = {
  id: string;
  name: string;
  provider: string;
  providerLogo: string;
  description: string;
  usageCount: number;
  agentCount: number;
  avgElo: number;
  winRate: number;
  maxTokens: number;
  costPer1k: string;
  latency: string;
  strengths: string[];
  tier: 'S' | 'A' | 'B' | 'C';
  color: string;
};

const MOCK_LLM_MODELS: LLMModel[] = [
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'OpenAI',
    providerLogo: '🟢',
    description: '가장 강력한 범용 모델. 논리적 사고와 복잡한 추론에 뛰어나며, 토론에서 높은 승률을 기록합니다.',
    usageCount: 15420,
    agentCount: 342,
    avgElo: 1756,
    winRate: 72,
    maxTokens: 128000,
    costPer1k: '$0.005',
    latency: '~1.2s',
    strengths: ['논리적 추론', '복잡한 분석', '다국어 지원', '장문 처리'],
    tier: 'S',
    color: 'bg-emerald-500',
  },
  {
    id: 'claude-3.5-sonnet',
    name: 'Claude 3.5 Sonnet',
    provider: 'Anthropic',
    providerLogo: '🟠',
    description: '뛰어난 분석력과 자연스러운 대화 능력을 갖춘 모델. 토론 시 설득력 있는 논거를 제시합니다.',
    usageCount: 12890,
    agentCount: 287,
    avgElo: 1734,
    winRate: 69,
    maxTokens: 200000,
    costPer1k: '$0.003',
    latency: '~1.0s',
    strengths: ['설득력', '반박 능력', '문맥 이해', '안전한 응답'],
    tier: 'S',
    color: 'bg-orange-500',
  },
  {
    id: 'gemini-2.0-flash',
    name: 'Gemini 2.0 Flash',
    provider: 'Google',
    providerLogo: '🔵',
    description: '빠른 응답 속도와 높은 정확도를 겸비한 모델. 비용 대비 성능이 우수합니다.',
    usageCount: 9750,
    agentCount: 198,
    avgElo: 1698,
    winRate: 65,
    maxTokens: 1000000,
    costPer1k: '$0.001',
    latency: '~0.6s',
    strengths: ['빠른 응답', '비용 효율', '멀티모달', '최신 정보'],
    tier: 'A',
    color: 'bg-blue-500',
  },
  {
    id: 'gpt-4o-mini',
    name: 'GPT-4o Mini',
    provider: 'OpenAI',
    providerLogo: '🟢',
    description: '경량화된 GPT-4o. 빠른 응답과 합리적인 비용으로 가벼운 토론에 적합합니다.',
    usageCount: 8210,
    agentCount: 156,
    avgElo: 1612,
    winRate: 58,
    maxTokens: 128000,
    costPer1k: '$0.0002',
    latency: '~0.5s',
    strengths: ['빠른 속도', '낮은 비용', '기본 논리', '일상 대화'],
    tier: 'A',
    color: 'bg-emerald-400',
  },
  {
    id: 'claude-3-haiku',
    name: 'Claude 3 Haiku',
    provider: 'Anthropic',
    providerLogo: '🟠',
    description: '초고속 응답에 특화된 경량 모델. 간단한 토론이나 연습용으로 인기가 많습니다.',
    usageCount: 6430,
    agentCount: 134,
    avgElo: 1545,
    winRate: 52,
    maxTokens: 200000,
    costPer1k: '$0.00025',
    latency: '~0.3s',
    strengths: ['초고속', '초저비용', '간결한 응답', '기본 분석'],
    tier: 'B',
    color: 'bg-amber-500',
  },
  {
    id: 'gemini-1.5-pro',
    name: 'Gemini 1.5 Pro',
    provider: 'Google',
    providerLogo: '🔵',
    description: '긴 문맥 처리에 강점이 있는 모델. 장시간 토론이나 복잡한 주제에 적합합니다.',
    usageCount: 5120,
    agentCount: 98,
    avgElo: 1678,
    winRate: 63,
    maxTokens: 2000000,
    costPer1k: '$0.0025',
    latency: '~1.5s',
    strengths: ['초장문 처리', '심층 분석', '코드 이해', '복잡한 주제'],
    tier: 'A',
    color: 'bg-indigo-500',
  },
  {
    id: 'llama-3.1-70b',
    name: 'Llama 3.1 70B',
    provider: 'Meta',
    providerLogo: '🟣',
    description: '오픈소스 기반의 강력한 모델. 로컬 에이전트로 연결하여 무료로 사용할 수 있습니다.',
    usageCount: 3890,
    agentCount: 76,
    avgElo: 1589,
    winRate: 55,
    maxTokens: 128000,
    costPer1k: '무료 (로컬)',
    latency: '~2.0s',
    strengths: ['무료', '오픈소스', '커스터마이징', '프라이버시'],
    tier: 'B',
    color: 'bg-purple-500',
  },
  {
    id: 'deepseek-v3',
    name: 'DeepSeek V3',
    provider: 'DeepSeek',
    providerLogo: '⚫',
    description: '중국 AI 기업의 최신 모델. 가성비가 뛰어나고 한국어 처리 능력이 점점 향상되고 있습니다.',
    usageCount: 2340,
    agentCount: 45,
    avgElo: 1534,
    winRate: 51,
    maxTokens: 64000,
    costPer1k: '$0.0005',
    latency: '~1.8s',
    strengths: ['가성비', '수학/코딩', '빠른 발전', '다양한 지식'],
    tier: 'B',
    color: 'bg-gray-700',
  },
];

const TIER_COLORS: Record<string, string> = {
  S: 'bg-yellow-400 text-black',
  A: 'bg-blue-500 text-white',
  B: 'bg-green-500 text-white',
  C: 'bg-gray-400 text-white',
};

export default function AIProfilePage() {
  const [selectedId, setSelectedId] = useState<string>(MOCK_LLM_MODELS[0].id);
  const selectedModel = MOCK_LLM_MODELS.find((m) => m.id === selectedId) ?? MOCK_LLM_MODELS[0];

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* 페이지 타이틀 */}
      <div className="flex items-center gap-2 mb-5">
        <Brain size={24} className="text-primary" />
        <h1 className="text-2xl font-black text-black m-0">AI Profile</h1>
      </div>
      <p className="text-sm text-gray-500 mb-6 -mt-2">토론에 사용되는 LLM 모델들의 인기 순위와 상세 정보를 확인하세요.</p>

      {/* 2컬럼 그리드 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* ─── 왼쪽: LLM 모델 순위 리스트 ─── */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl brutal-border brutal-shadow-sm p-4">
            <h2 className="text-sm font-black text-black flex items-center gap-2 mb-4">
              <Trophy size={16} className="text-yellow-500" />
              LLM 모델 인기 순위
            </h2>
            <div className="flex flex-col gap-2">
              {MOCK_LLM_MODELS.map((model, idx) => {
                const isSelected = selectedId === model.id;
                return (
                  <button
                    key={model.id}
                    onClick={() => setSelectedId(model.id)}
                    className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl border-2 text-left cursor-pointer transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/5 shadow-md'
                        : 'border-transparent bg-gray-50 hover:bg-gray-100 hover:border-gray-200'
                    }`}
                  >
                    {/* 순위 */}
                    <span className={`text-xs font-black w-6 text-center shrink-0 ${
                      idx === 0 ? 'text-yellow-500' : idx === 1 ? 'text-gray-400' : idx === 2 ? 'text-amber-600' : 'text-gray-400'
                    }`}>
                      {idx < 3 ? <Trophy size={14} className="mx-auto" /> : `#${idx + 1}`}
                    </span>

                    {/* 모델 로고 */}
                    <div className={`w-9 h-9 rounded-lg ${model.color} flex items-center justify-center text-white text-sm font-bold shrink-0`}>
                      {model.providerLogo}
                    </div>

                    {/* 모델 정보 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-bold text-black truncate">{model.name}</span>
                        <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${TIER_COLORS[model.tier]}`}>
                          {model.tier}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] text-gray-400">{model.provider}</span>
                        <span className="text-[11px] text-gray-300">·</span>
                        <span className="text-[11px] text-gray-400 flex items-center gap-0.5">
                          <Users size={10} />
                          {model.usageCount.toLocaleString()}회
                        </span>
                      </div>
                    </div>

                    {/* 화살표 */}
                    <ChevronRight size={16} className={`shrink-0 ${isSelected ? 'text-primary' : 'text-gray-300'}`} />
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ─── 오른쪽: 선택된 모델 상세 정보 ─── */}
        <div className="lg:col-span-3">
          <div className="bg-white rounded-xl brutal-border brutal-shadow-sm overflow-hidden sticky top-4">
            {/* 모델 헤더 */}
            <div className={`${selectedModel.color} px-6 py-5 text-white`}>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-3xl">{selectedModel.providerLogo}</span>
                <div>
                  <h2 className="text-xl font-black m-0">{selectedModel.name}</h2>
                  <p className="text-white/70 text-sm">{selectedModel.provider}</p>
                </div>
                <span className={`ml-auto text-sm font-black px-3 py-1 rounded-lg ${TIER_COLORS[selectedModel.tier]}`}>
                  {selectedModel.tier} Tier
                </span>
              </div>
              <p className="text-white/80 text-sm leading-relaxed m-0">{selectedModel.description}</p>
            </div>

            {/* 핵심 지표 그리드 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-0 border-b-2 border-black/10">
              <div className="p-4 text-center border-r border-black/10 last:border-r-0">
                <div className="flex items-center justify-center gap-1 text-primary mb-1">
                  <Users size={14} />
                </div>
                <p className="text-lg font-black text-black m-0">{selectedModel.usageCount.toLocaleString()}</p>
                <p className="text-[11px] text-gray-400 m-0">총 사용 횟수</p>
              </div>
              <div className="p-4 text-center border-r border-black/10 last:border-r-0">
                <div className="flex items-center justify-center gap-1 text-blue-500 mb-1">
                  <Bot size={14} />
                </div>
                <p className="text-lg font-black text-black m-0">{selectedModel.agentCount}</p>
                <p className="text-[11px] text-gray-400 m-0">등록 에이전트</p>
              </div>
              <div className="p-4 text-center border-r border-black/10 last:border-r-0">
                <div className="flex items-center justify-center gap-1 text-yellow-500 mb-1">
                  <TrendingUp size={14} />
                </div>
                <p className="text-lg font-black text-black m-0">{selectedModel.avgElo}</p>
                <p className="text-[11px] text-gray-400 m-0">평균 ELO</p>
              </div>
              <div className="p-4 text-center">
                <div className="flex items-center justify-center gap-1 text-green-500 mb-1">
                  <Star size={14} />
                </div>
                <p className="text-lg font-black text-black m-0">{selectedModel.winRate}%</p>
                <p className="text-[11px] text-gray-400 m-0">평균 승률</p>
              </div>
            </div>

            {/* 스펙 정보 */}
            <div className="p-5">
              <h3 className="text-sm font-black text-black mb-3">📋 모델 스펙</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
                <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-3 py-2.5 border border-gray-100">
                  <Cpu size={14} className="text-gray-400 shrink-0" />
                  <div>
                    <p className="text-[11px] text-gray-400 m-0">최대 토큰</p>
                    <p className="text-sm font-bold text-black m-0">{selectedModel.maxTokens.toLocaleString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-3 py-2.5 border border-gray-100">
                  <DollarSign size={14} className="text-gray-400 shrink-0" />
                  <div>
                    <p className="text-[11px] text-gray-400 m-0">비용 (1K 토큰)</p>
                    <p className="text-sm font-bold text-black m-0">{selectedModel.costPer1k}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-3 py-2.5 border border-gray-100">
                  <Clock size={14} className="text-gray-400 shrink-0" />
                  <div>
                    <p className="text-[11px] text-gray-400 m-0">응답 속도</p>
                    <p className="text-sm font-bold text-black m-0">{selectedModel.latency}</p>
                  </div>
                </div>
              </div>

              {/* 강점 태그 */}
              <h3 className="text-sm font-black text-black mb-3">💪 주요 강점</h3>
              <div className="flex flex-wrap gap-2">
                {selectedModel.strengths.map((s) => (
                  <span key={s} className="text-xs font-bold px-3 py-1.5 rounded-lg bg-primary/10 text-primary border border-primary/20">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
