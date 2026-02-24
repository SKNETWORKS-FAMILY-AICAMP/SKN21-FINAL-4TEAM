'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { UserSidebar } from '@/components/layout/UserSidebar';
import { MobileHeader } from '@/components/layout/MobileHeader';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { GuideProvider } from '@/components/guide/GuideProvider';
import { useUserStore } from '@/stores/userStore';

export default function UserLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { initialized, user, initialize } = useUserStore();
  const isChatPage = pathname.startsWith('/chat/');

  useEffect(() => {
    initialize();
  }, [initialize]);

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

  if (isChatPage) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <UserSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <MobileHeader />
        <main className="flex-1 p-4 md:p-6 overflow-y-auto">
          <ErrorBoundary>
            <GuideProvider>{children}</GuideProvider>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
