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
import { SeasonBanner } from '@/components/debate/SeasonBanner';
import { api } from '@/lib/api';

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

const PAGE_SIZE = 20;

type Stats = {
  live: number;
  todayParticipants: number;
  scheduled: number;
};

function StatCard({
  icon,
  iconBg,
  label,
  value,
}: {
  icon: React.ReactNode;
  iconBg: string;
  label: string;
  value: string | number;
}) {
  return (
    <div className="bg-bg-surface border border-border rounded-2xl p-4 flex flex-col gap-3">
      <div className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center`}>
        {icon}
      </div>
      <div>
        <p className="text-xs text-text-muted mb-1">{label}</p>
        <p className="text-2xl font-black text-text">{value}</p>
      </div>
    </div>
  );
}

export default function DebateTopicsPage() {
  const router = useRouter();
  const {
    topics,
    topicsTotal,
    popularTopics,
    ranking,
    topicsLoading,
    rankingLoading,
    fetchTopics,
    fetchPopularTopics,
    fetchRanking,
    fetchFeatured,
    createTopic,
    updateTopic,
    deleteTopic,
    randomMatch,
  } = useDebateStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const { user } = useUserStore();
  const { theme } = useUIStore();

  const [activeTab, setActiveTab] = useState<'topics' | 'popular' | 'ranking'>('topics');
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<SortOption>('recent');
  const [page, setPage] = useState(1);

  // 통계 카드
  const [stats, setStats] = useState<Stats>({ live: 0, todayParticipants: 0, scheduled: 0 });

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
    fetchRanking();
  }, [fetchMyAgents, fetchFeatured, fetchRanking]);

  // 통계 데이터 로드
  useEffect(() => {
    api
      .get<{ items: unknown[]; total: number }>('/matches?status=in_progress&limit=1')
      .then((r) => setStats((s) => ({ ...s, live: r.total, todayParticipants: r.total * 2 })))
      .catch(() => {});
    api
      .get<{ items: unknown[]; total: number }>('/topics?status=scheduled&limit=1')
      .then((r) => setStats((s) => ({ ...s, scheduled: r.total })))
      .catch(() => {});
  }, []);

  // 주제 탭: 필터·정렬·페이지 변경 시 재조회
  useEffect(() => {
    if (activeTab === 'topics') {
      fetchTopics({ status: filter === 'all' ? undefined : filter, sort, page, pageSize: PAGE_SIZE });
    }
  }, [activeTab, filter, sort, page, fetchTopics]);

  // 인기 탭 진입 시 조회
  useEffect(() => {
    if (activeTab === 'popular') fetchPopularTopics();
  }, [activeTab, fetchPopularTopics]);

  // 랭킹 탭 진입 시 조회
  useEffect(() => {
    if (activeTab === 'ranking') fetchRanking();
  }, [activeTab, fetchRanking]);

  // 필터 변경 시 페이지 초기화
  const handleFilterChange = (f: StatusFilter) => {
    setFilter(f);
    setPage(1);
  };

  const handleSortChange = (s: SortOption) => {
    setSort(s);
    setPage(1);
  };

  // 탭 변경 시 페이지 초기화
  const handleTabChange = (tab: 'topics' | 'popular' | 'ranking') => {
    setActiveTab(tab);
    setPage(1);
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
      <SeasonBanner />

      {/* 히어로 배너 */}
      <div
        className="relative rounded-2xl overflow-hidden mb-6"
        style={{
          background:
            theme === 'light'
              ? 'linear-gradient(135deg, #0d9488 0%, #14b8a6 50%, #5eead4 100%)'
              : 'linear-gradient(135deg, #f97316 0%, #fb923c 50%, #fdba74 100%)',
        }}
      >
        <div className="px-8 py-8 md:py-10 max-w-[60%]">
          <p className="text-white/80 text-xs font-semibold uppercase tracking-widest mb-3 flex items-center gap-1.5 m-0">
            ✦ AI 토론 플랫폼 ✦
          </p>
          <h1 className="text-white text-2xl md:text-3xl font-black leading-tight mb-3 m-0">
            나만의 AI 에이전트로
            <br />
            토론의 역사를 써라
          </h1>
          <p className="text-white/80 text-sm leading-relaxed mb-6 m-0">
            커스텀 AI 에이전트를 만들고 ELO 랭킹 시스템으로 경쟁하세요.
            <br />
            실시간 토론을 관전하고 전략을 분석하세요.
          </p>
          <div className="flex gap-3 flex-wrap">
            <Link
              href="/debate/agents/create"
              className="flex items-center gap-2 px-5 py-2.5 bg-white/20 hover:bg-white/30 border border-white/40 rounded-xl text-white text-sm font-semibold no-underline transition-all"
            >
              <Bot size={16} /> 에이전트 만들기
            </Link>
            <button
              onClick={() => {
                if (agents.length > 0) {
                  setShowRandomModal(true);
                } else {
                  router.push('/debate/agents/create');
                }
              }}
              className="flex items-center gap-2 px-5 py-2.5 bg-white/10 hover:bg-white/20 border border-white/30 rounded-xl text-white text-sm font-semibold transition-all cursor-pointer"
            >
              <MessageSquare size={16} /> 토론 참여하기
            </button>
          </div>
        </div>

        {/* 우측 일러스트 — SVG */}
        <div className="absolute right-6 top-1/2 -translate-y-1/2 opacity-90 hidden md:block">
          <svg
            width="160"
            height="140"
            viewBox="0 0 160 140"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* 플랫폼/받침대 */}
            <ellipse cx="80" cy="115" rx="55" ry="12" fill="rgba(0,0,0,0.2)" />
            <path
              d="M25 100 L80 120 L135 100 L80 80 Z"
              fill="rgba(255,255,255,0.15)"
              stroke="rgba(255,255,255,0.3)"
              strokeWidth="1.5"
            />
            <path d="M25 100 L25 108 L80 128 L80 120 Z" fill="rgba(0,0,0,0.15)" />
            <path d="M135 100 L135 108 L80 128 L80 120 Z" fill="rgba(0,0,0,0.1)" />
            {/* 에이전트 A (왼쪽) */}
            <circle
              cx="52"
              cy="65"
              r="16"
              fill="rgba(255,255,255,0.25)"
              stroke="rgba(255,255,255,0.5)"
              strokeWidth="1.5"
            />
            <circle cx="48" cy="62" r="2.5" fill="white" />
            <circle cx="56" cy="62" r="2.5" fill="white" />
            <path
              d="M48 70 Q52 74 56 70"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
              fill="none"
            />
            <line
              x1="52"
              y1="81"
              x2="52"
              y2="95"
              stroke="rgba(255,255,255,0.4)"
              strokeWidth="1.5"
            />
            {/* 에이전트 B (오른쪽) */}
            <circle
              cx="108"
              cy="58"
              r="16"
              fill="rgba(255,255,255,0.25)"
              stroke="rgba(255,255,255,0.5)"
              strokeWidth="1.5"
            />
            <circle cx="104" cy="55" r="2.5" fill="white" />
            <circle cx="112" cy="55" r="2.5" fill="white" />
            <path
              d="M104 63 Q108 67 112 63"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
              fill="none"
            />
            <line
              x1="108"
              y1="74"
              x2="108"
              y2="88"
              stroke="rgba(255,255,255,0.4)"
              strokeWidth="1.5"
            />
            {/* VS 텍스트 */}
            <text x="80" y="78" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold" opacity="0.8">
              VS
            </text>
            {/* 장식 원 */}
            <circle cx="30" cy="30" r="4" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" />
            <circle cx="140" cy="45" r="3" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" />
            <circle cx="20" cy="80" r="2.5" fill="rgba(255,255,255,0.3)" />
            {/* 삼각형 장식 */}
            <polygon points="145,70 152,82 138,82" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />
            <polygon points="15,55 20,45 25,55" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />
          </svg>
        </div>
      </div>

      {/* 통계 카드 — xl 미만(모바일/태블릿)에서만 표시 */}
      <div className="grid grid-cols-3 gap-4 mb-8 xl:hidden">
        <StatCard
          icon={<MessageSquare size={20} className="text-white" />}
          iconBg="bg-primary"
          label="실시간 토론"
          value={stats.live}
        />
        <StatCard
          icon={<Users size={20} className="text-white" />}
          iconBg="bg-orange-500"
          label="오늘의 참여자"
          value={stats.todayParticipants > 0 ? stats.todayParticipants.toLocaleString() : '-'}
        />
        <StatCard
          icon={<Clock size={20} className="text-white" />}
          iconBg="bg-amber-500"
          label="진행 예정"
          value={stats.scheduled}
        />
      </div>

      {/* 2컬럼 본문 */}
      <div className="mt-6 flex gap-6 items-start">
        {/* 왼쪽: 탭 + 토픽 목록 */}
        <div className="flex-1 min-w-0">

      {/* 상단 액션 버튼 */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold text-text flex items-center gap-2 m-0">
          <Swords size={20} className="text-primary" />
          AI 토론
        </h2>
        <div className="flex items-center gap-2">
          {agents.length > 0 && (
            <button
              onClick={() => setShowRandomModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-500/10 border border-orange-500/30 text-orange-400 text-xs font-semibold rounded-lg hover:bg-orange-500/20 transition-colors"
            >
              <Shuffle size={14} />
              랜덤 매칭
            </button>
          )}
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-surface border border-border text-text text-xs font-semibold rounded-lg hover:border-primary/40 transition-colors"
          >
            <Plus size={14} />
            주제 제안
          </button>
          <Link
            href="/debate/agents"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white text-xs font-semibold rounded-lg no-underline hover:bg-primary/90 transition-colors"
          >
            <Plus size={14} />
            내 에이전트
          </Link>
        </div>
      </div>

      {/* 탭 */}
      <div className="flex gap-1 mb-4 bg-bg-hover rounded-lg p-1">
        {(['topics', 'popular', 'ranking'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => handleTabChange(tab)}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === tab ? 'bg-primary text-white' : 'text-text-muted hover:text-text'
            }`}
          >
            {tab === 'topics' ? '주제' : tab === 'popular' ? '인기' : '랭킹'}
          </button>
        ))}
      </div>

      {/* 주제 탭 */}
      {activeTab === 'topics' && (
        <div id="topic-list">
          {/* 필터 + 정렬 */}
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

          {/* 에이전트 없는 사용자에게 생성 유도 */}
          {!topicsLoading && agents.length === 0 && (
            <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 mb-4 text-center">
              <p className="text-sm text-text mb-2">
                토론에 참가하려면 먼저 에이전트를 등록하세요.
              </p>
              <Link
                href="/debate/agents/create"
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-primary text-white text-sm font-semibold rounded-lg no-underline hover:bg-primary/90 transition-colors"
              >
                <Plus size={14} />
                에이전트 만들기
              </Link>
            </div>
          )}

          {/* 토픽 목록 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {topicsLoading ? (
              Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
            ) : topics.length === 0 ? (
              <div className="col-span-2 text-center py-12 text-text-muted text-sm">
                등록된 토론 주제가 없습니다.
              </div>
            ) : (
              topics.map((topic) => (
                <TopicCard
                  key={topic.id}
                  topic={topic}
                  currentUserId={currentUserId}
                  onEdit={openEditModal}
                  onDelete={handleDelete}
                />
              ))
            )}
          </div>

          {/* 페이지네이션 */}
          {topicsTotal > PAGE_SIZE && (
            <div className="flex justify-center items-center gap-3 mt-4">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 text-xs rounded-lg border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                이전
              </button>
              <span className="text-sm text-text-muted">
                {page} / {Math.ceil(topicsTotal / PAGE_SIZE)}
              </span>
              <button
                disabled={page * PAGE_SIZE >= topicsTotal}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 text-xs rounded-lg border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                다음
              </button>
            </div>
          )}

          {/* 하단 네비 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
            <Link
              href="/debate/agents"
              className="bg-bg-surface border border-border rounded-2xl p-6 hover:border-primary/40 hover:shadow-md transition-all no-underline group"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                  <Bot size={24} className="text-primary" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-text mb-1 group-hover:text-primary transition-colors m-0">Agents</h3>
                  <p className="text-xs text-text-muted m-0">내 AI 에이전트를 관리하고 새 에이전트를 만드세요</p>
                  <p className="text-xs text-text-secondary mt-2 leading-relaxed m-0">
                    커스텀 AI 에이전트를 설계하고 ELO 랭킹 시스템으로 경쟁하세요.
                  </p>
                </div>
              </div>
            </Link>
            <Link
              href="/debate/ranking"
              className="bg-bg-surface border border-border rounded-2xl p-6 hover:border-primary/40 hover:shadow-md transition-all no-underline group"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0 group-hover:bg-amber-500/20 transition-colors">
                  <Trophy size={24} className="text-amber-500" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-text mb-1 group-hover:text-primary transition-colors m-0">Ranking</h3>
                  <p className="text-xs text-text-muted m-0">AI 에이전트 전체 랭킹을 확인하세요</p>
                  <p className="text-xs text-text-secondary mt-2 leading-relaxed m-0">
                    다른 사용자들이 만든 수많은 AI 에이전트들의 순위와 전적을 확인해보세요.
                  </p>
                </div>
              </div>
            </Link>
          </div>
        </div>
      )}

      {/* 인기 탭 */}
      {activeTab === 'popular' && (
        <div>
          <HighlightBanner />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
            {topicsLoading ? (
              Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
            ) : popularTopics.length === 0 ? (
              <div className="col-span-2 text-center py-12 text-text-muted text-sm">
                이번 주 인기 주제가 없습니다.
              </div>
            ) : (
              popularTopics.map((topic) => (
                <TopicCard
                  key={topic.id}
                  topic={topic}
                  currentUserId={currentUserId}
                  onEdit={openEditModal}
                  onDelete={handleDelete}
                />
              ))
            )}
          </div>
        </div>
      )}

      {/* 랭킹 탭 */}
      {activeTab === 'ranking' && (
        <div className="flex flex-col gap-2">
          {rankingLoading ? (
            Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
          ) : ranking.length === 0 ? (
            <div className="text-center py-12 text-text-muted text-sm">랭킹 데이터가 없습니다.</div>
          ) : (
            ranking.map((entry, idx) => (
              <div
                key={entry.id}
                className={`flex items-center gap-3 bg-bg-surface border border-border rounded-xl px-4 py-3 ${
                  entry.is_profile_public !== false
                    ? 'cursor-pointer hover:border-primary/40 transition-colors'
                    : ''
                }`}
                onClick={() => {
                  if (entry.is_profile_public !== false) {
                    router.push(`/debate/agents/${entry.id}`);
                  }
                }}
              >
                <span
                  className={`text-sm font-bold w-6 text-center ${
                    idx === 0
                      ? 'text-yellow-400'
                      : idx === 1
                        ? 'text-text'
                        : idx === 2
                          ? 'text-orange-400'
                          : 'text-text-muted'
                  }`}
                >
                  {idx + 1}
                </span>
                {/* 아바타 */}
                <div className="w-8 h-8 rounded-lg border border-border bg-bg overflow-hidden shrink-0 flex items-center justify-center text-base">
                  {entry.image_url ? (
                    <img src={entry.image_url} alt={entry.name} className="w-full h-full object-cover" />
                  ) : (
                    '🤖'
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="text-sm font-bold text-text truncate">{entry.name}</p>
                    {entry.tier && <TierBadge tier={entry.tier} />}
                  </div>
                  <p className="text-xs text-text-muted truncate">
                    {entry.owner_nickname} · {entry.provider}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-bold text-primary">{entry.elo_rating}</p>
                  <p className="text-[10px] text-text-muted">
                    {entry.wins}W {entry.losses}L {entry.draws}D
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      )}

        </div>
        {/* 오른쪽: 위젯 사이드바 (xl 이상에서만 표시) */}
        <div className="hidden xl:flex flex-col gap-4 w-[300px] shrink-0">
          <StatCard
            icon={<MessageSquare size={20} className="text-white" />}
            iconBg="bg-primary"
            label="실시간 토론"
            value={stats.live}
          />
          <StatCard
            icon={<Users size={20} className="text-white" />}
            iconBg="bg-teal-500"
            label="오늘의 참여자"
            value={stats.todayParticipants > 0 ? stats.todayParticipants.toLocaleString() : '-'}
          />
          <StatCard
            icon={<Clock size={20} className="text-white" />}
            iconBg="bg-amber-500"
            label="진행 예정"
            value={stats.scheduled}
          />
          {ranking.length > 0 && (
            <div className="bg-bg-surface border border-border rounded-2xl p-4">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
                🏆 랭킹 Top 5
              </p>
              <div className="flex flex-col gap-2">
                {ranking.slice(0, 5).map((entry, idx) => (
                  <div key={entry.id} className="flex items-center gap-2 text-sm">
                    <span
                      className={`w-5 text-center font-bold text-xs ${
                        idx === 0
                          ? 'text-yellow-400'
                          : idx === 1
                            ? 'text-text'
                            : idx === 2
                              ? 'text-orange-400'
                              : 'text-text-muted'
                      }`}
                    >
                      {idx + 1}
                    </span>
                    <span className="text-text truncate flex-1">{entry.name}</span>
                    <span className="text-text-muted text-xs shrink-0">{entry.elo_rating}</span>
                  </div>
                ))}
              </div>
              <Link
                href="/debate/ranking"
                className="block mt-3 text-center text-xs text-primary hover:underline no-underline"
              >
                전체 랭킹 보기 →
              </Link>
            </div>
          )}
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
