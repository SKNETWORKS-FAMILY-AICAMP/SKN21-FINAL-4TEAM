'use client';

type Props = {
  modelPath: string;
  emotion?: string;
};

export function Live2DCanvas({ modelPath, emotion }: Props) {
  return (
    <div className="live2d-canvas">
      {/* PixiJS + pixi-live2d-display 렌더링 */}
    </div>
  );
}
