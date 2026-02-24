'use client';

import { useEffect, useState } from 'react';
import { Swords, Bot, MessageSquare, Trophy, Activity, Plus, X, CalendarClock } from 'lucide-react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';

type DebateStats = {
  agents_count: number;
  topics_count: number;
  matches_total: number;
  matches_completed: number;
  matches_in_progress: number;
};

type Topic = {
  id: string;
  title: string;
  description: string | null;
  mode: string;
  status: string;
  max_turns: number;
  turn_token_limit: number;
  scheduled_start_at: string | null;
  scheduled_end_at: string | null;
  is_admin_topic: boolean;
  queue_count: number;
  match_count: number;
  created_at: string;
};

const MODE_LABELS: Record<string, string> = {
  debate: '찬반 토론',
  persuasion: '설득',
  cross_exam: '교차 심문',
};

const STATUS_COLORS: Record<string, string> = {
  scheduled: 'text-blue-400',
  open: 'text-green-500',
  in_progress: 'text-yellow-500',
  closed: 'text-text-muted',
};

const STATUS_LABELS: Record<string, string> = {
  scheduled: '예정',
  open: '모집 중',
  in_progress: '진행 중',
  closed: '종료',
};

/** 로컬 datetime-local 값을 ISO 문자열로 변환. 빈 값이면 null. */
function toISOOrNull(localStr: string): string | null {
  if (!localStr) return null;
  return new Date(localStr).toISOString();
}

/** ISO → datetime-local input 값 형식 (YYYY-MM-DDTHH:mm) */
function toLocalDatetime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AdminDebatePage() {
  const [stats, setStats] = useState<DebateStats | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState({
    title: '',
    description: '',
    mode: 'debate',
    max_turns: 6,
    turn_token_limit: 500,
    scheduled_start_at: '',
    scheduled_end_at: '',
  });

  const fetchData = () => {
    api.get<DebateStats>('/admin/debate/stats').then(setStats).catch(() => {});
    api
      .get<{ items: Topic[]; total: number }>('/topics?limit=50')
      .then((r) => setTopics(r.items))
      .catch(() => {});
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const startAt = toISOOrNull(form.scheduled_start_at);
    const endAt = toISOOrNull(form.scheduled_end_at);

    if (startAt && endAt && new Date(endAt) <= new Date(startAt)) {
      setError('종료 시각은 시작 시각보다 뒤여야 합니다.');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/topics', {
        title: form.title.trim(),
        description: form.description.trim() || null,
        mode: form.mode,
        max_turns: form.max_turns,
        turn_token_limit: form.turn_token_limit,
        scheduled_start_at: startAt,
        scheduled_end_at: endAt,
      });
      setSuccess(true);
      setForm({
        title: '',
        description: '',
        mode: 'debate',
        max_turns: 6,
        turn_token_limit: 500,
        scheduled_start_at: '',
        scheduled_end_at: '',
      });
      setShowForm(false);
      fetchData();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '생성 실패';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-text mb-5 flex items-center gap-2">
        <Swords size={22} className="text-primary" />
        AI 토론 관리
      </h1>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <StatCard title="에이전트" value={stats?.agents_count ?? 0} icon={<Bot size={18} />} />
        <StatCard
          title="토론 주제"
          value={stats?.topics_count ?? 0}
          icon={<MessageSquare size={18} />}
        />
        <StatCard title="총 매치" value={stats?.matches_total ?? 0} icon={<Trophy size={18} />} />
        <StatCard
          title="완료 매치"
          value={stats?.matches_completed ?? 0}
          icon={<Trophy size={18} />}
        />
        <StatCard
          title="진행 중"
          value={stats?.matches_in_progress ?? 0}
          icon={<Activity size={18} />}
        />
      </div>

      {/* 토론 주제 섹션 */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-text">토론 주제</h2>
          <button
            onClick={() => {
              setShowForm(!showForm);
              setError(null);
            }}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            {showForm ? <X size={15} /> : <Plus size={15} />}
            {showForm ? '닫기' : '새 주제 생성'}
          </button>
        </div>

        {success && (
          <div className="mb-4 text-sm text-green-500 bg-green-500/10 rounded-lg px-3 py-2">
            토론 주제가 생성되었습니다.
          </div>
        )}

        {/* 생성 폼 */}
        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="mb-5 bg-bg border border-border rounded-lg p-4 space-y-3"
          >
            <div>
              <label className="block text-xs text-text-muted mb-1">
                주제 제목 <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                required
                maxLength={200}
                placeholder="예: 인공지능은 인간의 일자리를 빼앗는가?"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
              <textarea
                rows={2}
                maxLength={1000}
                placeholder="주제에 대한 배경 설명"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary resize-none"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value })}
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                >
                  <option value="debate">찬반 토론</option>
                  <option value="persuasion">설득</option>
                  <option value="cross_exam">교차 심문</option>
                </select>
              </div>

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
                <label className="block text-xs text-text-muted mb-1">턴 토큰 한도 (100–2000)</label>
                <input
                  type="number"
                  min={100}
                  max={2000}
                  step={100}
                  value={form.turn_token_limit}
                  onChange={(e) => setForm({ ...form, turn_token_limit: Number(e.target.value) })}
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                />
              </div>
            </div>

            {/* 스케줄 설정 (관리자 전용) */}
            <div className="border border-primary/20 rounded-lg p-3 bg-primary/5">
              <p className="text-xs font-semibold text-primary mb-2 flex items-center gap-1.5">
                <CalendarClock size={13} />
                자동 스케줄 설정 (선택)
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-text-muted mb-1">시작 시각</label>
                  <input
                    type="datetime-local"
                    value={form.scheduled_start_at}
                    onChange={(e) => setForm({ ...form, scheduled_start_at: e.target.value })}
                    className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                  />
                  <p className="text-[10px] text-text-muted mt-0.5">비워두면 즉시 모집 시작</p>
                </div>
                <div>
                  <label className="block text-xs text-text-muted mb-1">종료 시각</label>
                  <input
                    type="datetime-local"
                    value={form.scheduled_end_at}
                    min={form.scheduled_start_at || undefined}
                    onChange={(e) => setForm({ ...form, scheduled_end_at: e.target.value })}
                    className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                  />
                  <p className="text-[10px] text-text-muted mt-0.5">도달 시 자동으로 토론 종료</p>
                </div>
              </div>
            </div>

            {error && <p className="text-xs text-red-400">{error}</p>}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setError(null);
                }}
                className="text-sm px-4 py-1.5 rounded-lg border border-border text-text-muted hover:text-text transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={submitting || !form.title.trim()}
                className="text-sm px-4 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {submitting ? '생성 중...' : '주제 생성'}
              </button>
            </div>
          </form>
        )}

        {/* 주제 목록 */}
        {topics.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-6">생성된 토론 주제가 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-left">
                  <th className="pb-2 pr-4 font-medium">제목</th>
                  <th className="pb-2 pr-4 font-medium">방식</th>
                  <th className="pb-2 pr-4 font-medium">상태</th>
                  <th className="pb-2 pr-4 font-medium">스케줄</th>
                  <th className="pb-2 pr-4 font-medium text-right">턴수</th>
                  <th className="pb-2 pr-4 font-medium text-right">매치</th>
                  <th className="pb-2 font-medium text-right">대기</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {topics.map((t) => (
                  <tr key={t.id} className="hover:bg-bg transition-colors">
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-1.5">
                        {t.is_admin_topic && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-semibold">
                            공식
                          </span>
                        )}
                        <span className="font-medium text-text">{t.title}</span>
                      </div>
                      {t.description && (
                        <p className="text-xs text-text-muted mt-0.5 line-clamp-1">
                          {t.description}
                        </p>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-text-muted">{MODE_LABELS[t.mode] ?? t.mode}</td>
                    <td className={`py-2 pr-4 font-medium ${STATUS_COLORS[t.status] ?? ''}`}>
                      {STATUS_LABELS[t.status] ?? t.status}
                    </td>
                    <td className="py-2 pr-4 text-xs text-text-muted">
                      {t.scheduled_start_at || t.scheduled_end_at ? (
                        <div className="flex flex-col gap-0.5">
                          {t.scheduled_start_at && (
                            <span>시작: {toLocalDatetime(t.scheduled_start_at).replace('T', ' ')}</span>
                          )}
                          {t.scheduled_end_at && (
                            <span>종료: {toLocalDatetime(t.scheduled_end_at).replace('T', ' ')}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-text-muted/50">-</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-right text-text-muted">{t.max_turns}</td>
                    <td className="py-2 pr-4 text-right text-text-muted">{t.match_count}</td>
                    <td className="py-2 text-right text-text-muted">{t.queue_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
