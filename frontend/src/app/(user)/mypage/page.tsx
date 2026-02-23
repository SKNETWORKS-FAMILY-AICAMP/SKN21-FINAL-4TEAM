'use client';

import { Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { UserCircle, Settings, BarChart3, Crown, Users2, Brain, Palette } from 'lucide-react';
import { ProfileTab } from '@/components/mypage/ProfileTab';
import { SettingsTab } from '@/components/mypage/SettingsTab';
import { UsageTab } from '@/components/mypage/UsageTab';
import { SubscriptionTab } from '@/components/mypage/SubscriptionTab';
import { UserPersonaTab } from '@/components/mypage/UserPersonaTab';
import { MemoriesTab } from '@/components/mypage/MemoriesTab';
import { CreatorTab } from '@/components/mypage/CreatorTab';

const TABS = [
  { key: 'profile', label: '내 정보', icon: UserCircle },
  { key: 'settings', label: '설정', icon: Settings },
  { key: 'usage', label: '사용량', icon: BarChart3 },
  { key: 'subscription', label: '구독', icon: Crown },
  { key: 'user-persona', label: '내 캐릭터', icon: Users2 },
  { key: 'memories', label: '기억', icon: Brain },
  { key: 'creator', label: '크리에이터', icon: Palette },
] as const;

type TabKey = (typeof TABS)[number]['key'];

function MyPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'profile';

  const handleTabChange = (tab: TabKey) => {
    router.push(`/mypage?tab=${tab}`, { scroll: false });
  };

  return (
    <div className="max-w-[800px] mx-auto py-6 px-4">
      <h1 className="page-title">마이페이지</h1>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-border overflow-x-auto scrollbar-hide">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const active = currentTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              className={`flex items-center gap-1.5 px-3 md:px-4 py-2.5 text-sm font-medium border-b-2 transition-colors duration-200 bg-transparent border-x-0 border-t-0 cursor-pointer whitespace-nowrap flex-shrink-0 ${
                active
                  ? 'border-b-primary text-primary'
                  : 'border-b-transparent text-text-muted hover:text-text'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {currentTab === 'profile' && <ProfileTab />}
      {currentTab === 'settings' && <SettingsTab />}
      {currentTab === 'usage' && <UsageTab />}
      {currentTab === 'subscription' && <SubscriptionTab />}
      {currentTab === 'user-persona' && <UserPersonaTab />}
      {currentTab === 'memories' && <MemoriesTab />}
      {currentTab === 'creator' && <CreatorTab />}
    </div>
  );
}

export default function MyPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-[800px] mx-auto py-6 px-4">
          <div className="h-8 w-32 bg-bg-hover rounded animate-pulse mb-6" />
          <div className="flex gap-1 mb-6 border-b border-border">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="h-10 w-20 bg-bg-hover rounded animate-pulse" />
            ))}
          </div>
          <div className="h-64 bg-bg-hover rounded animate-pulse" />
        </div>
      }
    >
      <MyPageContent />
    </Suspense>
  );
}
