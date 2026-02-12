'use client';

type Props = {
  personaId?: string;
  onSubmit: (data: unknown) => void;
};

export function PersonaForm({ personaId, onSubmit }: Props) {
  return (
    <form>
      {/* 캐릭터 이름, 성격, 말투, 시스템 프롬프트, Live2D 선택, 배경, 연령등급 */}
    </form>
  );
}
