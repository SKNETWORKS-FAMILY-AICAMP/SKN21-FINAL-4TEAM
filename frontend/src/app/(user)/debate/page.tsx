'use client';

import { useEffect, useState } from 'react';
import { Swords, Plus, X, ChevronDown, Shuffle, MessageSquare, Users, Clock, Trophy } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useUserStore } from '@/stores/userStore';
import { TopicCard } from '@/components/debate/TopicCard';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { ScrollToTop } from '@/components/ui/ScrollToTop';

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
    ranking,
    rankingLoading,
    fetchRanking,
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

  // 캐러셀 슬라이드 인덱스
  const [slideIndex, setSlideIndex] = useState(0);

  // 초기 로드
  useEffect(() => {
    fetchMyAgents();
    fetchFeatured();
    fetchRanking();
  }, [fetchMyAgents, fetchFeatured, fetchRanking]);

  // 토픽 로드 (필터/정렬/페이지 변경 시 재조회)
  useEffect(() => {
    fetchTopics({
      status: filter === 'all' ? undefined : filter,
      sort,
      page,
      pageSize: 20,
    });
  }, [fetchTopics, filter, sort, page]);

  // Infinite scroll trigger on downward wheel/scroll intent
  useEffect(() => {
    let lastScrollTime = 0;
    const cooldown = 1500; // 1.5s cooldown between batches to maintain rhythm

    const handleWheel = (e: WheelEvent) => {
      // Detect downward scroll intent
      if (e.deltaY > 0 && topics.length < topicsTotal && !isRefreshing) {
        const now = Date.now();
        if (now - lastScrollTime > cooldown) {
          lastScrollTime = now;
          setIsRefreshing(true);
          setTimeout(() => {
            setPage(prev => prev + 1);
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
    setPage(1);
  };

  const handleSortChange = (s: SortOption) => {
    setSort(s);
    setVisibleCount(8);
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

  // 캐러셀 슬라이드 구성 (페이지당 8개)
  const topicChunks: (typeof topics)[] = [];
  for (let i = 0; i < topics.length; i += 8) {
    topicChunks.push(topics.slice(i, i + 8));
  }

  // 랭킹 색상: 1위=금, 2위=은, 3위=동, 나머지=회색
  const rankColor = (rank: number) => {
    if (rank === 1) return 'text-yellow-500';
    if (rank === 2) return 'text-gray-400';
    if (rank === 3) return 'text-amber-600';
    return 'text-gray-500';
  };

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

      {/* 주요 토픽 캐러셀 + 랭킹 사이드바 */}
      <div className="flex gap-6 mt-6 mb-8">
        {/* 캐러셀 섹션 */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-black text-text-muted uppercase tracking-wider mb-3">
            주요 토픽
          </h3>
          {topicsLoading ? (
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : topicChunks.length === 0 ? (
            <div className="flex items-center justify-center h-40 rounded-xl border border-border bg-bg-surface">
              <div className="text-center text-text-muted">
                <MessageSquare size={32} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">등록된 토픽이 없습니다</p>
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                {topicChunks[slideIndex]?.map((topic) => (
                  <Link
                    key={topic.id}
                    href={`/debate/topics/${topic.id}`}
                    className="block p-4 rounded-xl border border-border bg-bg-surface hover:border-primary hover:translate-y-[-2px] transition-all no-underline"
                  >
                    <div className="flex items-start gap-2 mb-2">
                      {(topic as any).is_admin_topic && (
                        <span className="shrink-0 text-[10px] font-black px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                          공식
                        </span>
                      )}
                      <p className="text-sm font-semibold text-text line-clamp-2 leading-snug m-0">
                        {topic.title}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-text-muted">
                      <span className="flex items-center gap-1">
                        <Users size={11} />
                        대기 {topic.queue_count}
                      </span>
                      <span className="flex items-center gap-1">
                        <Swords size={11} />
                        {topic.match_count}전
                      </span>
                      <span className="ml-auto truncate">
                        {topic.creator_nickname ?? '관리자'}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
              {/* 캐러셀 인디케이터 */}
              {topicChunks.length > 1 && (
                <div className="flex justify-center gap-2 mt-3">
                  {topicChunks.map((_, idx) => (
                    <button
                      key={idx}
                      onClick={() => setSlideIndex(idx)}
                      className={`w-2 h-2 rounded-full transition-all ${
                        slideIndex === idx ? 'bg-primary w-4' : 'bg-border'
                      }`}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* 랭킹 사이드바 */}
        <div className="w-64 shrink-0">
          <h3 className="text-sm font-black text-text-muted uppercase tracking-wider mb-3 flex items-center gap-2">
            <Trophy size={14} className="text-yellow-500" />
            에이전트 랭킹
          </h3>
          <div className="bg-bg-surface border border-border rounded-xl overflow-hidden">
            {rankingLoading ? (
              <div className="p-4 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 animate-pulse">
                    <div className="w-6 h-4 bg-border rounded" />
                    <div className="flex-1 h-4 bg-border rounded" />
                    <div className="w-12 h-4 bg-border rounded" />
                  </div>
                ))}
              </div>
            ) : ranking.length === 0 ? (
              <div className="p-6 text-center text-text-muted">
                <Trophy size={24} className="mx-auto mb-2 opacity-30" />
                <p className="text-xs">아직 랭킹 데이터가 없습니다</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {ranking.map((r, index) => {
                  const rank = index + 1;
                  return (
                    <div key={r.id} className="flex items-center gap-3 px-4 py-2.5">
                      <span className={`w-5 text-center text-xs font-black shrink-0 ${rankColor(rank)}`}>
                        {rank}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-text truncate m-0 leading-tight">
                          {r.name}
                        </p>
                        <p className="text-[10px] text-text-muted truncate m-0">
                          {r.owner_nickname}
                        </p>
                      </div>
                      <span className="text-xs font-black text-primary shrink-0">
                        {r.elo_rating}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <Link
            href="/debate/agents?tab=ranking"
            className="block text-center text-xs text-text-muted hover:text-primary mt-2 no-underline transition-colors"
          >
            전체 랭킹 보기 →
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
            ) : topics.length === 0 ? (
              <div className="col-span-2 text-center py-16 text-text-muted">
                <MessageSquare size={40} className="mx-auto mb-3 opacity-30" />
                <p className="font-semibold">등록된 토픽이 없습니다</p>
              </div>
            ) : (
              topics.map((topic, index) => (
                <div
                  key={topic.id}
                  className="animate-in fill-mode-forwards opacity-100"
                  style={{ animationDelay: `${(index % 8) * 80}ms`, animationDuration: '0.5s' }}
                >
                  <TopicCard
                    topic={topic}
                    currentUserId={currentUserId}
                    onEdit={openEditModal}
                    onDelete={handleDelete}
                  />
                </div>
              ))
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
          {topicsTotal > 20 && (
            <div className="flex justify-center gap-3 mt-12 mb-8">
              {Array.from({ length: Math.ceil(topicsTotal / 20) }).map((_, idx) => (
                <button
                  key={idx}
                  disabled
                  className={`w-10 h-10 rounded-xl border-2 border-black font-black text-sm flex items-center justify-center transition-all ${
                    page >= idx + 1
                      ? 'bg-primary text-white brutal-shadow-sm'
                      : 'bg-white text-gray-300'
                  }`}
                >
                  {idx + 1}
                </button>
              ))}
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
                      onClick={() => setEditForm((f) => ({ ...f, tools_enabled: !f.tools_enabled }))}
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
                  className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors bg-transparent cursor-pointer"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={editSubmitting || !editForm.title.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors border-none cursor-pointer"
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
