/** 스포일러 범위 설정 게이트. 채팅 시작 전 사용자에게 스포일러 허용 범위를 선택받는다. */
'use client';

import { useState } from 'react';

type Props = {
  webtoonId: string;
  onAccept: (maxEpisode: number) => void;
};

export function SpoilerGate({ webtoonId, onAccept }: Props) {
  const [maxEpisode, setMaxEpisode] = useState(1);

  return (
    <div className="modal-overlay">
      <div className="modal-content w-full max-w-[360px]">
        <h3 className="m-0 mb-2 text-lg">스포일러 범위 설정</h3>
        <p className="text-text-secondary text-sm mb-5">몇 화까지 스포일러를 허용하시겠습니까?</p>
        <div className="flex items-center justify-center gap-2 mb-5">
          <input
            type="number"
            min={1}
            value={maxEpisode}
            onChange={(e) => setMaxEpisode(Number(e.target.value))}
            className="w-20 py-2 px-3 border border-border-input rounded-lg text-base text-center bg-bg-input text-text"
          />
          <span className="text-sm text-text-secondary">화까지</span>
        </div>
        <button
          onClick={() => onAccept(maxEpisode)}
          className="py-2.5 px-8 border-none rounded-lg bg-primary text-white text-sm font-semibold cursor-pointer"
        >
          확인
        </button>
      </div>
    </div>
  );
}
