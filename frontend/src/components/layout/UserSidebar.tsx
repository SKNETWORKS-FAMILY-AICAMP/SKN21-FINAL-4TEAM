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
} from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';
import { useFeatureFlagStore } from '@/stores/featureFlagStore';
import { CreditBadge } from '@/components/credits/CreditBadge';

type MenuItem = { href: string; label: string; icon: typeof Home; flagKey?: string };

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

function NavItem({ item, active, onClick }: { item: MenuItem; active: boolean; onClick?: () => void }) {
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
      <span>{item.label}</span>
    </Link>
  );
}

export const UserSidebar = memo(function UserSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isAdmin } = useUserStore();
  const { sidebarOpen, closeSidebar } = useUIStore();
  const { isEnabled } = useFeatureFlagStore();

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

  const visiblePlatformItems = PLATFORM_ITEMS.filter(
    (item) => !item.flagKey || isEnabled(item.flagKey),
  );
  const visibleAccountItems = ACCOUNT_ITEMS.filter(
    (item) => !item.flagKey || isEnabled(item.flagKey),
  );

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
          <Link href="/personas" className="text-text no-underline text-base font-bold block">
            AI 토론 플랫폼
          </Link>
          <span className="text-[11px] text-primary font-semibold uppercase tracking-wide">
            AI Debate
          </span>
          <div className="mt-2">
            <CreditBadge />
          </div>
        </div>

        <nav className="flex-1 flex flex-col py-1 overflow-y-auto">
          <GroupLabel label="플랫폼" />
          {visiblePlatformItems.map((item) => (
            <NavItem key={item.href} item={item} active={isActive(item.href)} onClick={closeSidebar} />
          ))}

          <GroupLabel label="내 계정" />
          {visibleAccountItems.map((item) => (
            <NavItem key={item.href} item={item} active={isActive(item.href)} onClick={closeSidebar} />
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
