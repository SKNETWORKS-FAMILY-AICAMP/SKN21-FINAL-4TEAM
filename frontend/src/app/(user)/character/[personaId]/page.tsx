'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { useCharacterPageStore } from '@/stores/characterPageStore';
import { CharacterProfileHeader } from '@/components/character/CharacterProfileHeader';
import { CharacterPostFeed } from '@/components/character/CharacterPostFeed';
import { ChatRequestModal } from '@/components/character/ChatRequestModal';
import { WorldEventBanner } from '@/components/character/WorldEventBanner';
import { SkeletonCard } from '@/components/ui/Skeleton';

export default function CharacterPage() {
  const params = useParams();
  const router = useRouter();
  const personaId = params.personaId as string;

  const { page, posts, postsTotal, loading, fetchPage, fetchPosts, follow, unfollow } =
    useCharacterPageStore();
  const [chatModalOpen, setChatModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'posts' | 'chats'>('posts');

  useEffect(() => {
    if (personaId) {
      fetchPage(personaId);
      fetchPosts(personaId);
    }
  }, [personaId, fetchPage, fetchPosts]);

  const handleLoadMore = useCallback(() => {
    fetchPosts(personaId, posts.length);
  }, [personaId, posts.length, fetchPosts]);

  if (loading && !page) {
    return (
      <div className="max-w-[600px] mx-auto py-6 px-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (!page) {
    return (
      <div className="max-w-[600px] mx-auto py-6 px-4 text-center text-text-muted">
        캐릭터를 찾을 수 없습니다.
      </div>
    );
  }

  return (
    <div className="max-w-[600px] mx-auto py-6 px-4">
      {/* 뒤로가기 */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4 bg-transparent border-none cursor-pointer"
      >
        <ArrowLeft size={16} />
        돌아가기
      </button>

      {/* 세계관 이벤트 배너 */}
      <WorldEventBanner />

      {/* 프로필 헤더 */}
      <div className="bg-bg-surface border border-border rounded-xl mb-4 overflow-hidden">
        <CharacterProfileHeader
          page={page}
          onFollow={() => follow(personaId)}
          onUnfollow={() => unfollow(personaId)}
          onChatRequest={() => setChatModalOpen(true)}
        />
      </div>

      {/* 탭 */}
      <div className="flex gap-1 mb-4 border-b border-border">
        <TabButton active={activeTab === 'posts'} onClick={() => setActiveTab('posts')}>
          게시물
        </TabButton>
        <TabButton active={activeTab === 'chats'} onClick={() => setActiveTab('chats')}>
          대화
        </TabButton>
      </div>

      {/* 콘텐츠 */}
      {activeTab === 'posts' && (
        <CharacterPostFeed
          posts={posts}
          total={postsTotal}
          onLoadMore={handleLoadMore}
          loading={loading}
        />
      )}

      {activeTab === 'chats' && (
        <div className="text-center py-8 text-text-muted text-sm">
          공개된 캐릭터 대화가 여기에 표시됩니다.
        </div>
      )}

      {/* 대화 요청 모달 */}
      <ChatRequestModal
        responderPersonaId={personaId}
        responderName={page.display_name || '캐릭터'}
        open={chatModalOpen}
        onClose={() => setChatModalOpen(false)}
      />
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-semibold bg-transparent border-none cursor-pointer transition-colors ${
        active
          ? 'text-primary border-b-2 border-primary -mb-px'
          : 'text-text-muted hover:text-text'
      }`}
    >
      {children}
    </button>
  );
}
