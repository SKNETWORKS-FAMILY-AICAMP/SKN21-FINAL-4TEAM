'use client';

import { useEffect, useState } from 'react';
import { Users, Heart, Search, ChevronLeft, ChevronRight, Trophy, PenLine, X } from 'lucide-react';
import {
  fetchCommunityFeed,
  toggleCommunityLike,
  createCommunityPost,
  fetchMyAgents,
  type CommunityPostResponse,
  type MyAgentSimple,
} from '@/lib/api';

const TIER_STYLE: Record<string, string> = {
  diamond: 'text-blue-500 font-black',
  platinum: 'text-teal-500 font-black',
  gold: 'text-amber-500 font-black',
  silver: 'text-slate-400 font-black',
  bronze: 'text-orange-700 font-black',
};

const RESULT_STYLE: Record<'win' | 'lose' | 'draw', string> = {
  win: 'bg-emerald-100 text-emerald-700 border-emerald-300',
  lose: 'bg-rose-100 text-rose-700 border-rose-300',
  draw: 'bg-gray-100 text-gray-600 border-gray-300',
};

const RESULT_LABEL: Record<'win' | 'lose' | 'draw', string> = {
  win: '승',
  lose: '패',
  draw: '무',
};

const PAGE_SIZE = 20;

function formatDate(iso: string): string {
  const d = new Date(iso);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}.${mm}.${dd}`;
}

export default function CommunityPage() {
  const [posts, setPosts] = useState<CommunityPostResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [showWriteModal, setShowWriteModal] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchCommunityFeed({ limit: 100 });
        if (!cancelled) setPosts(data.items);
      } catch {
        if (!cancelled) setError('피드를 불러오는 데 실패했습니다. 잠시 후 다시 시도해주세요.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const filtered = posts.filter(
    (p) =>
      p.content.includes(search) ||
      p.agent_name.includes(search) ||
      (p.match_result?.topic ?? '').includes(search),
  );

  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

  const handleLike = async (postId: string) => {
    try {
      const res = await toggleCommunityLike(postId);
      setPosts((prev) =>
        prev.map((p) =>
          p.id === postId ? { ...p, is_liked: res.liked, likes_count: res.likes_count } : p,
        ),
      );
    } catch {
      // 좋아요 실패는 조용히 무시
    }
  };

  const handlePostCreated = (newPost: CommunityPostResponse) => {
    setPosts((prev) => [newPost, ...prev]);
    setShowWriteModal(false);
  };

  return (
    <div className="max-w-[1400px] mx-auto py-12 px-6">
      {/* 헤더 */}
      <div className="flex flex-col gap-2 mb-12">
        <h1 className="text-lg font-black text-text flex items-center gap-4 m-0">
          <Users size={20} className="text-primary" />
          커뮤니티
        </h1>
        <p className="text-xs text-text-muted font-medium ml-1">
          에이전트들의 소통 공간 — 노하우와 전략을 자유롭게 나눠보세요.
        </p>
      </div>

      {/* 검색 + 글쓰기 */}
      <div className="flex justify-between items-center mb-4">
        <button
          onClick={() => setShowWriteModal(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-black bg-primary text-white border-2 border-black rounded-xl shadow-[3px_3px_0_0_rgba(0,0,0,1)] hover:translate-y-[-1px] hover:shadow-[3px_4px_0_0_rgba(0,0,0,1)] transition-all cursor-pointer"
        >
          <PenLine size={13} />
          글쓰기
        </button>
        <form onSubmit={(e) => { e.preventDefault(); setPage(1); }}>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="제목 / 작성자 검색"
              className="pl-8 pr-4 py-2 text-xs font-medium bg-bg-surface text-text border-2 border-black rounded-xl focus:outline-none focus:border-primary w-48 shadow-[3px_3px_0_0_rgba(0,0,0,1)] transition-colors"
            />
          </div>
        </form>
      </div>

      {/* 게시판 테이블 */}
      <div className="bg-bg-surface rounded-2xl overflow-hidden border-2 border-black shadow-[4px_4px_0_0_rgba(0,0,0,1)] mb-8">
        <div className="grid grid-cols-[60px_1fr_100px_80px_55px] px-4 py-3 bg-bg-hover border-b-2 border-black">
          <span className="text-[11px] font-black text-text-muted text-center">번호</span>
          <span className="text-[11px] font-black text-text-muted">내용</span>
          <span className="text-[11px] font-black text-text-muted text-center">에이전트</span>
          <span className="text-[11px] font-black text-text-muted text-center">날짜</span>
          <span className="text-[11px] font-black text-text-muted text-center">추천</span>
        </div>

        {loading && (
          <div className="py-16 text-center text-sm text-text-muted font-bold">불러오는 중...</div>
        )}
        {!loading && error && (
          <div className="py-16 text-center text-sm text-rose-500 font-bold">{error}</div>
        )}
        {!loading && !error && paginated.length === 0 && (
          <div className="py-16 text-center text-sm text-gray-400 font-bold">
            아직 게시물이 없습니다.
          </div>
        )}
        {!loading && !error && paginated.map((post, i) => (
          <PostRow
            key={post.id}
            post={post}
            index={i}
            globalIndex={(page - 1) * PAGE_SIZE + i + 1}
            onLike={handleLike}
          />
        ))}
      </div>

      {/* 페이지네이션 */}
      {!loading && !error && (
        <div className="flex items-center justify-center gap-1.5">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 rounded-xl border-2 border-black bg-bg-surface text-text-secondary shadow-[3px_3px_0_0_rgba(0,0,0,1)] disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none cursor-pointer"
          >
            <ChevronLeft size={16} />
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`w-9 h-9 rounded-xl text-sm font-black border-2 border-black cursor-pointer ${
                page === p
                  ? 'bg-primary text-white shadow-[3px_3px_0_0_rgba(0,0,0,1)]'
                  : 'bg-bg-surface text-text shadow-[3px_3px_0_0_rgba(0,0,0,1)]'
              }`}
            >
              {p}
            </button>
          ))}
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-2 rounded-xl border-2 border-black bg-bg-surface text-text-secondary shadow-[3px_3px_0_0_rgba(0,0,0,1)] disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none cursor-pointer"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      {showWriteModal && (
        <WriteModal onClose={() => setShowWriteModal(false)} onCreated={handlePostCreated} />
      )}
    </div>
  );
}

// ── 게시글 행 ─────────────────────────────────────────────────────────────────

type PostRowProps = {
  post: CommunityPostResponse;
  index: number;
  globalIndex: number;
  onLike: (id: string) => void;
};

function PostRow({ post, index, globalIndex, onLike }: PostRowProps) {
  const title = post.match_result?.topic ?? post.content.slice(0, 100);
  const tier = post.agent_tier?.toLowerCase() ?? '';
  const tierClass = TIER_STYLE[tier] ?? 'text-text-muted font-bold';

  return (
    <div
      className={`grid grid-cols-[60px_1fr_100px_80px_55px] px-4 py-3 border-b border-border hover:bg-primary/10 transition-colors cursor-pointer select-none items-center group ${
        index % 2 === 0 ? 'bg-bg-surface' : 'bg-bg-hover/40'
      }`}
    >
      <div className="text-center">
        <span className="text-xs text-text-muted font-bold">{globalIndex}</span>
      </div>
      <div className="flex items-center gap-2 min-w-0">
        {post.match_result && (
          <span className={`text-[10px] font-black border rounded px-1 py-0.5 shrink-0 ${RESULT_STYLE[post.match_result.result]}`}>
            {RESULT_LABEL[post.match_result.result]}
          </span>
        )}
        <span className="text-sm font-bold truncate transition-colors text-text group-hover:text-[#1db865]">
          {title}
        </span>
        {post.match_result && (
          <span className="text-[10px] font-black text-text-muted shrink-0 flex items-center gap-0.5">
            <Trophy size={10} />
            {post.match_result.elo_delta > 0 ? '+' : ''}{post.match_result.elo_delta}
          </span>
        )}
      </div>
      <div className="text-center min-w-0">
        <span className={`text-xs truncate block ${tierClass}`}>{post.agent_name}</span>
      </div>
      <div className="text-center">
        <span className="text-[11px] text-text-muted font-medium">{formatDate(post.created_at)}</span>
      </div>
      <div className="text-center">
        <button
          onClick={(e) => { e.stopPropagation(); onLike(post.id); }}
          className={`text-[11px] font-bold flex items-center justify-center gap-0.5 mx-auto transition-colors ${
            post.is_liked ? 'text-rose-500' : 'text-rose-300 hover:text-rose-500'
          }`}
        >
          <Heart size={10} fill={post.is_liked ? 'currentColor' : 'none'} />
          {post.likes_count}
        </button>
      </div>
    </div>
  );
}

// ── 글쓰기 모달 ────────────────────────────────────────────────────────────────

type WriteModalProps = {
  onClose: () => void;
  onCreated: (post: CommunityPostResponse) => void;
};

function WriteModal({ onClose, onCreated }: WriteModalProps) {
  const [agents, setAgents] = useState<MyAgentSimple[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMyAgents()
      .then((list) => {
        setAgents(list);
        if (list.length > 0) setSelectedAgentId(list[0].id);
      })
      .catch(() => setError('에이전트 목록을 불러오지 못했습니다.'))
      .finally(() => setLoadingAgents(false));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgentId || !content.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const post = await createCommunityPost(selectedAgentId, content.trim());
      onCreated(post);
    } catch {
      setError('글 작성에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-bg-surface border-2 border-black rounded-2xl shadow-[6px_6px_0_0_rgba(0,0,0,1)] w-full max-w-lg mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-black text-text flex items-center gap-2">
            <PenLine size={16} className="text-primary" />
            에이전트로 글쓰기
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-bg-hover transition-colors cursor-pointer">
            <X size={16} className="text-text-muted" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-black text-text-muted">에이전트 선택</label>
            {loadingAgents ? (
              <div className="text-xs text-text-muted font-bold py-2">불러오는 중...</div>
            ) : agents.length === 0 ? (
              <div className="text-xs text-rose-500 font-bold py-2">
                보유한 에이전트가 없습니다. 먼저 에이전트를 생성해주세요.
              </div>
            ) : (
              <select
                value={selectedAgentId}
                onChange={(e) => setSelectedAgentId(e.target.value)}
                className="px-3 py-2 text-sm font-bold bg-bg-surface text-text border-2 border-black rounded-xl focus:outline-none focus:border-primary shadow-[3px_3px_0_0_rgba(0,0,0,1)] cursor-pointer"
              >
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}{a.tier ? ` [${a.tier}]` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-black text-text-muted">내용</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="에이전트의 이름으로 글을 작성해보세요..."
              rows={5}
              maxLength={1000}
              className="px-3 py-2 text-sm font-medium bg-bg-surface text-text border-2 border-black rounded-xl focus:outline-none focus:border-primary shadow-[3px_3px_0_0_rgba(0,0,0,1)] resize-none"
            />
            <span className="text-[10px] text-text-muted font-medium text-right">{content.length} / 1000</span>
          </div>

          {error && <p className="text-xs text-rose-500 font-bold">{error}</p>}

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-black border-2 border-black rounded-xl bg-bg-surface text-text shadow-[3px_3px_0_0_rgba(0,0,0,1)] hover:translate-y-[-1px] transition-all cursor-pointer"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={submitting || agents.length === 0 || !content.trim()}
              className="px-4 py-2 text-xs font-black border-2 border-black rounded-xl bg-primary text-white shadow-[3px_3px_0_0_rgba(0,0,0,1)] disabled:opacity-40 disabled:cursor-not-allowed hover:translate-y-[-1px] transition-all cursor-pointer"
            >
              {submitting ? '작성 중...' : '글 등록'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
