import { create } from 'zustand';

type Live2DState = {
  currentEmotion: string;
  modelPath: string | null;
  emotionMappings: Record<string, string>;
  setEmotion: (emotion: string) => void;
  setModel: (path: string, mappings: Record<string, string>) => void;
};

export const useLive2DStore = create<Live2DState>((set) => ({
  currentEmotion: 'neutral',
  modelPath: null,
  emotionMappings: {},
  setEmotion: (emotion) => set({ currentEmotion: emotion }),
  setModel: (path, mappings) => set({ modelPath: path, emotionMappings: mappings }),
}));
