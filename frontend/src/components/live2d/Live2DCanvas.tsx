/** Live2D 캐릭터 렌더링 캔버스. PixiJS + pixi-live2d-display로 Cubism 4 모델을 표시. */
'use client';

import { useEffect, useRef, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display/cubism4';
import { useLive2DStore } from '@/stores/live2dStore';

// pixi-live2d-display가 PixiJS의 Ticker를 사용하도록 등록
// pixi.js와 pixi-live2d-display의 @pixi/ticker 버전 차이로 인한 타입 불일치 우회
(Live2DModel as { registerTicker: (ticker: unknown) => void }).registerTicker(PIXI.Ticker);

type Props = {
  modelPath: string;
  emotion?: string;
};

export function Live2DCanvas({ modelPath, emotion }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<PIXI.Application | null>(null);
  const modelRef = useRef<InstanceType<typeof Live2DModel> | null>(null);
  const { emotionMappings } = useLive2DStore();

  const triggerMotion = useCallback(
    (emotionName: string) => {
      const model = modelRef.current;
      if (!model) return;

      const motionGroup = emotionMappings[emotionName] ?? emotionMappings['neutral'] ?? 'idle';

      // pixi-live2d-display의 motion API: motion(group, index)
      // index를 지정하지 않으면 그룹 내 랜덤 모션 재생
      try {
        model.motion(motionGroup);
      } catch {
        // 모션 그룹이 없으면 무시 (모델에 따라 매핑 불일치 가능)
      }
    },
    [emotionMappings],
  );

  // 감정 변화 시 모션 트리거
  useEffect(() => {
    if (emotion) {
      triggerMotion(emotion);
    }
  }, [emotion, triggerMotion]);

  // PixiJS + Live2D 모델 초기화
  useEffect(() => {
    if (!containerRef.current || !modelPath) return;

    const container = containerRef.current;
    let destroyed = false;

    const initApp = async () => {
      // 기존 앱 정리
      if (appRef.current) {
        appRef.current.destroy(true);
        appRef.current = null;
        modelRef.current = null;
      }

      const app = new PIXI.Application({
        backgroundAlpha: 0,
        resizeTo: container,
        antialias: true,
      });

      if (destroyed) {
        app.destroy(true);
        return;
      }

      container.appendChild(app.view as HTMLCanvasElement);
      appRef.current = app;

      try {
        const model = await Live2DModel.from(modelPath, {
          autoInteract: false,
          autoUpdate: true,
        });

        if (destroyed) {
          model.destroy();
          return;
        }

        modelRef.current = model;

        // 모델을 화면 중앙 하단에 배치
        const scale = Math.min(app.screen.width / model.width, app.screen.height / model.height) * 0.8;
        model.scale.set(scale);
        model.x = (app.screen.width - model.width * scale) / 2;
        model.y = app.screen.height - model.height * scale;

        app.stage.addChild(model as unknown as PIXI.DisplayObject);

        // 초기 idle 모션
        try {
          model.motion('idle');
        } catch {
          // idle 모션 그룹이 없는 모델도 있음
        }
      } catch (err) {
        // 모델 로딩 실패 시 플레이스홀더 표시
        if (!destroyed) {
          const text = new PIXI.Text('Live2D 모델 로딩 실패', {
            fill: '#ffffff',
            fontSize: 14,
            fontFamily: 'Pretendard, sans-serif',
          });
          text.anchor.set(0.5);
          text.x = app.screen.width / 2;
          text.y = app.screen.height / 2;
          app.stage.addChild(text);
        }
      }
    };

    initApp();

    return () => {
      destroyed = true;
      if (modelRef.current) {
        modelRef.current.destroy();
        modelRef.current = null;
      }
      if (appRef.current) {
        appRef.current.destroy(true);
        appRef.current = null;
      }
    };
  }, [modelPath]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none z-[1]"
    />
  );
}
