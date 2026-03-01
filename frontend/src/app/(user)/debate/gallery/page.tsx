'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { GalleryCard } from '@/components/debate/GalleryCard';
import type { GalleryEntry } from '@/components/debate/GalleryCard';

const SORT_OPTIONS = [
  { value: 'elo', label: 'ELO 순' },
  { value: 'wins', label: '승리 수' },
  { value: 'recent', label: '최신 순' },
];

export default function GalleryPage() {
  const [items, setItems] = useState<GalleryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [sort, setSort] = useState('elo');
  const [loading, setLoading] = useState(true);

  const fetchGallery = async (sortVal: string) => {
    setLoading(true);
    try {
      const data = await api.get<{ items: GalleryEntry[]; total: number }>(
        `/agents/gallery?sort=${sortVal}&limit=30`,
      );
      setItems(data.items);
      setTotal(data.total);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGallery(sort);
  }, [sort]);

  const handleClone = async (agentId: string, name: string) => {
    await api.post(`/agents/gallery/${agentId}/clone`, { name });
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-text">에이전트 갤러리</h1>
        <div className="flex gap-1">
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setSort(opt.value)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                sort === opt.value
                  ? 'bg-primary text-white'
                  : 'bg-bg-surface border border-border text-text-muted hover:text-text'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center text-text-muted py-12">로딩 중...</div>
      ) : items.length === 0 ? (
        <div className="text-center text-text-muted py-12">공개된 에이전트가 없습니다.</div>
      ) : (
        <>
          <p className="text-xs text-text-muted mb-4">총 {total}개</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((entry) => (
              <GalleryCard key={entry.id} entry={entry} onClone={handleClone} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
