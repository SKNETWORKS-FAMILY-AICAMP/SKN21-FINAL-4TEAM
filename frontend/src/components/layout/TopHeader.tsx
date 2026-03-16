'use client';

import { Search, Sun, Moon } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';
import { NotificationBell } from '@/components/layout/NotificationBell';

export function TopHeader() {
  const { user } = useUserStore();
  const { toggleSidebar, theme, toggleTheme } = useUIStore();

  const initial = user?.nickname?.[0]?.toUpperCase() ?? 'U';

  return (
    <header className="h-14 border-b border-border bg-bg-surface flex items-center px-4 md:px-6 sticky top-0 z-30 relative">
      {/* 모바일 햄버거 */}
      <button
        className="md:hidden p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-bg-hover border-none bg-transparent cursor-pointer shrink-0"
        onClick={toggleSidebar}
        aria-label="메뉴 열기"
      >
        <span className="block w-5 h-0.5 bg-current mb-1" />
        <span className="block w-5 h-0.5 bg-current mb-1" />
        <span className="block w-5 h-0.5 bg-current" />
      </button>

      {/* 중앙 검색바 */}
      <div className="absolute left-1/2 -translate-x-1/2 w-full max-w-md px-4">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
          <input
            type="text"
            placeholder="토픽, 에이전트 검색..."
            className="w-full bg-bg border border-border rounded-full pl-9 pr-4 py-2 text-sm text-text placeholder:text-text-muted outline-none focus:border-primary transition-colors"
          />
        </div>
      </div>

      {/* 우측 액션 */}
      <div className="flex items-center gap-2 ml-auto shrink-0">
        <button
          onClick={toggleTheme}
          className="w-8 h-8 rounded-full bg-bg border border-border flex items-center justify-center text-text-muted hover:text-text transition-colors cursor-pointer"
          aria-label="테마 변경"
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        {/* 알림 */}
        <NotificationBell />

        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white text-sm font-bold select-none cursor-pointer">
          {initial}
        </div>
      </div>
    </header>
  );
}
