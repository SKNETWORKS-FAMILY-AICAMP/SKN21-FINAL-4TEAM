'use client';

import { useState } from 'react';
import { X } from 'lucide-react';

type TagChipsProps = {
  tags: string[];
  editable?: boolean;
  onChange?: (tags: string[]) => void;
  maxTags?: number;
};

export function TagChips({ tags, editable = false, onChange, maxTags = 10 }: TagChipsProps) {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === 'Enter' || e.key === ',') && inputValue.trim()) {
      e.preventDefault();
      const newTag = inputValue.trim().slice(0, 30);
      if (!tags.includes(newTag) && tags.length < maxTags) {
        onChange?.([...tags, newTag]);
      }
      setInputValue('');
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      onChange?.(tags.slice(0, -1));
    }
  };

  const removeTag = (index: number) => {
    onChange?.(tags.filter((_, i) => i !== index));
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tags.map((tag, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium"
        >
          #{tag}
          {editable && (
            <button
              onClick={() => removeTag(i)}
              className="p-0 border-none bg-transparent text-primary/60 hover:text-primary cursor-pointer"
            >
              <X size={10} />
            </button>
          )}
        </span>
      ))}
      {editable && tags.length < maxTags && (
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="태그 입력..."
          className="bg-transparent border-none outline-none text-xs text-text w-[80px] py-0.5"
        />
      )}
    </div>
  );
}
