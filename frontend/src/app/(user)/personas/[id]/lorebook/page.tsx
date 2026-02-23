'use client';

import { useParams } from 'next/navigation';
import { LorebookEditor } from '@/components/persona/LorebookEditor';

export default function LorebookPage() {
  const params = useParams();

  return (
    <div className="max-w-[720px] mx-auto py-6 px-4">
      <h1 className="m-0 mb-1 text-2xl text-text">로어북 관리</h1>
      <p className="text-text-secondary text-sm mb-6">
        페르소나의 세계관, 배경, 캐릭터 설정을 정의하세요.
      </p>
      <LorebookEditor personaId={params.id as string} />
    </div>
  );
}
