/** Live2D 모델 선택 피커. 사용 가능한 모델 목록을 그리드로 표시, 선택 시 콜백. */
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type Live2DModel = {
  id: string;
  name: string;
  thumbnail_url: string;
};

type Props = {
  selectedModelId?: string;
  onSelect: (modelId: string) => void;
};

export function Live2DPicker({ selectedModelId, onSelect }: Props) {
  const [models, setModels] = useState<Live2DModel[]>([]);

  useEffect(() => {
    api.get<Live2DModel[]>('/personas/live2d-models').then(setModels).catch(() => {});
  }, []);

  if (models.length === 0) {
    return <div className="text-center text-text-muted p-5 text-sm">사용 가능한 Live2D 모델이 없습니다</div>;
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3">
      {models.map((model) => (
        <div
          key={model.id}
          onClick={() => onSelect(model.id)}
          className={`border-2 rounded-xl p-2 cursor-pointer text-center transition-colors duration-200 ${
            selectedModelId === model.id
              ? 'border-primary bg-primary/10'
              : 'border-border'
          }`}
        >
          <div
            className="w-full aspect-square rounded-lg bg-bg bg-cover bg-center"
            style={{
              backgroundImage: model.thumbnail_url ? `url(${model.thumbnail_url})` : 'none',
            }}
          />
          <div className="mt-2 text-[13px] font-medium">{model.name}</div>
        </div>
      ))}
    </div>
  );
}
