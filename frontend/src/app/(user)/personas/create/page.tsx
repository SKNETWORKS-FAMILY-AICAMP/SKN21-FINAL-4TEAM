'use client';

import { useRouter } from 'next/navigation';
import { PersonaForm } from '@/components/persona/PersonaForm';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

export default function CreatePersonaPage() {
  const router = useRouter();

  const handleSubmit = async (data: Record<string, unknown>) => {
    try {
      const body = {
        ...data,
        persona_key: (data.display_name as string).toLowerCase().replace(/[^a-z0-9가-힣]/g, '_').slice(0, 50) + '_' + Date.now(),
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
      const persona = await api.post<{ id: string }>('/personas', body);
      router.push(`/personas/${persona.id}/lorebook`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '생성에 실패했습니다';
      toast.error(message);
    }
  };

  return (
    <div className="max-w-[640px] mx-auto py-6 px-4">
      <h1 className="page-title">새 페르소나 생성</h1>
      <PersonaForm onSubmit={handleSubmit} />
    </div>
  );
}
