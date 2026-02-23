'use client';

import { useEffect, useState } from 'react';
import { Brain, Trash2, Plus } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

type Memory = {
  id: string;
  memory_type: string;
  namespace: string;
  key: string;
  value: unknown;
  created_at: string;
};

export function MemoriesTab() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');

  useEffect(() => {
    loadMemories();
  }, []);

  const loadMemories = () => {
    api
      .get<{ items: Memory[]; total: number }>('/memories/')
      .then((res) => setMemories(res.items ?? []))
      .catch(() => {});
  };

  const handleAdd = async () => {
    if (!key.trim() || !value.trim()) return;
    try {
      await api.post('/memories/', {
        key: key.trim(),
        value: { text: value.trim() },
        namespace: 'manual',
        memory_type: 'manual',
      });
      setShowForm(false);
      setKey('');
      setValue('');
      loadMemories();
      toast.success('기억 추가됨');
    } catch {
      toast.error('추가 실패');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/memories/${id}`);
      setMemories((prev) => prev.filter((m) => m.id !== id));
      toast.success('삭제됨');
    } catch {
      toast.error('삭제 실패');
    }
  };

  const grouped = memories.reduce<Record<string, Memory[]>>((acc, m) => {
    const ns = m.namespace || 'general';
    if (!acc[ns]) acc[ns] = [];
    acc[ns].push(m);
    return acc;
  }, {});

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-text-secondary m-0">AI가 기억하고 있는 정보를 관리하세요</p>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-white border-none cursor-pointer hover:bg-primary-dark"
        >
          <Plus size={14} />
          수동 추가
        </button>
      </div>

      {showForm && (
        <div className="bg-bg-hover rounded-xl p-4 mb-4">
          <input
            type="text"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="제목 (예: 좋아하는 웹툰)"
            className="input w-full mb-3"
          />
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="내용"
            className="input w-full mb-3 min-h-[60px] resize-y"
          />
          <div className="flex gap-2">
            <button onClick={handleAdd} className="btn-primary text-sm">추가</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">취소</button>
          </div>
        </div>
      )}

      {Object.entries(grouped).map(([ns, items]) => (
        <div key={ns} className="mb-6">
          <h3 className="text-xs font-semibold text-text-muted uppercase mb-2 flex items-center gap-1">
            <Brain size={12} />
            {ns}
          </h3>
          <div className="flex flex-col gap-2">
            {items.map((m) => (
              <div
                key={m.id}
                className="flex items-start justify-between p-3 rounded-lg border border-border bg-bg-surface"
              >
                <div>
                  <div className="text-sm font-medium text-text">{m.key}</div>
                  <div className="text-xs text-text-secondary mt-0.5">
                    {typeof m.value === 'object' ? JSON.stringify(m.value) : String(m.value)}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(m.id)}
                  className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-red-400 transition-colors border-none bg-transparent cursor-pointer flex-shrink-0"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}

      {memories.length === 0 && !showForm && (
        <p className="text-sm text-text-muted text-center py-8">아직 저장된 기억이 없습니다</p>
      )}
    </div>
  );
}
