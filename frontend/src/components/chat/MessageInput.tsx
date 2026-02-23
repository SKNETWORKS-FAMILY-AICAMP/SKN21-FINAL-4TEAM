/** 채팅 입력창. Enter 전송, Shift+Enter 줄바꿈, 스트리밍 중 비활성화. */
'use client';

import { memo, useCallback, useState, useRef } from 'react';

type Props = {
  onSend: (message: string) => void;
  disabled?: boolean;
  modelSelector?: React.ReactNode;
};

export const MessageInput = memo(function MessageInput({ onSend, disabled = false, modelSelector }: Props) {
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      const trimmed = text.trim();
      if (!trimmed || disabled) return;
      onSend(trimmed);
      setText('');
      inputRef.current?.focus();
    },
    [text, disabled, onSend],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2 py-2 md:py-3 px-3 md:px-4 border-t border-border bg-bg-surface">
      {modelSelector}
      <textarea
        ref={inputRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="메시지를 입력하세요..."
        disabled={disabled}
        rows={1}
        className="flex-1 py-2.5 px-3.5 border border-border-input rounded-[20px] text-sm resize-none outline-none font-[inherit] leading-[1.4] bg-bg-input text-text"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className={`py-2 px-3.5 md:py-2.5 md:px-5 border-none rounded-[20px] bg-primary text-white text-sm font-semibold cursor-pointer whitespace-nowrap ${
          disabled || !text.trim() ? 'opacity-50' : 'opacity-100'
        }`}
      >
        전송
      </button>
    </form>
  );
});
