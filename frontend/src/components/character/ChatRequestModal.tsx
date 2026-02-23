'use client';

import { useState, useEffect } from 'react';
import { X, MessageCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { useCharacterChatStore } from '@/stores/characterChatStore';

type Persona = {
  id: string;
  display_name: string;
  age_rating: string;
};

type Props = {
  responderPersonaId: string;
  responderName: string;
  open: boolean;
  onClose: () => void;
};

export function ChatRequestModal({ responderPersonaId, responderName, open, onClose }: Props) {
  const [myPersonas, setMyPersonas] = useState<Persona[]>([]);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>('');
  const [maxTurns, setMaxTurns] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { requestChat } = useCharacterChatStore();

  useEffect(() => {
    if (open) {
      api
        .get<Persona[]>('/personas?mine=true&limit=50')
        .then((data) => {
          setMyPersonas(data);
          if (data.length > 0) setSelectedPersonaId(data[0].id);
        })
        .catch(() => setMyPersonas([]));
    }
  }, [open]);

  if (!open) return null;

  const handleSubmit = async () => {
    if (!selectedPersonaId) return;
    setLoading(true);
    setError('');
    try {
      await requestChat(selectedPersonaId, responderPersonaId, maxTurns);
      onClose();
    } catch (err: any) {
      setError(err.message || '요청에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-bg-surface rounded-xl w-full max-w-md p-6 border border-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-text flex items-center gap-2">
            <MessageCircle size={20} className="text-primary" />
            1:1 대화 요청
          </h2>
          <button onClick={onClose} className="text-text-muted hover:text-text bg-transparent border-none cursor-pointer">
            <X size={20} />
          </button>
        </div>

        <p className="text-sm text-text-secondary mb-4">
          <strong>{responderName}</strong>에게 대화를 요청합니다.
        </p>

        {/* 내 캐릭터 선택 */}
        <label className="block text-sm font-semibold text-text mb-1">내 캐릭터 선택</label>
        <select
          value={selectedPersonaId}
          onChange={(e) => setSelectedPersonaId(e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm mb-3"
        >
          {myPersonas.map((p) => (
            <option key={p.id} value={p.id}>
              {p.display_name} [{p.age_rating}]
            </option>
          ))}
        </select>

        {myPersonas.length === 0 && (
          <p className="text-xs text-danger mb-3">캐릭터가 없습니다. 먼저 캐릭터를 만들어주세요.</p>
        )}

        {/* 턴 수 */}
        <label className="block text-sm font-semibold text-text mb-1">최대 턴 수</label>
        <input
          type="number"
          min={1}
          max={20}
          value={maxTurns}
          onChange={(e) => setMaxTurns(Number(e.target.value))}
          className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-sm mb-4"
        />

        {error && <p className="text-xs text-danger mb-3">{error}</p>}

        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold bg-bg-hover text-text-secondary border border-border cursor-pointer"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !selectedPersonaId}
            className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold bg-primary text-white border-none cursor-pointer disabled:opacity-50"
          >
            {loading ? '요청 중...' : '대화 요청'}
          </button>
        </div>
      </div>
    </div>
  );
}
