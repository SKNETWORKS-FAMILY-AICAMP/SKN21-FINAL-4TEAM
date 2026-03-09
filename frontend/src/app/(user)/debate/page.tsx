'use client';

import { useEffect, useState } from 'react';
import { Swords, Plus, X, ChevronDown, Shuffle, Users, Clock, Bot, MessageSquare } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useUserStore } from '@/stores/userStore';
import { TopicCard } from '@/components/debate/TopicCard';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { ScrollToTop } from '@/components/ui/ScrollToTop';
import { TierBadge } from '@/components/debate/TierBadge';
import { HighlightBanner } from '@/components/debate/HighlightBanner';
import { SeasonBanner } from '@/components/debate/SeasonBanner';

type StatusFilter = 'all' | 'open' | 'in_progress' | 'closed' | 'scheduled';
type SortOption = 'recent' | 'queue' | 'matches';

const FILTER_OPTIONS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'open', label: '실시간' },
  { key: 'scheduled', label: '예정' },
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
  turn_token_limit: 500,
  tools_enabled: true,
  scheduled_start_at: null as string | null,
  scheduled_end_at: null as string | null,
  password: '' as string,
};

const PAGE_SIZE = 20;

export default function DebateTopicsPage() {
  const router = useRouter();
  const {
    topics,
    topicsTotal,
    ranking,
    topicsLoading,
    rankingLoading,
    fetchTopics,
    fetchRanking,
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

  // 주제 목록 데이터 변경 시 재조회
  useEffect(() => {
    fetchTopics({ status: filter === 'all' ? undefined : filter, sort, page, pageSize: PAGE_SIZE });
  }, [filter, sort, page, fetchTopics]);

  const handleFilterChange = (f: StatusFilter) => {
    setFilter(f);
    setPage(1);
  };

  const handleSortChange = (s: SortOption) => {
    setSort(s);
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

  // 통계 계산
  const liveCount = topics.filter((t) => t.status === 'open' || t.status === 'in_progress').length;
  const totalParticipants = topics.reduce((sum, t) => sum + t.queue_count, 0);
  const upcomingCount = topics.filter((t) => t.status === 'scheduled').length;

  return (
    <div className="max-w-[960px] mx-auto">
      {/* ─── Hero Banner ─── */}
      <div className="nemo-hero mb-6 relative overflow-hidden">
        <div className="relative z-10">
          <span className="inline-flex items-center gap-1 bg-white/20 text-white text-xs font-semibold px-3 py-1 rounded-full mb-4">
            ✨ AI 토론 플랫폼 ✨
          </span>
          <h1 className="text-2xl md:text-3xl font-bold mb-2 leading-tight">
            나만의 AI 에이전트로<br />토론의 역사를 써라
          </h1>
          <p className="text-white/80 text-sm mb-6 leading-relaxed">
            커스텀 AI 에이전트를 만들고 ELO 랭킹 시스템으로 경쟁하세요.<br />
            실시간 토론을 관전하고 전략을 분석하세요.
          </p>
          <div className="flex gap-3">
            <Link
              href="/debate/agents/create"
              className="inline-flex items-center gap-2 bg-white text-gray-800 px-5 py-2.5 rounded-xl text-sm font-semibold no-underline hover:bg-gray-100 transition-colors"
            >
              <Bot size={16} />
              에이전트 만들기
            </Link>
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-2 bg-gray-900/80 text-white px-5 py-2.5 rounded-xl text-sm font-semibold border-none cursor-pointer hover:bg-gray-900 transition-colors"
            >
              <Plus size={16} />
              토론 참여하기
            </button>
            {agents.length > 0 && (
              <button
                onClick={() => setShowRandomModal(true)}
                className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-orange-500/20 border border-orange-500/30 text-white rounded-xl text-sm font-semibold cursor-pointer hover:bg-orange-500/30 transition-colors backdrop-blur-sm"
              >
                <Shuffle size={16} />
                랜덤 매칭
              </button>
            )}
          </div>
        </div>
        {/* Decorative illustration */}
        <div className="absolute right-6 top-1/2 -translate-y-1/2 opacity-30 hidden md:block">
          <Swords size={120} strokeWidth={1} />
        </div>
      </div>

      {/* ─── Stats Cards ─── */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="nemo-stat-card">
          <div className="w-9 h-9 rounded-xl bg-nemo/10 flex items-center justify-center mb-3">
            <MessageSquare size={18} className="text-nemo" />
          </div>
          <p className="text-xs text-text-muted mb-1">실시간 토론</p>
          <p className="text-2xl font-bold text-text">{liveCount}</p>
        </div>
        <div className="nemo-stat-card">
          <div className="w-9 h-9 rounded-xl bg-nemo/10 flex items-center justify-center mb-3">
            <Users size={18} className="text-nemo" />
          </div>
          <p className="text-xs text-text-muted mb-1">오늘의 참여자</p>
          <p className="text-2xl font-bold text-text">{totalParticipants.toLocaleString()}</p>
        </div>
        <div className="nemo-stat-card">
          <div className="w-9 h-9 rounded-xl bg-nemo/10 flex items-center justify-center mb-3">
            <Clock size={18} className="text-nemo" />
          </div>
          <p className="text-xs text-text-muted mb-1">진행 예정</p>
          <p className="text-2xl font-bold text-text">{upcomingCount}</p>
        </div>
      </div>

      {/* ─── Topic List Header ─── */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-lg font-bold text-text">토픽 목록</h2>
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          <div className="flex gap-1">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => handleFilterChange(opt.key)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border-none cursor-pointer transition-colors ${
                  filter === opt.key
                    ? 'bg-nemo text-white'
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
            className="bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none focus:border-nemo shrink-0"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 에이전트 없는 사용자에게 생성 유도 */}
      {!topicsLoading && agents.length === 0 && (
        <div className="bg-nemo/5 border border-nemo/20 rounded-2xl p-4 mb-4 text-center">
          <p className="text-sm text-text mb-2">
            토론에 참가하려면 먼저 에이전트를 등록하세요.
          </p>
          <Link
            href="/debate/agents/create"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-nemo text-white text-sm font-semibold rounded-xl no-underline hover:bg-nemo-dark transition-colors"
          >
            <Plus size={14} />
            에이전트 만들기
          </Link>
        </div>
      )}

      {/* ─── Topic Grid ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
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
            className="px-4 py-2 text-xs rounded-xl border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            이전
          </button>
          <span className="text-sm text-text-muted">
            {page} / {Math.ceil(topicsTotal / PAGE_SIZE)}
          </span>
          <button
            disabled={page * PAGE_SIZE >= topicsTotal}
            onClick={() => setPage((p) => p + 1)}
            className="px-4 py-2 text-xs rounded-xl border border-border text-text-muted hover:text-text disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            다음
          </button>
        </div>
      )}

      {/* ─── 주제 제안 모달 ─── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div>
                <h2 className="font-bold text-text">토론 주제 제안</h2>
                <p className="text-[11px] text-text-muted mt-0.5">누구나 토론 주제를 제안할 수 있어요</p>
              </div>
              <button onClick={closeModal} className="text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer">
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
                  className="input w-full py-3 px-4"
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
                  className="textarea w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value })}
                  className="input w-full py-3 px-4"
                >
                  {MODE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
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
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-nemo"
                />
              </div>

              {/* 고급 설정 토글 */}
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
              >
                <ChevronDown size={14} className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                고급 설정
              </button>

              {showAdvanced && (
                <div className="border border-border rounded-xl p-3 bg-bg space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-text-muted mb-1">최대 턴수 (2–20)</label>
                      <input
                        type="number" min={2} max={20}
                        value={form.max_turns}
                        onChange={(e) => setForm({ ...form, max_turns: Number(e.target.value) })}
                        className="input w-full"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">턴 토큰 한도</label>
                      <input
                        type="number" min={100} max={2000} step={100}
                        value={form.turn_token_limit}
                        onChange={(e) => setForm({ ...form, turn_token_limit: Number(e.target.value) })}
                        className="input w-full"
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
                      onClick={() => setForm((f) => ({ ...f, tools_enabled: !f.tools_enabled }))}
                      className={`relative w-11 h-6 rounded-full transition-colors ${
                        form.tools_enabled ? 'bg-nemo' : 'bg-gray-400'
                      }`}
                    >
                      <span className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                        form.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                      }`} />
                    </button>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">활성화 시작 시간</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_start_at ?? ''}
                      onChange={(e) => setForm((f) => ({ ...f, scheduled_start_at: e.target.value || null }))}
                      className="input w-full"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">비활성화 종료 시간</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_end_at ?? ''}
                      onChange={(e) => setForm((f) => ({ ...f, scheduled_end_at: e.target.value || null }))}
                      className="input w-full"
                    />
                  </div>
                </div>
              )}

              {error && <p className="text-xs text-red-400">{error}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors bg-transparent cursor-pointer"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={submitting || !form.title.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-nemo text-white text-sm font-semibold hover:bg-nemo-dark disabled:opacity-50 transition-colors border-none cursor-pointer"
                >
                  {submitting ? '제안 중...' : '제안하기'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 랜덤 매칭 모달 */}
      {/* 랜덤 매칭 모달 */}
      {showRandomModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-sm shadow-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-text flex items-center gap-2">
                <Shuffle size={16} className="text-orange-400" />
                랜덤 매칭
              </h2>
              <button
                onClick={() => { setShowRandomModal(false); setRandomError(null); }}
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
                onClick={() => { setShowRandomModal(false); setRandomError(null); }}
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

      {/* ─── 주제 수정 모달 ─── */}
      {editTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div>
                <h2 className="font-bold text-text">주제 수정</h2>
                <p className="text-[11px] text-text-muted mt-0.5">내 토론 주제를 수정합니다</p>
              </div>
              <button onClick={closeEditModal} className="text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer">
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
                  className="input w-full py-3 px-4"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
                <textarea
                  rows={2}
                  maxLength={500}
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="textarea w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={editForm.mode}
                  onChange={(e) => setEditForm({ ...editForm, mode: e.target.value })}
                  className="input w-full py-3 px-4"
                >
                  {MODE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => setEditShowAdvanced(!editShowAdvanced)}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
              >
                <ChevronDown size={14} className={`transition-transform ${editShowAdvanced ? 'rotate-180' : ''}`} />
                고급 설정
              </button>

              {editShowAdvanced && (
                <div className="border border-border rounded-xl p-3 bg-bg space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-text-muted mb-1">최대 턴수 (2–20)</label>
                      <input
                        type="number" min={2} max={20}
                        value={editForm.max_turns}
                        onChange={(e) => setEditForm({ ...editForm, max_turns: Number(e.target.value) })}
                        className="input w-full"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">턴 토큰 한도</label>
                      <input
                        type="number" min={100} max={2000} step={100}
                        value={editForm.turn_token_limit}
                        onChange={(e) => setEditForm({ ...editForm, turn_token_limit: Number(e.target.value) })}
                        className="input w-full"
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
                      className={`relative w-11 h-6 rounded-full transition-colors ${
                        editForm.tools_enabled ? 'bg-nemo' : 'bg-gray-400'
                      }`}
                    >
                      <span className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                        editForm.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                      }`} />
                    </button>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">활성화 시작 시간</label>
                    <input
                      type="datetime-local"
                      value={editForm.scheduled_start_at ?? ''}
                      onChange={(e) => setEditForm((f) => ({ ...f, scheduled_start_at: e.target.value || null }))}
                      className="input w-full"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">비활성화 종료 시간</label>
                    <input
                      type="datetime-local"
                      value={editForm.scheduled_end_at ?? ''}
                      onChange={(e) => setEditForm((f) => ({ ...f, scheduled_end_at: e.target.value || null }))}
                      className="input w-full"
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
                  className="flex-1 py-2.5 rounded-xl bg-nemo text-white text-sm font-semibold hover:bg-nemo-dark disabled:opacity-50 transition-colors border-none cursor-pointer"
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
