import { create } from 'zustand';

type Message = {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  emotionSignal?: Record<string, unknown>;
  createdAt: string;
};

type ChatState = {
  messages: Message[];
  isStreaming: boolean;
  addMessage: (message: Message) => void;
  appendToLastMessage: (chunk: string) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;
};

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  appendToLastMessage: (chunk) =>
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (last) {
        messages[messages.length - 1] = { ...last, content: last.content + chunk };
      }
      return { messages };
    }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  clearMessages: () => set({ messages: [] }),
}));
