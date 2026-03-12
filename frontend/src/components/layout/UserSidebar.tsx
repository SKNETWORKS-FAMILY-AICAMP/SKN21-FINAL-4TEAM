/** 사용자 사이드바. 모바일에서는 드로어, 데스크톱에서는 고정 사이드바. */
'use client';

import { memo, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { MessageSquare, Trophy, Bot, User, ShieldCheck } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';

type MenuItem = { href: string; label: string; icon: typeof MessageSquare };

const NAV_ITEMS: MenuItem[] = [
  { href: '/debate', label: 'Debate', icon: MessageSquare },
  { href: '/debate/ranking', label: 'Ranking', icon: Trophy },
  { href: '/debate/agents', label: 'Agents', icon: Bot },
  { href: '/mypage', label: 'Profile', icon: User },
];

export const UserSidebar = memo(function UserSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isAdmin } = useUserStore();
  const { sidebarOpen, closeSidebar } = useUIStore();

  // 경로 변경 시 모바일 사이드바 자동 닫기
  useEffect(() => {
    closeSidebar();
  }, [pathname, closeSidebar]);

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  const isActive = (href: string) => {
    if (href === '/debate') {
      return (
        pathname === '/debate' ||
        (pathname.startsWith('/debate/') &&
          !pathname.startsWith('/debate/ranking') &&
          !pathname.startsWith('/debate/agents') &&
          !pathname.startsWith('/debate/gallery') &&
          !pathname.startsWith('/debate/tournaments'))
      );
    }
    return pathname === href || pathname.startsWith(href + '/');
  };

  return (
    <>
      {/* 모바일 백드롭 */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-[79] md:hidden" onClick={closeSidebar} />
      )}

      <aside
        className={`w-[220px] bg-bg-surface border-r border-border flex flex-col
          fixed top-0 left-0 h-full z-[80] transition-transform duration-250 ease-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:z-auto md:min-h-screen`}
      >
        {/* 로고 */}
        <div className="px-5 py-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
              <MessageSquare size={18} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-text leading-tight m-0">AI Arena</p>
              <p className="text-[10px] text-primary font-semibold uppercase tracking-wider m-0">
                Season 3
              </p>
            </div>
          </div>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 flex flex-col py-4 gap-1 px-3 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={closeSidebar}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl no-underline text-sm font-medium transition-all duration-200
                  ${
                    active
                      ? 'bg-primary text-white shadow-sm'
                      : 'text-text-secondary hover:text-text hover:bg-bg-hover'
                  }`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* 관리자 링크 */}
        {isAdmin() && (
          <div className="px-3 py-2 border-t border-border">
            <Link
              href="/admin"
              onClick={closeSidebar}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm text-amber-400 hover:bg-amber-500/10 transition-colors no-underline font-medium"
            >
              <ShieldCheck size={16} />
              <span>관리자</span>
            </Link>
          </div>
        )}

        {/* 유저 정보 */}
        <div className="px-4 py-4 border-t border-border">
          {user && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-sm font-bold flex-shrink-0">
                  {user.nickname[0]?.toUpperCase()}
                </div>
                <span className="text-sm text-text truncate">{user.nickname}</span>
              </div>
              <button
                onClick={handleLogout}
                className="text-xs text-text-muted hover:text-danger bg-transparent border-none cursor-pointer shrink-0"
              >
                로그아웃
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
});
