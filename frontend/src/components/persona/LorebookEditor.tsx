/** 로어북(세계관 설정) 편집기. 페르소나별 로어북 항목 CRUD + 태그 관리. */
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';

type LorebookEntry = {
  id: string;
  title: string;
  content: string;
  tags: string[];
};

type Props = {
  personaId: string;
};

export function LorebookEditor({ personaId }: Props) {
  const [entries, setEntries] = useState<LorebookEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ title: '', content: '', tags: '' });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchEntries = async () => {
    setLoading(true);
    try {
      const data = await api.get<{ items: LorebookEntry[]; total: number }>(`/lorebook/persona/${personaId}`);
      setEntries(data.items ?? []);
    } catch {
      /* empty */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntries();
  }, [personaId]);

  const handleSave = async () => {
    const body = {
      title: form.title,
      content: form.content,
      tags: form.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    };

    setSaving(true);
    try {
      if (editing) {
        await api.put(`/lorebook/${editing}`, body);
        toast.success('항목이 수정되었습니다.');
      } else {
        await api.post('/lorebook', { ...body, persona_id: personaId });
        toast.success('항목이 추가되었습니다.');
      }
      setForm({ title: '', content: '', tags: '' });
      setEditing(null);
      fetchEntries();
    } catch {
      toast.error('저장에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (entry: LorebookEntry) => {
    setEditing(entry.id);
    setForm({ title: entry.title, content: entry.content, tags: entry.tags.join(', ') });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/lorebook/${deleteTarget}`);
      toast.success('항목이 삭제되었습니다.');
      fetchEntries();
    } catch {
      toast.error('삭제에 실패했습니다.');
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2.5 bg-bg-surface p-5 rounded-xl border border-border">
        <h3 className="m-0 text-base text-text">{editing ? '항목 수정' : '새 항목 추가'}</h3>
        <input
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          placeholder="제목 (예: 세계관 설정)"
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none bg-bg-input text-text"
        />
        <textarea
          value={form.content}
          onChange={(e) => setForm({ ...form, content: e.target.value })}
          placeholder="내용을 입력하세요..."
          rows={4}
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none font-[inherit] resize-y bg-bg-input text-text"
        />
        <input
          value={form.tags}
          onChange={(e) => setForm({ ...form, tags: e.target.value })}
          placeholder="태그 (쉼표로 구분)"
          className="py-2.5 px-3 border border-border-input rounded-lg text-sm outline-none bg-bg-input text-text"
        />
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            className="py-2 px-5 border-none rounded-lg bg-primary text-white text-[13px] font-semibold cursor-pointer disabled:opacity-50"
            disabled={!form.title || !form.content || saving}
          >
            {saving ? '저장 중...' : editing ? '수정' : '추가'}
          </button>
          {editing && (
            <button
              onClick={() => {
                setEditing(null);
                setForm({ title: '', content: '', tags: '' });
              }}
              className="py-2 px-5 border border-border-input rounded-lg bg-bg-surface text-text text-[13px] cursor-pointer"
            >
              취소
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {loading && <div className="text-center text-text-muted p-5 text-sm">불러오는 중...</div>}
        {!loading && entries.length === 0 && (
          <div className="text-center text-text-muted p-5 text-sm">
            로어북 항목이 없습니다. 위에서 추가하세요.
          </div>
        )}
        {entries.map((entry) => (
          <div key={entry.id} className="bg-bg-surface p-4 rounded-xl border border-border">
            <div className="flex justify-between items-center">
              <h4 className="m-0 text-[15px] text-text">{entry.title}</h4>
              <div className="flex gap-1.5">
                <button
                  onClick={() => handleEdit(entry)}
                  className="py-1 px-3 border border-border-input rounded-md bg-bg-surface text-text text-xs cursor-pointer"
                >
                  수정
                </button>
                <button
                  onClick={() => setDeleteTarget(entry.id)}
                  className="py-1 px-3 border border-border-delete rounded-md bg-bg-surface text-danger-text text-xs cursor-pointer"
                >
                  삭제
                </button>
              </div>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed my-2">{entry.content}</p>
            {entry.tags.length > 0 && (
              <div className="flex gap-1.5 flex-wrap">
                {entry.tags.map((tag, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-0.5 rounded-xl bg-bg-tag text-xs text-text-secondary"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="항목 삭제"
        message="이 로어북 항목을 삭제하시겠습니까? 삭제하면 되돌릴 수 없습니다."
        confirmLabel="삭제"
        variant="danger"
        loading={deleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
