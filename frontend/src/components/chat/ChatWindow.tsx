/** 채팅 메시지 목록 표시. 메시지 액션 바, 브랜칭 탐색, 수정/재생성 지원. */
'use client';

import { memo, useEffect, useRef, useState } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { MessageActions } from './MessageActions';
import { ScrollToTop } from '@/components/ui/ScrollToTop';

type Props = {
  sessionId: string;
  personaName?: string;
  onRegenerate?: (messageId: number) => void;
  onEdit?: (messageId: number, content: string) => void;
};

export const ChatWindow = memo(function ChatWindow({ sessionId, personaName, onRegenerate, onEdit }: Props) {
  const { messages, isStreaming } = useChatStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');

  // 바닥 감지: IntersectionObserver로 사용자가 바닥 근처에 있는지 추적
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !bottomRef.current) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        isNearBottomRef.current = entry.isIntersecting;
      },
      { root: container, threshold: 0, rootMargin: '0px 0px 100px 0px' },
    );

    observer.observe(bottomRef.current);
    return () => observer.disconnect();
  }, []);

  // 스마트 자동 스크롤: 사용자가 바닥 근처에 있을 때만 스크롤
  useEffect(() => {
    if (isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleEditStart = (id: number) => {
    const msg = messages.find((m) => m.id === id);
    if (msg) {
      setEditingId(id);
      setEditContent(msg.content);
    }
  };

  const handleEditSave = () => {
    if (editingId !== null && editContent.trim()) {
      onEdit?.(editingId, editContent.trim());
      setEditingId(null);
      setEditContent('');
    }
  };

  const handleEditCancel = () => {
    setEditingId(null);
    setEditContent('');
  };

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
      {messages.length === 0 && (
        <div className="text-center text-text-muted mt-10 text-sm">대화를 시작해보세요!</div>
      )}
      {messages.map((msg, i) => (
        <div
          key={msg.id ?? i}
          className={`group max-w-[90%] md:max-w-[80%] py-3 px-4 rounded-2xl text-sm leading-relaxed break-words whitespace-pre-wrap ${
            msg.role === 'user'
              ? 'self-end bg-primary text-white rounded-br-sm'
              : 'self-start bg-bg-surface text-text rounded-bl-sm shadow-bubble'
          }`}
        >
          <div className="text-[11px] font-semibold mb-1 opacity-70">
            {msg.role === 'user' ? '나' : personaName || '캐릭터'}
            {msg.isEdited && <span className="ml-1 text-text-muted">(수정됨)</span>}
          </div>
          {editingId === msg.id ? (
            <div className="flex flex-col gap-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="input text-sm p-2 min-h-[60px] resize-y"
                autoFocus
              />
              <div className="flex gap-2">
                <button onClick={handleEditSave} className="btn-primary text-xs py-1 px-3">
                  저장
                </button>
                <button onClick={handleEditCancel} className="btn-secondary text-xs py-1 px-3">
                  취소
                </button>
              </div>
            </div>
          ) : (
            <>
              <div>{msg.content}</div>
              {msg.emotionSignal && msg.emotionSignal.label && (
                <div className="text-[11px] mt-1.5 py-0.5 px-2 rounded-badge bg-bg-hover text-text-secondary inline-flex items-center gap-1">
                  <span>{msg.emotionSignal.label}</span>
                  {typeof msg.emotionSignal.intensity === 'number' && (
                    <span className="inline-block w-[32px] h-[4px] rounded-full bg-border overflow-hidden">
                      <span
                        className="block h-full rounded-full bg-primary"
                        style={{ width: `${Math.round(msg.emotionSignal.intensity * 100)}%` }}
                      />
                    </span>
                  )}
                </div>
              )}
              {msg.id && (
                <MessageActions
                  messageId={msg.id}
                  role={msg.role}
                  content={msg.content}
                  isStreaming={isStreaming}
                  onRegenerate={onRegenerate}
                  onEdit={handleEditStart}
                  siblingCount={msg.siblingIds?.length ?? 1}
                  siblingIndex={msg.siblingIndex ?? 0}
                />
              )}
            </>
          )}
        </div>
      ))}
      {isStreaming && messages[messages.length - 1]?.content === '' && (
        <div className="max-w-[90%] md:max-w-[80%] py-3 px-4 rounded-2xl text-sm self-start bg-bg-surface text-text rounded-bl-sm shadow-bubble opacity-60">
          <span>입력 중...</span>
        </div>
      )}
      <div ref={bottomRef} />
      <ScrollToTop scrollContainer={containerRef} />
    </div>
  );
});
