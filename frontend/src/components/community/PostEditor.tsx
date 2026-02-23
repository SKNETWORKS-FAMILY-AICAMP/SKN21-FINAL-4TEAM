'use client';

import { useState } from 'react';
import { Send } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

type Props = {
  boardId: string;
  onCreated?: () => void;
};

export function PostEditor({ boardId, onCreated }: Props) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setSubmitting(true);
    try {
      await api.post(`/board/${boardId}/posts`, {
        title: title.trim() || null,
        content: content.trim(),
      });
      setTitle('');
      setContent('');
      toast.success('게시글이 작성되었습니다');
      onCreated?.();
    } catch {
      toast.error('게시글 작성에 실패했습니다');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card p-4">
      <input
        type="text"
        placeholder="제목 (선택)"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
        className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-sm text-text placeholder-text-muted mb-2 outline-none focus:border-primary"
      />
      <textarea
        placeholder="무슨 이야기를 나누고 싶으세요?"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        maxLength={5000}
        rows={3}
        className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-sm text-text placeholder-text-muted resize-none outline-none focus:border-primary"
      />
      <div className="flex justify-between items-center mt-2">
        <span className="text-xs text-text-muted">{content.length}/5000</span>
        <button
          onClick={handleSubmit}
          disabled={!content.trim() || submitting}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold border-none cursor-pointer transition-colors duration-200 ${
            content.trim() && !submitting
              ? 'bg-primary text-white hover:bg-primary/90'
              : 'bg-bg-hover text-text-muted cursor-not-allowed'
          }`}
        >
          <Send size={14} />
          게시
        </button>
      </div>
    </div>
  );
}
