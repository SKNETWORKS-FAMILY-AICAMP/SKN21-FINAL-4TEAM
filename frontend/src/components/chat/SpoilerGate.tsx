'use client';

type Props = {
  webtoonId: string;
  onAccept: () => void;
};

export function SpoilerGate({ webtoonId, onAccept }: Props) {
  return (
    <div className="spoiler-gate">
      {/* 스포일러 범위 설정 UI */}
    </div>
  );
}
