/** 사용자 사이드바. 모바일에서는 드로어, 데스크톱에서는 고정 사이드바. */
'use client';

import { memo, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import {
  Swords,
  MessageSquare,
  Trophy,
  UserCircle,
  BookOpen,
  List,
  Users,
  ShieldCheck,
  LogOut,
  X,
  Menu,
  LayoutGrid,
  Home,
} from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';

type MenuItem = { href: string; label: string; icon: typeof Swords };

const PLATFORM_ITEMS: MenuItem[] = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/debate', label: 'Debate', icon: MessageSquare },
  { href: '/debate/ranking', label: 'Ranking', icon: Trophy },
  { href: '/debate/gallery', label: 'Gallery', icon: LayoutGrid },
  { href: '/community', label: 'Community', icon: Users },
];

const MY_ITEMS: MenuItem[] = [
  { href: '/mypage', label: '마이페이지', icon: UserCircle },
];

type TopicCountResponse = { items: unknown[]; total: number };

export const UserSidebar = memo(function UserSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout, isAdmin } = useUserStore();
  const { sidebarOpen, closeSidebar, sidebarCollapsed, toggleSidebarCollapsed } = useUIStore();

  const [liveCount, setLiveCount] = useState<number | null>(null);
  const [scheduledCount, setScheduledCount] = useState<number | null>(null);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  useEffect(() => {
    closeSidebar();
  }, [pathname, closeSidebar]);

  useEffect(() => {
    async function fetchStats() {
      try {
        const [liveData, scheduledData] = await Promise.all([
          api.get<TopicCountResponse>('/topics?status=in_progress&page=1&page_size=1'),
          api.get<TopicCountResponse>('/topics?status=scheduled&page=1&page_size=1'),
        ]);
        setLiveCount(liveData.total);
        setScheduledCount(scheduledData.total);
      } catch {
        // 통계 로드 실패는 조용히 무시
      }
    }

    fetchStats();
    const interval = setInterval(fetchStats, 30_000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    setShowLogoutConfirm(true);
  };

  const confirmLogout = () => {
    logout();
    router.push('/login');
  };

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
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

  const sidebarWidth = sidebarCollapsed ? 'w-[70px]' : 'w-[200px]';

  return (
    <>
      {/* 모바일 백드롭 */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-[79] md:hidden" onClick={closeSidebar} />
      )}

      <aside
        className={`${sidebarWidth} bg-white border-r-2 border-black flex flex-col
          fixed top-0 left-0 h-full z-[80] transition-all duration-300 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:sticky md:translate-x-0 md:min-h-screen`}
      >
        {/* 로고 헤더 */}
        <div className={`px-4 py-6 flex items-center ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}>
          {!sidebarCollapsed ? (
            <Link href="/" className="flex-1 no-underline group">
              <p className="text-xl font-bold text-black m-0 leading-tight tracking-tight group-hover:text-primary transition-colors">NEMo</p>
              <p className="text-[10px] font-black m-0 text-primary tracking-widest">AI DEBATE</p>
            </Link>
          ) : (
            <Link href="/" className="no-underline group">
              <div className="w-8 h-8 bg-black text-white rounded-lg flex items-center justify-center font-black text-xl hover:bg-primary transition-colors">
                N
              </div>
            </Link>
          )}
          <button
            onClick={toggleSidebarCollapsed}
            className={`p-2 rounded-lg bg-transparent border-none text-black hover:bg-gray-100 cursor-pointer hidden md:flex items-center justify-center transition-colors`}
            aria-label="사이드바 토글"
          >
            <Menu size={20} strokeWidth={2.5} />
          </button>

          <button
            onClick={closeSidebar}
            className="p-1 rounded-lg bg-transparent border-none text-text-muted hover:text-text cursor-pointer md:hidden"
          >
            <X size={18} />
          </button>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 flex flex-col py-2 px-3 gap-6 overflow-y-auto scrollbar-hide">
          {/* 플랫폼 */}
          <div>
            {!sidebarCollapsed && (
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest px-3 mb-3">
                플랫폼
              </p>
            )}
            <div className={`flex flex-col gap-1.5 ${sidebarCollapsed ? 'items-center' : ''}`}>
              {PLATFORM_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 no-underline text-sm font-bold transition-all duration-150
                      ${sidebarCollapsed ? 'justify-center p-2.5 rounded-xl' : 'px-4 py-2.5 rounded-xl'}
                      ${
                        active
                          ? 'bg-primary text-white brutal-border brutal-shadow-sm'
                          : 'text-gray-500 hover:text-black hover:bg-gray-50'
                      }`}
                    title={sidebarCollapsed ? item.label : undefined}
                  >
                    <Icon size={18} strokeWidth={active ? 2.5 : 2} />
                    {!sidebarCollapsed && <span>{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* 내 계정 */}
          <div>
            {!sidebarCollapsed && (
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest px-3 mb-3">
                내 계정
              </p>
            )}
            <div className={`flex flex-col gap-1.5 ${sidebarCollapsed ? 'items-center' : ''}`}>
              {MY_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 no-underline text-sm font-bold transition-all duration-150
                      ${sidebarCollapsed ? 'justify-center p-2.5 rounded-xl' : 'px-4 py-2.5 rounded-xl'}
                      ${
                        active
                          ? 'bg-primary text-white brutal-border brutal-shadow-sm'
                          : 'text-gray-500 hover:text-black hover:bg-gray-50'
                      }`}
                    title={sidebarCollapsed ? item.label : undefined}
                  >
                    <Icon size={18} strokeWidth={active ? 2.5 : 2} />
                    {!sidebarCollapsed && <span>{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* 통계 */}
          {!sidebarCollapsed && (
            <div className="px-3 py-3 bg-gray-50 rounded-xl mx-0">
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest px-1 mb-2">통계</p>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between px-1">
                  <span className="text-[11px] font-bold text-gray-500 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                    실시간 토론
                  </span>
                  <span className="text-sm font-black text-black">
                    {liveCount === null ? '...' : liveCount.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center justify-between px-1">
                  <span className="text-[11px] font-bold text-gray-500 flex items-center gap-1.5">
                    <List size={10} className="text-gray-400" />
                    진행 예정
                  </span>
                  <span className="text-sm font-black text-black">
                    {scheduledCount === null ? '...' : scheduledCount.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          )}
        </nav>

        {/* 관리자 링크 */}
        {isAdmin() && (
          <div className={`px-3 py-2 ${sidebarCollapsed ? 'flex justify-center' : ''}`}>
            <Link
              href="/admin"
              className={`flex items-center gap-2 rounded-xl text-sm text-amber-500 hover:bg-amber-50 transition-colors no-underline font-bold
                ${sidebarCollapsed ? 'p-2.5 justify-center' : 'px-4 py-2.5'}`}
              title={sidebarCollapsed ? '관리자' : undefined}
            >
              <ShieldCheck size={18} />
              {!sidebarCollapsed && <span>관리자</span>}
            </Link>
          </div>
        )}

        {/* 로그아웃 */}
        <div className={`px-3 py-4 border-t-2 border-black/5 ${sidebarCollapsed ? 'flex justify-center' : ''}`}>
          <button
            onClick={handleLogout}
            className={`w-full flex items-center gap-3 rounded-xl text-sm font-bold cursor-pointer border-none transition-all duration-150 bg-red-50 text-red-500 hover:bg-red-100
              ${sidebarCollapsed ? 'p-2.5 justify-center' : 'px-4 py-3'}`}
            title={sidebarCollapsed ? '로그아웃' : undefined}
          >
            <LogOut size={18} />
            {!sidebarCollapsed && <span>로그아웃</span>}
          </button>
        </div>
      </aside>

      {/* Logout Confirmation Modal */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setShowLogoutConfirm(false)}>
          <div className="bg-white brutal-border brutal-shadow-lg w-full max-w-sm p-8 animate-in zoom-in-95 duration-200" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center text-red-500 brutal-border border-red-200">
                <LogOut size={32} />
              </div>
            </div>
            
            <h3 className="text-xl font-black text-center text-black mb-2">로그아웃 하시겠습니까?</h3>
            <p className="text-sm font-bold text-center text-gray-500 mb-8">안전하게 세션이 종료됩니다.</p>

            <div className="flex flex-col gap-3">
              <button
                onClick={confirmLogout}
                className="w-full py-4 bg-red-500 text-white font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer border-none"
              >
                로그아웃
              </button>
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="w-full py-4 bg-white text-black font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer border-none"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
});
