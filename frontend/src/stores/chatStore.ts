/**
 * 채팅 상태 스토어. SSE 스트리밍, 메시지 브랜칭, 수정, 재생성 지원.
 */
import { create } from 'zustand';

type Message = {
  id?: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  emotionSignal?: { label: string; intensity: number; confidence: number } | null;
  createdAt?: string;
  parentId?: number | null;
  isActive?: boolean;
  isEdited?: boolean;
  siblingIds?: number[];
  siblingIndex?: number;
};

type ChatState = {
  messages: Message[];
  isStreaming: boolean;
  addMessage: (message: Omit<Message, 'createdAt'>) => void;
  appendToLastMessage: (chunk: string) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;
  updateMessage: (id: number, content: string) => void;
  replaceMessage: (id: number, newMessage: Message) => void;
  setMessages: (messages: Message[]) => void;
};

let _nextId = 0;

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        { ...message, id: message.id ?? Date.now() * 1000 + ++_nextId, createdAt: new Date().toISOString() },
      ],
    })),
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
  updateMessage: (id, content) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content, isEdited: true } : m,
      ),
    })),
  replaceMessage: (id, newMessage) =>
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? { ...newMessage } : m)),
    })),
  setMessages: (messages) => set({ messages }),
}));
