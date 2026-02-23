'use client';

import { useEffect, useState } from 'react';
import { Globe, Plus, Edit, Trash2, Power, PowerOff } from 'lucide-react';
import { useWorldEventStore } from '@/stores/worldEventStore';
import type { WorldEvent, WorldEventCreate } from '@/stores/worldEventStore';

const EVENT_TYPE_LABELS: Record<string, string> = {
  world_state: '세계 상태',
  seasonal: '시즌 이벤트',
  crisis: '위기 상황',
  lore_update: '로어 업데이트',
};

export default function AdminWorldEventsPage() {
  const { events, total, loading, fetchAll, create, update, remove } = useWorldEventStore();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<WorldEventCreate>({
    title: '',
    content: '',
    event_type: 'world_state',
    priority: 0,
    age_rating: 'all',
  });

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleSubmit = async () => {
    if (!form.title || !form.content) return;
    if (editingId) {
      await update(editingId, form);
      setEditingId(null);
    } else {
      await create(form);
    }
    setForm({ title: '', content: '', event_type: 'world_state', priority: 0, age_rating: 'all' });
    setShowForm(false);
  };

  const handleEdit = (event: WorldEvent) => {
    setEditingId(event.id);
    setForm({
      title: event.title,
      content: event.content,
      event_type: event.event_type,
      priority: event.priority,
      starts_at: event.starts_at,
      expires_at: event.expires_at,
      age_rating: event.age_rating,
    });
    setShowForm(true);
  };

  const handleToggleActive = async (event: WorldEvent) => {
    await update(event.id, { is_active: !event.is_active });
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-text flex items-center gap-2">
          <Globe size={24} className="text-primary" />
          세계관 이벤트 관리
        </h1>
        <button
          onClick={() => {
            setShowForm(!showForm);
            setEditingId(null);
            setForm({ title: '', content: '', event_type: 'world_state', priority: 0, age_rating: 'all' });
          }}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-primary text-white border-none cursor-pointer"
        >
          <Plus size={16} />
          이벤트 생성
        </button>
      </div>

      {/* 생성/편집 폼 */}
      {showForm && (
        <div className="bg-bg-surface border border-border rounded-xl p-4 mb-6">
          <h2 className="text-sm font-bold text-text mb-3">
            {editingId ? '이벤트 수정' : '새 이벤트 생성'}
          </h2>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs font-semibold text-text-muted mb-1">제목</label>
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm"
                placeholder="유성 접근..."
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-muted mb-1">유형</label>
              <select
                value={form.event_type}
                onChange={(e) => setForm({ ...form, event_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm"
              >
                {Object.entries(EVENT_TYPE_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="mb-3">
            <label className="block text-xs font-semibold text-text-muted mb-1">내용</label>
            <textarea
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              rows={3}
              className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm resize-y"
              placeholder="캐릭터들이 인지하고 반응할 세계 상황을 설명..."
            />
          </div>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs font-semibold text-text-muted mb-1">우선순위</label>
              <input
                type="number"
                min={0}
                max={100}
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-muted mb-1">연령등급</label>
              <select
                value={form.age_rating}
                onChange={(e) => setForm({ ...form, age_rating: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm"
              >
                <option value="all">전체</option>
                <option value="15+">15+</option>
                <option value="18+">18+</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs font-semibold text-text-muted mb-1">시작일시</label>
              <input
                type="datetime-local"
                value={form.starts_at ? new Date(form.starts_at).toISOString().slice(0, 16) : ''}
                onChange={(e) =>
                  setForm({ ...form, starts_at: e.target.value ? new Date(e.target.value).toISOString() : null })
                }
                className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-muted mb-1">만료일시</label>
              <input
                type="datetime-local"
                value={form.expires_at ? new Date(form.expires_at).toISOString().slice(0, 16) : ''}
                onChange={(e) =>
                  setForm({ ...form, expires_at: e.target.value ? new Date(e.target.value).toISOString() : null })
                }
                className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => { setShowForm(false); setEditingId(null); }}
              className="px-4 py-2 rounded-lg text-sm text-text-muted bg-bg-hover border-none cursor-pointer"
            >
              취소
            </button>
            <button
              onClick={handleSubmit}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-primary text-white border-none cursor-pointer"
            >
              {editingId ? '수정' : '생성'}
            </button>
          </div>
        </div>
      )}

      {/* 이벤트 목록 */}
      <div className="flex flex-col gap-3">
        {events.map((event) => (
          <div
            key={event.id}
            className={`bg-bg-surface border rounded-xl p-4 ${
              event.is_active ? 'border-primary/30' : 'border-border opacity-60'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-text">{event.title}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary">
                  {EVENT_TYPE_LABELS[event.event_type] || event.event_type}
                </span>
                <span className="text-xs text-text-muted">P{event.priority}</span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleToggleActive(event)}
                  className="p-1.5 rounded text-text-muted hover:text-primary bg-transparent border-none cursor-pointer"
                  title={event.is_active ? '비활성화' : '활성화'}
                >
                  {event.is_active ? <Power size={14} /> : <PowerOff size={14} />}
                </button>
                <button
                  onClick={() => handleEdit(event)}
                  className="p-1.5 rounded text-text-muted hover:text-text bg-transparent border-none cursor-pointer"
                >
                  <Edit size={14} />
                </button>
                <button
                  onClick={() => remove(event.id)}
                  className="p-1.5 rounded text-text-muted hover:text-danger bg-transparent border-none cursor-pointer"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            <p className="text-xs text-text-secondary line-clamp-2">{event.content}</p>
            <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
              <span>{event.age_rating}</span>
              {event.starts_at && <span>시작: {new Date(event.starts_at).toLocaleDateString('ko-KR')}</span>}
              {event.expires_at && <span>만료: {new Date(event.expires_at).toLocaleDateString('ko-KR')}</span>}
            </div>
          </div>
        ))}

        {events.length === 0 && !loading && (
          <div className="text-center py-12 text-text-muted text-sm">
            세계관 이벤트가 없습니다. 새 이벤트를 생성하세요.
          </div>
        )}
      </div>
    </div>
  );
}
