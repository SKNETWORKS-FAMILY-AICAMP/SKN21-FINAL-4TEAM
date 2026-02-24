/** 채팅 화면 배경 이미지 레이어. 페르소나별 배경 URL을 표시한다. */
'use client';

import { memo, useState } from 'react';

// 이미지 로드 실패 시 CSS 그라디언트 폴백
const FALLBACK_GRADIENT = 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%)';

type Props = {
  imageUrl: string;
};

export const BackgroundLayer = memo(function BackgroundLayer({ imageUrl }: Props) {
  const [failed, setFailed] = useState(false);

  const bgStyle =
    imageUrl && !failed
      ? { backgroundImage: `url(${imageUrl})` }
      : { backgroundImage: FALLBACK_GRADIENT };

  return (
    <>
      <div className="absolute inset-0 bg-cover bg-center z-0" style={bgStyle} />
      {/* 이미지 로드 오류 감지용 hidden img */}
      {imageUrl && !failed && (
        <img
          src={imageUrl}
          alt=""
          className="hidden"
          onError={() => setFailed(true)}
        />
      )}
    </>
  );
});
