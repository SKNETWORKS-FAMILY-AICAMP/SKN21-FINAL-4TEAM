import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore } from './chatStore';

describe('useChatStore', () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], isStreaming: false });
  });

  it('should start with empty messages', () => {
    expect(useChatStore.getState().messages).toEqual([]);
  });

  it('should start with isStreaming false', () => {
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it('should add a message', () => {
    useChatStore.getState().addMessage({
      role: 'user',
      content: '안녕하세요',
    });
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0].content).toBe('안녕하세요');
  });

  it('should add multiple messages in order', () => {
    useChatStore.getState().addMessage({ role: 'user', content: '첫번째' });
    useChatStore.getState().addMessage({ role: 'assistant', content: '두번째' });
    expect(useChatStore.getState().messages).toHaveLength(2);
    expect(useChatStore.getState().messages[0].content).toBe('첫번째');
    expect(useChatStore.getState().messages[1].content).toBe('두번째');
  });

  it('should append chunk to last message', () => {
    useChatStore.getState().addMessage({ role: 'assistant', content: '안녕' });
    useChatStore.getState().appendToLastMessage('하세요');
    expect(useChatStore.getState().messages[0].content).toBe('안녕하세요');
  });

  it('should handle appendToLastMessage with empty messages', () => {
    useChatStore.getState().appendToLastMessage('chunk');
    expect(useChatStore.getState().messages).toHaveLength(0);
  });

  it('should set streaming state', () => {
    useChatStore.getState().setStreaming(true);
    expect(useChatStore.getState().isStreaming).toBe(true);
    useChatStore.getState().setStreaming(false);
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it('should clear all messages', () => {
    useChatStore.getState().addMessage({ role: 'user', content: 'test' });
    useChatStore.getState().addMessage({ role: 'assistant', content: 'response' });
    useChatStore.getState().clearMessages();
    expect(useChatStore.getState().messages).toEqual([]);
  });

  it('should preserve emotionSignal when adding message', () => {
    const emotion = { label: '행복', intensity: 0.9, confidence: 0.85 };
    useChatStore.getState().addMessage({
      role: 'assistant',
      content: '기쁜 응답',
      emotionSignal: emotion,
    });
    expect(useChatStore.getState().messages[0].emotionSignal).toEqual(emotion);
  });
});
