/** 사용자 사이드바. 모바일에서는 드로어, 데스크톱에서는 고정 사이드바. */
'use client';

import { memo, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  UserCircle,
  User,
  Swords,
  Images,
  Trophy,
  ShieldCheck,
} from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';

type MenuItem = { href: string; label: string; icon: typeof Swords };

const PLATFORM_ITEMS: MenuItem[] = [
  { href: '/debate', label: 'AI 토론', icon: Swords },
  { href: '/debate/gallery', label: '에이전트 갤러리', icon: Images },
  { href: '/debate/tournaments', label: '토너먼트', icon: Trophy },
];

const ACCOUNT_ITEMS: MenuItem[] = [
  { href: '/mypage', label: '마이페이지', icon: UserCircle },
];

function GroupLabel({ label }: { label: string }) {
  return (
    <span className="text-[11px] text-text-muted uppercase font-semibold px-5 pt-4 pb-1 block">
      {label}
    </span>
  );
}

function NavItem({
  item,
  active,
  onClick,
}: {
  item: MenuItem;
  active: boolean;
  onClick?: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onClick}
      className={`flex items-center gap-2.5 px-5 py-2.5 no-underline text-sm transition-colors duration-200 ${
        active
          ? 'text-primary bg-primary/10 border-r-[3px] border-primary font-semibold'
          : 'text-text-secondary hover:text-text hover:bg-bg-hover'
      }`}
    >
      <Icon size={20} />
      <span className="flex-1">{item.label}</span>
    </Link>
  );
}

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
    if (href === '/mypage') return pathname.startsWith('/mypage');
    // /debate는 갤러리·토너먼트 전용 메뉴가 있으므로 해당 하위 경로에선 비활성
    if (href === '/debate') {
      return (
        pathname === '/debate' ||
        (pathname.startsWith('/debate/') &&
          !pathname.startsWith('/debate/gallery') &&
          !pathname.startsWith('/debate/tournaments'))
      );
    }
    return pathname === href || pathname.startsWith(href + '/');
  };

  const visiblePlatformItems = PLATFORM_ITEMS;
  const visibleAccountItems = ACCOUNT_ITEMS;

  return (
    <>
      {/* 모바일 백드롭 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-[79] md:hidden"
          onClick={closeSidebar}
        />
      )}

      <aside
        className={`w-[220px] bg-bg-surface border-r border-border flex flex-col
          fixed top-0 left-0 h-full z-[80] transition-transform duration-250 ease-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:z-auto md:min-h-screen`}
      >
        <div className="px-5 py-5 border-b border-border">
          <Link href="/debate" className="text-text no-underline text-base font-bold block">
            AI 토론 플랫폼
          </Link>
          <span className="text-[11px] text-primary font-semibold uppercase tracking-wide">
            AI Debate
          </span>
        </div>

        <nav className="flex-1 flex flex-col py-1 overflow-y-auto">
          <GroupLabel label="플랫폼" />
          {visiblePlatformItems.map((item) => (
            <NavItem key={item.href} item={item} active={isActive(item.href)} onClick={closeSidebar} />
          ))}

          <GroupLabel label="내 계정" />
          {visibleAccountItems.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              active={isActive(item.href)}
              onClick={closeSidebar}
            />
          ))}
        </nav>

        {isAdmin() && (
          <div className="px-3 py-2 border-t border-border">
            <Link
              href="/admin"
              onClick={closeSidebar}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-amber-600 dark:text-amber-400 hover:bg-amber-500/10 transition-colors no-underline font-medium"
            >
              <ShieldCheck size={16} />
              <span>관리자 페이지</span>
            </Link>
          </div>
        )}

        <div className="px-5 py-4 border-t border-border">
          {user && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary flex-shrink-0">
                  <User size={16} />
                </div>
                <span className="text-sm text-text truncate">{user.nickname}</span>
              </div>
              <button
                onClick={handleLogout}
                className="text-xs text-text-muted hover:text-danger bg-transparent border-none cursor-pointer"
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
