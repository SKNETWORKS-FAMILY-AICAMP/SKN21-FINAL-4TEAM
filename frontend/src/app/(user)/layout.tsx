'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { UserSidebar } from '@/components/layout/UserSidebar';
import { TopHeader } from '@/components/layout/TopHeader';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { GuideProvider } from '@/components/guide/GuideProvider';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';

export default function UserLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { initialized, user, initialize } = useUserStore();
  const { theme } = useUIStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  // 테마 변경 시 html 요소에 data-theme 속성 동기화
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (initialized && !user) {
      router.push('/');
    }
  }, [initialized, user, router]);

  if (!initialized || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <span className="inline-block w-6 h-6 border-2 border-text-muted border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <UserSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopHeader />
        <main className="flex-1 p-4 md:p-6 overflow-y-auto">
          <ErrorBoundary>
            <GuideProvider>{children}</GuideProvider>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
