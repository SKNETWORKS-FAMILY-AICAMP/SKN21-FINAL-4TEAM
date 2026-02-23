'use client';

import { useParams, useRouter } from 'next/navigation';
import { Download } from 'lucide-react';
import { PersonaForm } from '@/components/persona/PersonaForm';
import { PersonaLoungeSettings } from '@/components/community/PersonaLoungeSettings';
import { ActivityReport } from '@/components/community/ActivityReport';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

export default function EditPersonaPage() {
  const params = useParams();
  const router = useRouter();

  const handleSubmit = async (data: Record<string, unknown>) => {
    try {
      const body = {
        ...data,
        catchphrases:
          typeof data.catchphrases === 'string'
            ? (data.catchphrases as string).split('\n').filter(Boolean)
            : [],
        style_rules:
          typeof data.style_rules === 'string' && data.style_rules
            ? { rules: (data.style_rules as string).split('\n').filter(Boolean) }
            : {},
        category: data.category || null,
      };
      await api.put(`/personas/${params.id as string}`, body);
      router.push('/personas');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '수정에 실패했습니다';
      alert(message);
    }
  };

  const personaId = params.id as string;

  const handleExport = async () => {
    try {
      const card = await api.get<Record<string, unknown>>(`/character-cards/export/${personaId}`);
      const blob = new Blob([JSON.stringify(card, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${card.name || 'character'}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('캐릭터 카드를 다운로드했습니다');
    } catch {
      toast.error('내보내기에 실패했습니다');
    }
  };

  return (
    <div className="max-w-[640px] mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-2">
        <h1 className="page-title m-0">페르소나 수정</h1>
        <button
          onClick={handleExport}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-border bg-bg-surface text-text-secondary hover:border-primary/50 hover:text-primary transition-colors duration-150"
        >
          <Download size={14} />
          내보내기
        </button>
      </div>
      <PersonaForm personaId={personaId} onSubmit={handleSubmit} />

      {/* 캐릭터 라운지 설정 */}
      <div className="mt-8 space-y-4">
        <h2 className="text-base font-semibold text-gray-200">캐릭터 라운지</h2>
        <PersonaLoungeSettings personaId={personaId} />
        <ActivityReport personaId={personaId} />
      </div>
    </div>
  );
}
