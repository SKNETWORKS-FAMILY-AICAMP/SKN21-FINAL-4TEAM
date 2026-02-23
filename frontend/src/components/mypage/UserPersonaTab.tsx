'use client';

import { useEffect, useState } from 'react';
import { Plus, Star, Trash2, Pencil } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

type UserPersona = {
  id: string;
  display_name: string;
  description: string | null;
  avatar_url: string | null;
  is_default: boolean;
};

export function UserPersonaTab() {
  const [personas, setPersonas] = useState<UserPersona[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  useEffect(() => {
    loadPersonas();
  }, []);

  const loadPersonas = () => {
    api
      .get<UserPersona[]>('/user-personas/')
      .then(setPersonas)
      .catch(() => {});
  };

  const handleSubmit = async () => {
    if (!name.trim()) return;
    try {
      if (editId) {
        await api.patch(`/user-personas/${editId}`, { display_name: name, description: desc || null });
      } else {
        await api.post('/user-personas/', { display_name: name, description: desc || null });
      }
      setShowForm(false);
      setEditId(null);
      setName('');
      setDesc('');
      loadPersonas();
      toast.success(editId ? '수정됨' : '생성됨');
    } catch {
      toast.error('저장 실패');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/user-personas/${id}`);
      loadPersonas();
      toast.success('삭제됨');
    } catch {
      toast.error('삭제 실패');
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await api.post(`/user-personas/${id}/set-default`);
      loadPersonas();
      toast.success('기본 페르소나 설정됨');
    } catch {
      toast.error('설정 실패');
    }
  };

  const startEdit = (p: UserPersona) => {
    setEditId(p.id);
    setName(p.display_name);
    setDesc(p.description || '');
    setShowForm(true);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-text-secondary m-0">대화에서 사용할 나만의 캐릭터를 만들어보세요</p>
        <button
          onClick={() => { setShowForm(true); setEditId(null); setName(''); setDesc(''); }}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-white border-none cursor-pointer hover:bg-primary-dark"
        >
          <Plus size={14} />
          새 캐릭터
        </button>
      </div>

      {showForm && (
        <div className="bg-bg-hover rounded-xl p-4 mb-4">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="캐릭터 이름"
            className="input w-full mb-3"
          />
          <textarea
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="캐릭터 설명 (선택)"
            className="input w-full mb-3 min-h-[80px] resize-y"
          />
          <div className="flex gap-2">
            <button onClick={handleSubmit} className="btn-primary text-sm">
              {editId ? '수정' : '생성'}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">
              취소
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {personas.map((p) => (
          <div
            key={p.id}
            className={`flex items-center justify-between p-4 rounded-xl border transition-colors ${
              p.is_default ? 'border-primary bg-primary/5' : 'border-border bg-bg-surface'
            }`}
          >
            <div>
              <div className="flex items-center gap-2">
                <h3 className="m-0 text-sm font-semibold">{p.display_name}</h3>
                {p.is_default && (
                  <span className="text-[10px] font-semibold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                    기본
                  </span>
                )}
              </div>
              {p.description && (
                <p className="m-0 text-xs text-text-secondary mt-1">{p.description}</p>
              )}
            </div>
            <div className="flex items-center gap-1">
              {!p.is_default && (
                <button
                  onClick={() => handleSetDefault(p.id)}
                  className="p-1.5 rounded hover:bg-bg-hover text-text-muted hover:text-primary transition-colors border-none bg-transparent cursor-pointer"
                  title="기본으로 설정"
                >
                  <Star size={14} />
                </button>
              )}
              <button
                onClick={() => startEdit(p)}
                className="p-1.5 rounded hover:bg-bg-hover text-text-muted hover:text-text transition-colors border-none bg-transparent cursor-pointer"
                title="수정"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => handleDelete(p.id)}
                className="p-1.5 rounded hover:bg-bg-hover text-text-muted hover:text-red-400 transition-colors border-none bg-transparent cursor-pointer"
                title="삭제"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
        {personas.length === 0 && !showForm && (
          <p className="text-sm text-text-muted text-center py-8">아직 캐릭터가 없습니다</p>
        )}
      </div>
    </div>
  );
}
