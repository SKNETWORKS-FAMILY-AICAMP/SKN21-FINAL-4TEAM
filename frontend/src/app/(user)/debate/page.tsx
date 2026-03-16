'use client';

import { useEffect, useState } from 'react';
import { Swords, Plus, X, ChevronDown, Shuffle, Bot, MessageSquare, Users, Clock, Trophy } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';
import { TopicCard } from '@/components/debate/TopicCard';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { ScrollToTop } from '@/components/ui/ScrollToTop';
import { TierBadge } from '@/components/debate/TierBadge';
import { HighlightBanner } from '@/components/debate/HighlightBanner';
import { api } from '@/lib/api';
import { DebateTopic } from '@/types/debate';

const MOCK_TOPICS: DebateTopic[] = [
  {
    id: 'mock-1',
    title: '원자력 발전은 친환경 에너지인가?',
    description: '탄소 배출 저감과 핵폐기물 처리 문제 사이의 논쟁',
    mode: 'tournament',
    status: 'open',
    max_turns: 10,
    turn_token_limit: 1000,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: true,
    queue_count: 2,
    match_count: 45,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  },
  {
    id: 'mock-2',
    title: '기본소득제 도입, 시기상조인가?',
    description: '자동화 시대의 사회안전망 구축과 재정 부담',
    mode: 'tournament',
    status: 'open',
    max_turns: 12,
    turn_token_limit: 1200,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: false,
    queue_count: 1,
    match_count: 32,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  },
  {
    id: 'mock-3',
    title: 'AI 저작권, 인공지능에게도 권리가 있는가?',
    description: '생성형 AI의 결과물에 대한 법적 보호와 작가 권리',
    mode: 'tournament',
    status: 'open',
    max_turns: 8,
    turn_token_limit: 1500,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: true,
    queue_count: 3,
    match_count: 128,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  },
  {
    id: 'mock-4',
    title: '채식주의, 기후 위기의 해법인가?',
    description: '축산업의 환경 영향과 식문화의 변화',
    mode: 'tournament',
    status: 'open',
    max_turns: 10,
    turn_token_limit: 1000,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: false,
    queue_count: 0,
    match_count: 15,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  },
  {
    id: 'mock-5',
    title: '우주 탐사 예산, 지구 문제 해결에 써야 하는가?',
    description: '테라포밍의 꿈과 당면한 환경 문제 사이의 우선순위',
    mode: 'tournament',
    status: 'open',
    max_turns: 15,
    turn_token_limit: 2000,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: true,
    queue_count: 2,
    match_count: 67,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  },
  {
    id: 'mock-6',
    title: '재택근무 vs 사무실 출근, 무엇이 더 효율적인가?',
    description: '업무 생산성과 조직 문화, 소속감의 상관관계',
    mode: 'tournament',
    status: 'open',
    max_turns: 6,
    turn_token_limit: 800,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: false,
    queue_count: 4,
    match_count: 89,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  },
  {
    id: 'mock-7',
    title: 'SNS 규제, 표현의 자유 침해인가?',
    description: '가짜 뉴스와 혐오 표현 방지를 위한 플랫폼의 책임',
    mode: 'tournament',
    status: 'open',
    max_turns: 10,
    turn_token_limit: 1000,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: true,
    queue_count: 1,
    match_count: 42,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  },
  {
    id: 'mock-8',
    title: '디지털 자산(NFT), 투기인가 혁명인가?',
    description: '블록체인 기술의 활용 가능성과 시장의 거품 논란',
    mode: 'tournament',
    status: 'open',
    max_turns: 10,
    turn_token_limit: 1200,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: true,
    tools_enabled: false,
    queue_count: 0,
    match_count: 112,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  }
];

type StatusFilter = 'all' | 'open' | 'in_progress' | 'closed' | 'scheduled';
type SortOption = 'recent' | 'queue' | 'matches';

const FILTER_OPTIONS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'scheduled', label: '예정' },
  { key: 'open', label: '참가 가능' },
  { key: 'in_progress', label: '진행 중' },
  { key: 'closed', label: '종료' },
];

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'recent', label: '최신순' },
  { value: 'queue', label: '대기 많은 순' },
  { value: 'matches', label: '매치 많은 순' },
];

const MODE_OPTIONS = [
  { value: 'debate', label: '찬반 토론' },
  { value: 'persuasion', label: '설득' },
  { value: 'cross_exam', label: '교차 심문' },
];

const defaultForm = {
  title: '',
  description: '',
  mode: 'debate',
  max_turns: 6,
  turn_token_limit: 1500,
  tools_enabled: true,
  scheduled_start_at: null as string | null,
  scheduled_end_at: null as string | null,
  password: '' as string,
};

const PAGE_SIZE = 4;

const MORE_MOCK_TOPICS: DebateTopic[] = [
  {
    id: 'mock-9',
    title: '동물실험, 인류의 발전을 위해 정당화될 수 있는가?',
    description: '생명 윤리와 의학적 진보 사이의 딜레마',
    mode: 'debate',
    status: 'open',
    max_turns: 10,
    turn_token_limit: 1000,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: false,
    tools_enabled: true,
    queue_count: 5,
    match_count: 24,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'user-1',
    creator_nickname: '윤리전문가'
  },
  {
    id: 'mock-10',
    title: '메타버스에서의 범죄, 실질적 처벌이 가능한가?',
    description: '가상 세계의 법적 정의와 관할권 문제',
    mode: 'cross_exam',
    status: 'open',
    max_turns: 12,
    turn_token_limit: 1500,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: false,
    tools_enabled: true,
    queue_count: 2,
    match_count: 18,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'user-2',
    creator_nickname: '사이버리안'
  },
  {
    id: 'mock-11',
    title: '유전자 가위 기술, 맞춤형 아기 탄생을 허용해야 하는가?',
    description: '질병 예방과 유전적 불평등, 그리고 진화의 방향',
    mode: 'persuasion',
    status: 'open',
    max_turns: 15,
    turn_token_limit: 2000,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: false,
    tools_enabled: false,
    queue_count: 8,
    match_count: 56,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'user-3',
    creator_nickname: '바이오해커'
  },
  {
    id: 'mock-12',
    title: '인공지능 판사 도입, 공정한 판결을 보장하는가?',
    description: '알고리즘의 편향성과 인간적 판단의 가치',
    mode: 'debate',
    status: 'open',
    max_turns: 8,
    turn_token_limit: 1200,
    scheduled_start_at: null,
    scheduled_end_at: null,
    is_admin_topic: false,
    tools_enabled: true,
    queue_count: 3,
    match_count: 37,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by: 'admin',
    creator_nickname: '시스템'
  }
];

const ALL_MOCK_TOPICS = [...MOCK_TOPICS, ...MORE_MOCK_TOPICS];

type Stats = {
  live: number;
  todayParticipants: number;
  scheduled: number;
};

export default function DebateTopicsPage() {
  const router = useRouter();
  const {
    topics,
    topicsTotal,
    topicsLoading,
    fetchTopics,
    fetchFeatured,
    createTopic,
    updateTopic,
    deleteTopic,
    randomMatch,
  } = useDebateStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const { user } = useUserStore();

  const [filter, setFilter] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<SortOption>('recent');
  const [page, setPage] = useState(1);
  const [visibleCount, setVisibleCount] = useState(8);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // 주제 생성 모달
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(defaultForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 랜덤 매칭 모달
  const [showRandomModal, setShowRandomModal] = useState(false);
  const [randomAgentId, setRandomAgentId] = useState('');
  const [randomMatching, setRandomMatching] = useState(false);
  const [randomError, setRandomError] = useState<string | null>(null);

  // 주제 수정 모달
  const [editTopic, setEditTopic] = useState<(typeof topics)[number] | null>(null);
  const [editForm, setEditForm] = useState(defaultForm);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editShowAdvanced, setEditShowAdvanced] = useState(false);

  // 초기 로드
  useEffect(() => {
    fetchMyAgents();
    fetchFeatured();
  }, [fetchMyAgents, fetchFeatured]);

  // Infinite scroll trigger on downward wheel/scroll intent
  useEffect(() => {
    let lastScrollTime = 0;
    const cooldown = 1500; // 1.5s cooldown between batches to maintain rhythm

    const handleWheel = (e: WheelEvent) => {
      // Detect downward scroll intent
      if (e.deltaY > 0 && visibleCount < ALL_MOCK_TOPICS.length && !isRefreshing) {
        const now = Date.now();
        if (now - lastScrollTime > cooldown) {
          lastScrollTime = now;
          setIsRefreshing(true);
          setTimeout(() => {
            setVisibleCount(prev => Math.min(prev + 8, ALL_MOCK_TOPICS.length));
            setIsRefreshing(false);
          }, 800);
        }
      }
    };

    // Also handle touch for mobile if needed, but wheel is primary for mouse
    window.addEventListener('wheel', handleWheel, { passive: true });
    return () => window.removeEventListener('wheel', handleWheel);
  }, [visibleCount, isRefreshing]);

  // 필터 변경 시 페이지 초기화
  const handleFilterChange = (f: StatusFilter) => {
    setFilter(f);
    setVisibleCount(8);
  };

  const handleSortChange = (s: SortOption) => {
    setSort(s);
    setVisibleCount(8);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      await createTopic({
        title: form.title.trim(),
        description: form.description.trim() || null,
        mode: form.mode,
        max_turns: form.max_turns,
        turn_token_limit: form.turn_token_limit,
        tools_enabled: form.tools_enabled,
        scheduled_start_at: form.scheduled_start_at || null,
        scheduled_end_at: form.scheduled_end_at || null,
        password: form.password || null,
      });
      setShowModal(false);
      setForm(defaultForm);
      setShowAdvanced(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '생성 실패');
    } finally {
      setSubmitting(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setError(null);
    setForm(defaultForm);
    setShowAdvanced(false);
  };

  const openEditModal = (topic: (typeof topics)[number]) => {
    setEditTopic(topic);
    setEditForm({
      title: topic.title,
      description: topic.description ?? '',
      mode: topic.mode,
      max_turns: topic.max_turns,
      turn_token_limit: topic.turn_token_limit,
      tools_enabled: topic.tools_enabled,
      scheduled_start_at: topic.scheduled_start_at ?? null,
      scheduled_end_at: topic.scheduled_end_at ?? null,
      password: '',
    });
    setEditError(null);
    setEditShowAdvanced(false);
  };

  const closeEditModal = () => {
    setEditTopic(null);
    setEditError(null);
    setEditShowAdvanced(false);
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTopic || !editForm.title.trim()) return;
    setEditError(null);
    setEditSubmitting(true);
    try {
      await updateTopic(editTopic.id, {
        title: editForm.title.trim(),
        description: editForm.description.trim() || null,
        mode: editForm.mode,
        max_turns: editForm.max_turns,
        turn_token_limit: editForm.turn_token_limit,
        tools_enabled: editForm.tools_enabled,
        scheduled_start_at: editForm.scheduled_start_at || null,
        scheduled_end_at: editForm.scheduled_end_at || null,
      });
      closeEditModal();
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : '수정 실패');
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDelete = async (topicId: string) => {
    if (!confirm('정말 이 주제를 삭제하시겠습니까?')) return;
    try {
      await deleteTopic(topicId);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : '삭제 실패');
    }
  };

  const handleRandomMatch = async () => {
    if (!randomAgentId) return;
    setRandomError(null);
    setRandomMatching(true);
    try {
      const result = await randomMatch(randomAgentId);
      setShowRandomModal(false);
      router.push(`/debate/topics/${result.topic_id}`);
    } catch (err: unknown) {
      setRandomError(err instanceof Error ? err.message : '매칭 실패');
    } finally {
      setRandomMatching(false);
    }
  };

  const currentUserId = user?.id ?? null;

  return (
    <div className="max-w-[1400px] mx-auto py-6 px-4 xl:px-8">
      {/* 상단 액션 버튼 */}
      <div className="flex items-center justify-between mb-8 mt-4">
        <h2 className="text-2xl font-black text-text flex items-center gap-3 m-0">
          <Swords size={28} className="text-primary" />
          AI 토론
        </h2>
        <div className="flex items-center gap-3">
          {agents.length > 0 && (
            <button
              onClick={() => setShowRandomModal(true)}
              className="px-6 py-2.5 bg-orange-500 text-white text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer flex items-center gap-2"
            >
              <Shuffle size={18} />
              랜덤 매칭
            </button>
          )}
          <button
            onClick={() => setShowModal(true)}
            className="px-6 py-2.5 bg-white text-black text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer flex items-center gap-2"
          >
            <Plus size={18} />
            주제 제안
          </button>
          <Link
            href="/debate/agents"
            className="px-6 py-2.5 bg-primary text-white text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all no-underline flex items-center gap-2"
          >
            <Plus size={18} />
            내 에이전트
          </Link>
        </div>
      </div>

      <div className="mt-6">
        <div id="topic-list">
          <div className="flex items-center justify-between gap-2 mb-4 flex-wrap">
            <div className="flex gap-1.5 flex-wrap">
              {FILTER_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => handleFilterChange(opt.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border-none cursor-pointer transition-colors ${
                    filter === opt.key
                      ? 'bg-primary text-white'
                      : 'bg-transparent text-text-muted hover:text-text'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <select
              value={sort}
              onChange={(e) => handleSortChange(e.target.value as SortOption)}
              className="bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none focus:border-primary shrink-0"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {topicsLoading ? (
              Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
            ) : (
              ALL_MOCK_TOPICS.slice(0, visibleCount).map((topic, index) => {
                // 현재 배치(마지막 8개 또는 초기 8개)에만 애니메이션 적용 효과를 주기 위해
                // index가 visibleCount - 8보다 큰 경우에만 딜레이 적용 (초기는 0~7)
                const isNewBatch = index >= visibleCount - 8;
                const delayIndex = isNewBatch ? (index % 8) : 0;
                
                return (
                  <div 
                    key={topic.id} 
                    className={`animate-in fill-mode-forwards ${isNewBatch ? '' : 'opacity-100 transform-none'}`}
                    style={{ 
                      animationDelay: isNewBatch ? `${delayIndex * 150}ms` : '0ms',
                      animationDuration: isNewBatch ? '0.8s' : '0s'
                    }}
                  >
                    <TopicCard
                      topic={topic}
                      currentUserId={currentUserId}
                      onEdit={openEditModal}
                      onDelete={handleDelete}
                    />
                  </div>
                );
              })
            )}
          </div>

          {/* Infinite Scroll Refreshing State */}
          {isRefreshing && (
            <div className="flex justify-center items-center py-8">
              <div className="flex gap-2 items-center text-primary font-black animate-pulse">
                <Clock size={18} />
                <span>새로운 주제를 불러오는 중...</span>
              </div>
            </div>
          )}

          {/* Numeric Indicators (Carousel style) */}
          <div className="flex justify-center gap-3 mt-12 mb-8">
            {Array.from({ length: Math.ceil((ALL_MOCK_TOPICS.length - 8) / 8) + 1 }).map((_, idx) => {
              const isActive = (visibleCount >= 8 + idx * 8);
              return (
                <button
                  key={idx}
                  disabled
                  className={`w-10 h-10 rounded-xl border-2 border-black font-black text-sm flex items-center justify-center transition-all ${
                    isActive 
                      ? 'bg-primary text-white brutal-shadow-sm' 
                      : 'bg-white text-gray-300'
                  }`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 주제 제안 모달 */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div>
                <h2 className="font-bold text-text m-0">토론 주제 제안</h2>
                <p className="text-[11px] text-text-muted mt-0.5 m-0">
                  누구나 토론 주제를 제안할 수 있어요
                </p>
              </div>
              <button onClick={closeModal} className="text-text-muted hover:text-text transition-colors">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-5 space-y-4">
              <div>
                <label className="block text-xs text-text-muted mb-1">
                  주제 제목 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  autoFocus
                  maxLength={200}
                  placeholder="예: 원자력 발전은 친환경 에너지인가?"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
                <textarea
                  rows={2}
                  maxLength={500}
                  placeholder="주제에 대한 간단한 배경 설명"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary resize-none"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:outline-none focus:border-primary"
                >
                  {MODE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">방 비밀번호 (선택)</label>
                <input
                  type="password"
                  maxLength={50}
                  placeholder="비어 있으면 공개방"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
                />
              </div>

              {/* 고급 설정 토글 */}
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
              >
                <ChevronDown
                  size={14}
                  className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
                />
                고급 설정
              </button>

              {showAdvanced && (
                <div className="border border-border rounded-lg p-3 bg-bg space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-text-muted mb-1">최대 턴수 (2–20)</label>
                      <input
                        type="number"
                        min={2}
                        max={20}
                        value={form.max_turns}
                        onChange={(e) => setForm({ ...form, max_turns: Number(e.target.value) })}
                        className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">턴 토큰 한도</label>
                      <input
                        type="number"
                        min={100}
                        max={2000}
                        step={100}
                        value={form.turn_token_limit}
                        onChange={(e) =>
                          setForm({ ...form, turn_token_limit: Number(e.target.value) })
                        }
                        className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                      />
                    </div>
                  </div>
                  {/* 툴 사용 허용 토글 */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-text">툴 사용 허용</p>
                      <p className="text-[10px] text-text-muted">계산기, 주장 추적 등 보조 툴</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, tools_enabled: !f.tools_enabled }))}
                      className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors ${
                        form.tools_enabled ? 'bg-primary' : 'bg-gray-600'
                      }`}
                    >
                      <span
                        className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
                          form.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                  {/* 스케줄 */}
                  <div>
                    <label className="text-xs text-text-muted">활성화 시작 시간</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_start_at ?? ''}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, scheduled_start_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">비활성화 종료 시간</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_end_at ?? ''}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, scheduled_end_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                </div>
              )}

              {error && <p className="text-xs text-red-400">{error}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={submitting || !form.title.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {submitting ? '제안 중...' : '제안하기'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 랜덤 매칭 모달 */}
      {showRandomModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-sm shadow-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-text flex items-center gap-2 m-0">
                <Shuffle size={16} className="text-orange-400" />
                랜덤 매칭
              </h2>
              <button
                onClick={() => {
                  setShowRandomModal(false);
                  setRandomError(null);
                }}
                className="text-text-muted hover:text-text transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <p className="text-xs text-text-muted mb-4">
              참가할 에이전트를 선택하면 열린 토픽에 자동으로 매칭됩니다.
            </p>
            <select
              value={randomAgentId}
              onChange={(e) => setRandomAgentId(e.target.value)}
              className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:outline-none focus:border-primary mb-3"
            >
              <option value="">에이전트 선택...</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} (ELO {a.elo_rating})
                </option>
              ))}
            </select>
            {randomError && <p className="text-xs text-red-400 mb-3">{randomError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowRandomModal(false);
                  setRandomError(null);
                }}
                className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleRandomMatch}
                disabled={!randomAgentId || randomMatching}
                className="flex-1 py-2.5 rounded-xl bg-orange-500 text-white text-sm font-semibold hover:bg-orange-500/90 disabled:opacity-50 transition-colors"
              >
                {randomMatching ? '매칭 중...' : '매칭 시작'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ScrollToTop />

      {/* 주제 수정 모달 */}
      {editTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div>
                <h2 className="font-bold text-text m-0">주제 수정</h2>
                <p className="text-[11px] text-text-muted mt-0.5 m-0">내 토론 주제를 수정합니다</p>
              </div>
              <button
                onClick={closeEditModal}
                className="text-text-muted hover:text-text transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleEdit} className="p-5 space-y-4">
              <div>
                <label className="block text-xs text-text-muted mb-1">
                  주제 제목 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  autoFocus
                  maxLength={200}
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
                <textarea
                  rows={2}
                  maxLength={500}
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary resize-none"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={editForm.mode}
                  onChange={(e) => setEditForm({ ...editForm, mode: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:outline-none focus:border-primary"
                >
                  {MODE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => setEditShowAdvanced(!editShowAdvanced)}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
              >
                <ChevronDown
                  size={14}
                  className={`transition-transform ${editShowAdvanced ? 'rotate-180' : ''}`}
                />
                고급 설정
              </button>

              {editShowAdvanced && (
                <div className="border border-border rounded-lg p-3 bg-bg space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-text-muted mb-1">최대 턴수 (2–20)</label>
                      <input
                        type="number"
                        min={2}
                        max={20}
                        value={editForm.max_turns}
                        onChange={(e) =>
                          setEditForm({ ...editForm, max_turns: Number(e.target.value) })
                        }
                        className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">턴 토큰 한도</label>
                      <input
                        type="number"
                        min={100}
                        max={2000}
                        step={100}
                        value={editForm.turn_token_limit}
                        onChange={(e) =>
                          setEditForm({ ...editForm, turn_token_limit: Number(e.target.value) })
                        }
                        className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-text">툴 사용 허용</p>
                      <p className="text-[10px] text-text-muted">계산기, 주장 추적 등 보조 툴</p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setEditForm((f) => ({ ...f, tools_enabled: !f.tools_enabled }))
                      }
                      className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors ${
                        editForm.tools_enabled ? 'bg-primary' : 'bg-gray-600'
                      }`}
                    >
                      <span
                        className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
                          editForm.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">활성화 시작 시간</label>
                    <input
                      type="datetime-local"
                      value={editForm.scheduled_start_at ?? ''}
                      onChange={(e) =>
                        setEditForm((f) => ({ ...f, scheduled_start_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">비활성화 종료 시간</label>
                    <input
                      type="datetime-local"
                      value={editForm.scheduled_end_at ?? ''}
                      onChange={(e) =>
                        setEditForm((f) => ({ ...f, scheduled_end_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                </div>
              )}

              {editError && <p className="text-xs text-red-400">{editError}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={closeEditModal}
                  className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={editSubmitting || !editForm.title.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {editSubmitting ? '수정 중...' : '저장'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
