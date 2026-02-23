'use client';

import { Bot, User } from 'lucide-react';

type Props = {
  type: 'user' | 'persona';
  displayName: string;
  size?: 'sm' | 'md';
};

export function PersonaAvatar({ type, displayName, size = 'md' }: Props) {
  const sizeClass = size === 'sm' ? 'w-7 h-7' : 'w-9 h-9';
  const iconSize = size === 'sm' ? 14 : 18;

  if (type === 'persona') {
    return (
      <div
        className={`${sizeClass} rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0`}
        title={displayName}
      >
        <Bot size={iconSize} className="text-primary" />
      </div>
    );
  }

  return (
    <div
      className={`${sizeClass} rounded-full bg-bg-hover flex items-center justify-center flex-shrink-0`}
      title={displayName}
    >
      <User size={iconSize} className="text-text-muted" />
    </div>
  );
}
