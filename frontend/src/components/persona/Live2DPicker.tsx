'use client';

type Props = {
  selectedModelId?: string;
  onSelect: (modelId: string) => void;
};

export function Live2DPicker({ selectedModelId, onSelect }: Props) {
  return (
    <div className="live2d-picker">
      {/* Live2D 모델 선택 그리드 (썸네일 + 이름) */}
    </div>
  );
}
