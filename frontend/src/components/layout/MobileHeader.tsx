'use client';

import { Menu } from 'lucide-react';
import { useUIStore } from '@/stores/uiStore';

export function MobileHeader() {
  const { toggleSidebar } = useUIStore();
  return (
    <div className="md:hidden flex items-center gap-3 px-4 py-3 bg-bg-surface border-b border-border sticky top-0 z-[10]">
      <button
        onClick={toggleSidebar}
        className="p-1.5 rounded-lg bg-transparent border-none text-text cursor-pointer hover:bg-bg-hover transition-colors"
        aria-label="메뉴 열기"
      >
        <Menu size={22} />
      </button>
      <span className="text-sm font-bold text-text">Webtoon Chat</span>
    </div>
  );
}
