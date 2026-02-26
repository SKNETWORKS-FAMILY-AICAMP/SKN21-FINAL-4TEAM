'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Search, MessageCircle, Plus, Sparkles, Settings2, MessageSquare, PenSquare, Users, Crown, Heart, Upload, Flag } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useUserStore } from '@/stores/userStore';
import { CATEGORIES } from '@/constants/categories';
import { AgeRatingBadge } from '@/components/persona/AgeRatingBadge';
import { CreatorPopup } from '@/components/persona/CreatorPopup';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { toast } from '@/stores/toastStore';
import { ReportModal } from '@/components/persona/ReportModal';

type Persona = {
  id: string;
  display_name: string;
  age_rating: 'all' | '15+' | '18+';
  visibility: string;
  type: string;
  system_prompt: string;
  background_image_url: string | null;
  created_by: string | null;
  creator_nickname: string | null;
  is_anonymous: boolean;
  description: string | null;
  tags: string[] | null;
  category: string | null;
  chat_count: number;
  like_count: number;
};

export default function PersonasPage() {
  const router = useRouter();
  const { user, isAdultVerified } = useUserStore();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [ratingFilter, setRatingFilter] = useState<'all' | 'all_age' | '15+' | '18+'>('all');
  const [sortBy, setSortBy] = useState<'recent' | 'popular' | 'name'>('recent');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [popularTags, setPopularTags] = useState<{tag: string; count: number}[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [creatorPopupId, setCreatorPopupId] = useState<string | null>(null);
  const [reportTarget, setReportTarget] = useState<{ id: string; name: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (sortBy !== 'recent') params.set('sort', sortBy);
    if (selectedTags.length > 0) params.set('tags', selectedTags.join(','));
    if (categoryFilter !== 'all') params.set('category', categoryFilter);
    if (ratingFilter !== 'all') params.set('rating', ratingFilter);

    setLoading(true);
    api
      .get<{ items: Persona[]; total: number }>(`/personas?${params}`, { signal: controller.signal })
      .then((res) => setPersonas(res.items ?? []))
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        console.error('Failed to load personas:', err);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [debouncedSearch, sortBy, selectedTags, categoryFilter, ratingFilter]);

  useEffect(() => {
    Promise.all([
      api.get<{tag: string; count: number}[]>('/personas/tags').catch(() => [] as {tag: string; count: number}[]),
      api.get<{items: {persona_id: string}[]}>('/favorites').catch(() => ({ items: [] })),
    ]).then(([tags, favRes]) => {
      setPopularTags(tags);
      setFavorites(new Set((favRes.items ?? []).map(f => f.persona_id)));
    });
  }, []);

  const handleStartChat = async (personaId: string) => {
    try {
      const session = await api.post<{ id: string }>('/chat/sessions', { persona_id: personaId });
      router.push(`/chat/${session.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '세션 생성에 실패했습니다';
      toast.error(message);
    }
  };

  const [togglingFav, setTogglingFav] = useState<string | null>(null);

  const handleToggleFavorite = async (personaId: string) => {
    if (togglingFav) return;
    setTogglingFav(personaId);
    try {
      if (favorites.has(personaId)) {
        await api.delete(`/favorites/${personaId}`);
        setFavorites(prev => { const next = new Set(prev); next.delete(personaId); return next; });
        setPersonas(prev => prev.map(p => p.id === personaId ? {...p, like_count: Math.max(0, p.like_count - 1)} : p));
      } else {
        await api.post(`/favorites/${personaId}`);
        setFavorites(prev => new Set(prev).add(personaId));
        setPersonas(prev => prev.map(p => p.id === personaId ? {...p, like_count: p.like_count + 1} : p));
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          // 이미 즐겨찾기 상태 — 로컬 상태만 동기화
          setFavorites(prev => new Set(prev).add(personaId));
          return;
        }
        if (err.status === 404) {
          // 이미 해제된 상태 — 로컬 상태만 동기화
          setFavorites(prev => { const next = new Set(prev); next.delete(personaId); return next; });
          return;
        }
      }
      toast.error('즐겨찾기 처리에 실패했습니다');
    } finally { setTogglingFav(null); }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const cardData = JSON.parse(text);
      if (!cardData.name || typeof cardData.name !== 'string') {
        toast.error('유효하지 않은 캐릭터 카드: name 필드가 필요합니다');
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }
      await api.post('/character-cards/import', cardData);
      toast.success('캐릭터 카드를 가져왔습니다');
      setLoading(true);
      const res = await api.get<{ items: Persona[]; total: number }>('/personas');
      setPersonas(res.items ?? []);
      setLoading(false);
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error('JSON 파싱 실패: 올바른 JSON 파일인지 확인하세요');
      } else {
        toast.error('가져오기에 실패했습니다');
        console.error('Import failed:', err);
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const ratingChips: { key: 'all' | 'all_age' | '15+' | '18+'; label: string }[] = [
    { key: 'all', label: '전체' },
    { key: 'all_age', label: '전연령' },
    { key: '15+', label: '15+' },
    ...(isAdultVerified() ? [{ key: '18+' as const, label: '18+' }] : []),
  ];

  const myPersonas = personas.filter((p) => p.created_by === user?.id);
  const publicPersonas = personas.filter((p) => p.created_by !== user?.id);

  return (
    <div className="max-w-[1000px] mx-auto py-6 px-4">
      {/* Hero / Welcome */}
      <div className="mb-8">
        <h1 className="m-0 text-2xl text-text">
          {user ? `${user.nickname}님, 안녕하세요` : 'AI 토론 플랫폼'}
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          어떤 캐릭터와 대화하고 싶으세요?
        </p>
      </div>

      {/* Quick Access Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <Link
          href="/sessions"
          className="card p-4 no-underline hover:border-primary transition-colors duration-200 group"
        >
          <MessageSquare size={24} className="text-primary mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="m-0 text-sm font-semibold text-text">내 대화</h3>
          <p className="m-0 text-xs text-text-muted mt-0.5">진행 중인 대화 이어가기</p>
        </Link>
        <Link
          href="/personas/create"
          className="card p-4 no-underline hover:border-primary transition-colors duration-200 group"
        >
          <PenSquare size={24} className="text-success mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="m-0 text-sm font-semibold text-text">챗봇 만들기</h3>
          <p className="m-0 text-xs text-text-muted mt-0.5">나만의 AI 캐릭터 생성</p>
        </Link>
        <Link
          href="/community"
          className="card p-4 no-underline hover:border-primary transition-colors duration-200 group"
        >
          <Users size={24} className="text-secondary mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="m-0 text-sm font-semibold text-text">캐릭터 라운지</h3>
          <p className="m-0 text-xs text-text-muted mt-0.5">다른 사람의 캐릭터 구경</p>
        </Link>
        <Link
          href="/mypage?tab=subscription"
          className="card p-4 no-underline hover:border-primary transition-colors duration-200 group"
        >
          <Crown size={24} className="text-warning mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="m-0 text-sm font-semibold text-text">구독 & 크레딧</h3>
          <p className="m-0 text-xs text-text-muted mt-0.5">플랜 관리 및 대화석 확인</p>
        </Link>
      </div>

      {/* Search bar */}
      <div className="relative mb-5">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          placeholder="챗봇 검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input py-3 pl-11 pr-4 w-full text-[15px] rounded-xl"
        />
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {ratingChips.map((chip) => (
          <button
            key={chip.key}
            onClick={() => setRatingFilter(chip.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors duration-150 ${
              ratingFilter === chip.key
                ? 'bg-primary text-white border-primary'
                : 'bg-bg-surface text-text-secondary border-border hover:border-primary/50'
            }`}
          >
            {chip.label}
          </button>
        ))}
        <div className="hidden sm:block sm:flex-1" />
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'recent' | 'popular' | 'name')}
            className="px-3 py-1.5 rounded-lg text-sm border border-border bg-bg-surface text-text-secondary"
          >
            <option value="recent">최신순</option>
            <option value="popular">인기순</option>
            <option value="name">이름순</option>
          </select>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImport}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-border bg-bg-surface text-text-secondary hover:border-primary/50 hover:text-primary transition-colors duration-150"
          >
            <Upload size={14} />
            <span className="hidden sm:inline">가져오기</span>
          </button>
          <Link
            href="/personas/create"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-border bg-bg-surface text-text-secondary hover:border-primary/50 hover:text-primary no-underline transition-colors duration-150"
          >
            <Plus size={14} />
            <span className="hidden sm:inline">새 챗봇 만들기</span>
          </Link>
        </div>
      </div>

      {/* Category filter chips */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-xs text-text-muted">카테고리:</span>
        <button
          onClick={() => setCategoryFilter('all')}
          className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
            categoryFilter === 'all'
              ? 'bg-primary text-white border-primary'
              : 'bg-bg-surface text-text-muted border-border hover:border-primary/50'
          }`}
        >
          전체
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c.id}
            onClick={() => setCategoryFilter(categoryFilter === c.id ? 'all' : c.id)}
            className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
              categoryFilter === c.id
                ? 'bg-primary text-white border-primary'
                : 'bg-bg-surface text-text-muted border-border hover:border-primary/50'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Tag filter chips */}
      {popularTags.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <span className="text-xs text-text-muted">태그:</span>
          {popularTags.slice(0, 10).map((t) => (
            <button
              key={t.tag}
              onClick={() => setSelectedTags(prev =>
                prev.includes(t.tag) ? prev.filter(x => x !== t.tag) : [...prev, t.tag]
              )}
              className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                selectedTags.includes(t.tag)
                  ? 'bg-secondary text-white border-secondary'
                  : 'bg-bg-surface text-text-muted border-border hover:border-secondary/50'
              }`}
            >
              #{t.tag} ({t.count})
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && personas.length === 0 && (
        <EmptyState
          icon={<MessageCircle size={48} />}
          title="챗봇이 없습니다"
          description={search ? `"${search}"에 대한 검색 결과가 없습니다` : '새로운 AI 캐릭터를 만들어보세요'}
          action={
            !search ? (
              <Link href="/personas/create" className="btn-primary">
                첫 챗봇 만들기
              </Link>
            ) : undefined
          }
        />
      )}

      {!loading && personas.length > 0 && (
        <>
          {/* My chatbots section */}
          {myPersonas.length > 0 && (
            <section className="mb-8">
              <h2 className="flex items-center gap-2 text-base font-semibold text-text mb-3">
                <Sparkles size={16} className="text-primary" />
                내가 만든 챗봇
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
                {myPersonas.map((persona) => (
                  <ChatbotCard
                    key={persona.id}
                    persona={persona}
                    locked={persona.age_rating === '18+' && !isAdultVerified()}
                    isMine
                    isFavorited={favorites.has(persona.id)}
                    isToggling={togglingFav === persona.id}
                    onChat={handleStartChat}
                    onEdit={(id) => router.push(`/personas/${id}/edit`)}
                    onLorebook={(id) => router.push(`/personas/${id}/lorebook`)}
                    onToggleFavorite={handleToggleFavorite}
                    onCreatorClick={setCreatorPopupId}
                    onReport={setReportTarget}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Public chatbots section */}
          {publicPersonas.length > 0 && (
            <section>
              <h2 className="flex items-center gap-2 text-base font-semibold text-text mb-3">
                <MessageCircle size={16} className="text-secondary" />
                {myPersonas.length > 0 ? '공개 챗봇' : '챗봇 목록'}
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
                {publicPersonas.map((persona) => (
                  <ChatbotCard
                    key={persona.id}
                    persona={persona}
                    locked={persona.age_rating === '18+' && !isAdultVerified()}
                    isMine={false}
                    isFavorited={favorites.has(persona.id)}
                    isToggling={togglingFav === persona.id}
                    onChat={handleStartChat}
                    onEdit={() => {}}
                    onLorebook={() => {}}
                    onToggleFavorite={handleToggleFavorite}
                    onCreatorClick={setCreatorPopupId}
                    onReport={setReportTarget}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {creatorPopupId && (
        <CreatorPopup
          creatorId={creatorPopupId}
          onClose={() => setCreatorPopupId(null)}
          onChat={(personaId) => {
            setCreatorPopupId(null);
            handleStartChat(personaId);
          }}
        />
      )}

      {reportTarget && (
        <ReportModal
          personaId={reportTarget.id}
          personaName={reportTarget.name}
          onClose={() => setReportTarget(null)}
        />
      )}
    </div>
  );
}

function ChatbotCard({
  persona,
  locked,
  isMine,
  isFavorited,
  isToggling,
  onChat,
  onEdit,
  onLorebook,
  onToggleFavorite,
  onCreatorClick,
  onReport,
}: {
  persona: Persona;
  locked: boolean;
  isMine: boolean;
  isFavorited: boolean;
  isToggling: boolean;
  onChat: (id: string) => void;
  onEdit: (id: string) => void;
  onLorebook: (id: string) => void;
  onToggleFavorite: (id: string) => void;
  onCreatorClick?: (creatorId: string) => void;
  onReport?: (target: { id: string; name: string }) => void;
}) {
  return (
    <div
      className={`bg-bg-surface rounded-xl overflow-hidden border border-border transition-all duration-200 hover:border-primary hover:shadow-glow group ${
        locked ? 'opacity-60' : ''
      }`}
    >
      <div
        className="h-[140px] bg-gradient-to-br from-primary/20 to-secondary/20 bg-cover bg-center relative"
        style={
          persona.background_image_url
            ? { backgroundImage: `url(${persona.background_image_url})` }
            : undefined
        }
      >
        <div className="absolute top-3 right-3">
          <AgeRatingBadge rating={persona.age_rating} locked={locked} />
        </div>
        <div className="absolute top-3 left-3 flex gap-1.5">
          {isMine && (
            <button
              onClick={(e) => { e.stopPropagation(); onEdit(persona.id); }}
              className="p-1.5 rounded-lg bg-black/40 text-white border-none cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity"
              title="수정"
            >
              <Settings2 size={14} />
            </button>
          )}
          {!isMine && (
            <button
              onClick={(e) => { e.stopPropagation(); onReport?.({ id: persona.id, name: persona.display_name }); }}
              className="p-1.5 rounded-lg bg-black/40 text-white border-none cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity"
              title="신고"
            >
              <Flag size={14} />
            </button>
          )}
        </div>
      </div>
      <div className="p-4">
        <h3 className="m-0 text-[15px] font-semibold mb-1">{persona.display_name}</h3>
        <p className="text-[13px] text-text-secondary leading-relaxed mb-3 line-clamp-2">
          {persona.description || persona.system_prompt.slice(0, 100)}
          {!persona.description && persona.system_prompt.length > 100 ? '...' : ''}
        </p>
        <div className="flex gap-1 mb-2 flex-wrap">
          {persona.category && (
            <span className="text-[11px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium">
              {CATEGORIES.find(c => c.id === persona.category)?.label ?? persona.category}
            </span>
          )}
          {persona.tags?.slice(0, 3).map(tag => (
            <span key={tag} className="text-[11px] px-1.5 py-0.5 rounded bg-bg-hover text-text-muted">#{tag}</span>
          ))}
        </div>
        <div className="flex items-center gap-3 mb-2 text-xs text-text-muted">
          {persona.creator_nickname && !persona.is_anonymous && persona.created_by ? (
            <button
              onClick={(e) => { e.stopPropagation(); onCreatorClick?.(persona.created_by!); }}
              className="truncate max-w-[120px] bg-transparent border-none p-0 cursor-pointer text-xs text-text-muted hover:text-primary transition-colors underline decoration-dotted underline-offset-2"
            >
              by {persona.creator_nickname}
            </button>
          ) : (
            <span className="truncate max-w-[120px]">
              {isMine ? `by ${persona.creator_nickname ?? '나'}` : '익명'}
            </span>
          )}
          <span className="flex items-center gap-1"><MessageCircle size={12} />{persona.chat_count}</span>
          <button
            onClick={(e) => { e.stopPropagation(); onToggleFavorite(persona.id); }}
            disabled={isToggling}
            className={`flex items-center gap-1 bg-transparent border-none cursor-pointer p-0 transition-colors duration-200 ${
              isToggling ? 'opacity-50 pointer-events-none' : ''
            } ${isFavorited ? 'text-danger' : 'text-text-muted hover:text-danger'}`}
          >
            <Heart
              size={12}
              fill={isFavorited ? 'currentColor' : 'none'}
              className={`transition-transform duration-200 ${isFavorited ? 'scale-110' : 'scale-100'}`}
            />
            <span className="tabular-nums min-w-[1ch]">{persona.like_count}</span>
          </button>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onChat(persona.id)}
            disabled={locked}
            className={`flex items-center gap-1.5 py-2 px-4 border-none rounded-lg bg-primary text-white text-[13px] font-semibold flex-1 justify-center ${
              locked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-primary-dark'
            }`}
          >
            <MessageCircle size={14} />
            {locked ? '성인인증 필요' : '대화하기'}
          </button>
          {isMine && (
            <button
              onClick={() => onLorebook(persona.id)}
              className="btn-secondary text-[13px] px-3"
              title="로어북"
            >
              설정
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
