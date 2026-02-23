/** Live2D 모델 로드 및 감정→모션 매핑 컨트롤러. 감정 신호에 따라 모션을 전환한다. */
'use client';

import { useEffect } from 'react';
import { useLive2DStore } from '@/stores/live2dStore';
import { api } from '@/lib/api';

type SessionDetail = {
  live2d_model_path: string | null;
  live2d_emotion_mappings: Record<string, string> | null;
};

type Props = {
  sessionId: string;
};

/**
 * 세션 정보에서 Live2D 모델 경로와 감정→모션 매핑을 로드하여 스토어에 설정.
 * 렌더링 없이 스토어 상태만 관리하는 컨트롤러 컴포넌트.
 */
export function Live2DController({ sessionId }: Props) {
  const { setModel } = useLive2DStore();

  useEffect(() => {
    api
      .get<SessionDetail>(`/chat/sessions/${sessionId}`)
      .then((detail) => {
        if (detail.live2d_model_path) {
          setModel(
            detail.live2d_model_path,
            detail.live2d_emotion_mappings ?? { neutral: 'idle' },
          );
        }
      })
      .catch(() => {});
  }, [sessionId, setModel]);

  return null;
}
