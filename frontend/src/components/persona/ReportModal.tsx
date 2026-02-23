'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/stores/toastStore';

const REASONS = [
  { value: 'inappropriate', label: '부적절한 콘텐츠' },
  { value: 'sexual', label: '성적 콘텐츠' },
  { value: 'harassment', label: '괴롭힘 / 혐오' },
  { value: 'copyright', label: '저작권 침해' },
  { value: 'spam', label: '스팸' },
  { value: 'other', label: '기타' },
] as const;

type Props = {
  personaId: string;
  personaName: string;
  onClose: () => void;
};

export function ReportModal({ personaId, personaName, onClose }: Props) {
  const [reason, setReason] = useState<string>('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!reason) {
      toast.error('신고 사유를 선택해주세요');
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/personas/${personaId}/report`, {
        reason,
        description: description.trim() || null,
      });
      toast.success('신고가 접수되었습니다');
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          toast.error('이미 신고한 페르소나입니다');
          onClose();
          return;
        }
        if (err.status === 400) {
          toast.error(err.message);
          onClose();
          return;
        }
      }
      toast.error('신고 접수에 실패했습니다');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-bg-surface rounded-2xl border border-border w-full max-w-[420px] mx-4 p-6">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-text-muted hover:text-text bg-transparent border-none cursor-pointer"
        >
          <X size={20} />
        </button>

        <h2 className="text-lg font-semibold text-text mb-1">페르소나 신고</h2>
        <p className="text-sm text-text-secondary mb-5">
          &ldquo;{personaName}&rdquo;을(를) 신고합니다
        </p>

        <div className="flex flex-col gap-2 mb-4">
          {REASONS.map((r) => (
            <label
              key={r.value}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-colors ${
                reason === r.value
                  ? 'border-primary bg-primary/10'
                  : 'border-border hover:border-primary/50'
              }`}
            >
              <input
                type="radio"
                name="reason"
                value={r.value}
                checked={reason === r.value}
                onChange={(e) => setReason(e.target.value)}
                className="accent-primary"
              />
              <span className="text-sm text-text">{r.label}</span>
            </label>
          ))}
        </div>

        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="상세 사유를 입력해주세요 (선택)"
          maxLength={1000}
          rows={3}
          className="input w-full mb-4 resize-none text-sm"
        />

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm border border-border bg-transparent text-text-secondary cursor-pointer hover:bg-bg-hover transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={!reason || submitting}
            className={`px-4 py-2 rounded-lg text-sm border-none text-white font-medium transition-colors ${
              !reason || submitting
                ? 'bg-danger/50 cursor-not-allowed'
                : 'bg-danger cursor-pointer hover:bg-danger/90'
            }`}
          >
            {submitting ? '처리 중...' : '신고하기'}
          </button>
        </div>
      </div>
    </div>
  );
}
