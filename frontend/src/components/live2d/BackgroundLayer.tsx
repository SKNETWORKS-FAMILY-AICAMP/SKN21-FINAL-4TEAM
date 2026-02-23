/** 채팅 화면 배경 이미지 레이어. 페르소나별 배경 URL을 표시한다. */
'use client';

import { memo } from 'react';

type Props = {
  imageUrl: string;
};

export const BackgroundLayer = memo(function BackgroundLayer({ imageUrl }: Props) {
  return (
    <div
      className="absolute inset-0 bg-cover bg-center bg-dark z-0"
      style={{ backgroundImage: imageUrl ? `url(${imageUrl})` : 'none' }}
    />
  );
});
