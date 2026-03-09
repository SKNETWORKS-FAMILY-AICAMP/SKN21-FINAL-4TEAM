'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { UserSidebar } from '@/components/layout/UserSidebar';
import { MobileHeader } from '@/components/layout/MobileHeader';
import { DesktopHeader } from '@/components/layout/DesktopHeader';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { GuideProvider } from '@/components/guide/GuideProvider';
import { useUserStore } from '@/stores/userStore';
import { useFeatureFlagStore } from '@/stores/featureFlagStore';

/** pathname prefix → feature flag key 매핑. */
const ROUTE_FLAG_MAP: [string, string][] = [
  ['/sessions', 'chat'],
  ['/chat/', 'chat'],
  ['/personas', 'personas'],
  ['/community', 'community'],
  ['/character-chats', 'character_chats'],
  ['/character/', 'character_pages'],
  ['/debate', 'debate'],
  ['/favorites', 'favorites'],
  ['/relationships', 'relationships'],
  ['/pending-posts', 'pending_posts'],
  ['/mypage', 'mypage'],
  ['/notifications', 'notifications'],
];

function resolveFlag(pathname: string): string | null {
  for (const [prefix, key] of ROUTE_FLAG_MAP) {
    if (pathname === prefix || pathname.startsWith(prefix + '/') || pathname.startsWith(prefix)) {
      return key;
    }
  }
  return null;
}

function MaintenancePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-4">
      <div className="text-5xl">🔧</div>
      <h2 className="text-xl font-bold text-text">서비스 점검 중</h2>
      <p className="text-text-secondary text-sm max-w-xs">
        이 화면은 현재 관리자에 의해 비활성화되어 있습니다.
        <br />
        잠시 후 다시 시도해 주세요.
      </p>
    </div>
  );
}

export default function UserLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { initialized, user, initialize } = useUserStore();
  const { load: loadFlags, isEnabled, loaded: flagsLoaded } = useFeatureFlagStore();
  const isChatPage = pathname.startsWith('/chat/');

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    loadFlags();
  }, [loadFlags]);

  useEffect(() => {
    if (initialized && !user) {
      router.push('/');
    }
  }, [initialized, user, router]);

  if (!initialized || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <span className="inline-block w-6 h-6 border-2 border-text-muted border-t-nemo rounded-full animate-spin" />
      </div>
    );
  }

  if (isChatPage) {
    return <>{children}</>;
  }

  const flagKey = resolveFlag(pathname);
  const pageDisabled = flagsLoaded && flagKey !== null && !isEnabled(flagKey);

  return (
    <div className="flex min-h-screen">
      <UserSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <MobileHeader />
        <DesktopHeader />
        <main className="flex-1 p-4 md:p-6 overflow-y-auto">
          <ErrorBoundary>
            <GuideProvider>{pageDisabled ? <MaintenancePage /> : children}</GuideProvider>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
