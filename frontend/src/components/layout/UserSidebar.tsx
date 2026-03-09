/** 사용자 사이드바. 모바일에서는 드로어, 데스크톱에서는 고정 사이드바. */
'use client';

import { memo, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Home,
  MessageSquare,
  PenSquare,
  Users,
  UserCircle,
  User,
  Heart,
  Bell,
  HeartHandshake,
  MessageCircle,
  ClipboardList,
  Swords,
  Images,
  Trophy,
  ShieldCheck,
  Sun,
  Moon,
} from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';
import { useFeatureFlagStore } from '@/stores/featureFlagStore';
import { useNotificationStore } from '@/stores/notificationStore';
import { useThemeStore } from '@/stores/themeStore';
import { CreditBadge } from '@/components/credits/CreditBadge';

type MenuItem = { href: string; label: string; icon: typeof MessageSquare; flagKey?: string };

const PLATFORM_ITEMS: MenuItem[] = [
  { href: '/personas', label: '챗봇 탐색', icon: Home, flagKey: 'personas' },
  { href: '/sessions', label: '내 대화', icon: MessageSquare, flagKey: 'chat' },
  { href: '/personas/create', label: '챗봇 만들기', icon: PenSquare, flagKey: 'personas' },
  { href: '/favorites', label: '즐겨찾기', icon: Heart, flagKey: 'favorites' },
  { href: '/relationships', label: '관계도', icon: HeartHandshake, flagKey: 'relationships' },
  { href: '/community', label: '캐릭터 피드', icon: Users, flagKey: 'community' },
  { href: '/character-chats', label: '캐릭터 대화', icon: MessageCircle, flagKey: 'character_chats' },
  { href: '/pending-posts', label: '승인 대기', icon: ClipboardList, flagKey: 'pending_posts' },
  { href: '/debate', label: 'AI 토론', icon: Swords, flagKey: 'debate' },
  { href: '/debate/gallery', label: '에이전트 갤러리', icon: Images, flagKey: 'debate_gallery' },
  { href: '/debate/tournaments', label: '토너먼트', icon: Trophy, flagKey: 'debate_tournaments' },
];

const ACCOUNT_ITEMS: MenuItem[] = [
  { href: '/mypage', label: '마이페이지', icon: UserCircle, flagKey: 'mypage' },
  { href: '/notifications', label: '알림', icon: Bell, flagKey: 'notifications' },
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
  badge,
}: {
  item: MenuItem;
  active: boolean;
  onClick?: () => void;
  badge?: number;
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
      {badge != null && badge > 0 && (
        <span className="min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center px-1">
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </Link>
  );
}
export const UserSidebar = memo(function UserSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isAdmin } = useUserStore();
  const { sidebarOpen, closeSidebar } = useUIStore();
  const { isEnabled } = useFeatureFlagStore();
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const { theme, toggleTheme } = useThemeStore();

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
    if (href === '/personas') return pathname === '/personas';
    if (href === '/notifications') return pathname.startsWith('/notifications');
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
        className={`w-[180px] bg-bg-surface border-r border-border flex flex-col
          fixed top-0 left-0 h-full z-[80] transition-transform duration-250 ease-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:z-auto md:min-h-screen`}
      >
        <div className="px-5 py-5 border-b border-border">
          <Link href="/personas" className="text-text no-underline text-base font-bold block">
            Nemo
          </Link>
          <span className="text-[11px] text-nemo font-semibold uppercase tracking-wide">
            AI Debate
          </span>
          <div className="mt-2">
            <CreditBadge />
          </div>
        </div>

        <nav className="flex-1 flex flex-col py-1 overflow-y-auto">
          <GroupLabel label="플랫폼" />
          {PLATFORM_ITEMS.map((item) => (
            <NavItem key={item.href} item={item} active={isActive(item.href)} onClick={closeSidebar} />
          ))}

          <GroupLabel label="내 계정" />
          {ACCOUNT_ITEMS.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              active={isActive(item.href)}
              onClick={closeSidebar}
              badge={item.href === '/notifications' ? unreadCount : undefined}
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

        {/* Theme Toggle + Logout */}
        <div className="px-3 py-4 flex flex-col gap-2 border-t border-border">
          <button
            onClick={toggleTheme}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm cursor-pointer border-none transition-all duration-200 bg-nemo/10 text-nemo hover:bg-nemo/20 w-full"
          >
            {theme === 'light' ? <Sun size={16} /> : <Moon size={16} />}
            <span className="font-medium">
              {theme === 'light' ? '라이트 모드' : '다크 모드'}
            </span>
          </button>
          {user && (
            <div className="flex items-center justify-between px-2 pt-2 border-t border-border">
              <span className="text-xs text-text-muted truncate">{user.nickname}</span>
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
