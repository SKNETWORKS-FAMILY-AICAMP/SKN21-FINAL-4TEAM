'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Send } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';
import type { Post, Comment } from '@/stores/communityStore';
import { PersonaAvatar } from '@/components/community/PersonaAvatar';
import { ReactionButton } from '@/components/community/ReactionButton';
import { CommentTree } from '@/components/community/CommentTree';

type PostDetail = {
  post: Post;
  comments: Comment[];
};

export default function PostDetailPage() {
  const params = useParams();
  const router = useRouter();
  const postId = params.id as string;

  const [data, setData] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [commentText, setCommentText] = useState('');
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchDetail = async () => {
    try {
      const result = await api.get<PostDetail>(`/board/posts/${postId}`);
      setData(result);
    } catch {
      toast.error('게시글을 불러올 수 없습니다');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [postId]);

  const handleComment = async () => {
    if (!commentText.trim() || submitting) return;
    setSubmitting(true);
    try {
      await api.post(`/board/posts/${postId}/comments`, {
        content: commentText.trim(),
        parent_id: replyTo,
      });
      setCommentText('');
      setReplyTo(null);
      toast.success('댓글이 작성되었습니다');
      await fetchDetail();
    } catch {
      toast.error('댓글 작성에 실패했습니다');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReply = (commentId: string) => {
    setReplyTo(commentId);
  };

  if (loading) {
    return (
      <div className="max-w-[800px] mx-auto py-6 px-4">
        <div className="animate-pulse">
          <div className="h-6 w-1/3 rounded bg-bg-hover mb-4" />
          <div className="h-4 w-full rounded bg-bg-hover mb-2" />
          <div className="h-4 w-2/3 rounded bg-bg-hover" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-[800px] mx-auto py-6 px-4 text-center">
        <p className="text-text-muted">게시글을 찾을 수 없습니다</p>
      </div>
    );
  }

  const { post, comments } = data;

  return (
    <div className="max-w-[800px] mx-auto py-6 px-4">
      {/* 뒤로가기 */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4 bg-transparent border-none cursor-pointer"
      >
        <ArrowLeft size={16} />
        목록으로
      </button>

      {/* 게시글 */}
      <article className="card p-6 mb-6">
        <div className="flex items-start gap-3 mb-4">
          <PersonaAvatar type={post.author.type} displayName={post.author.display_name} />
          <div>
            <span className="text-sm font-semibold text-text">{post.author.display_name}</span>
            <span className="text-xs text-text-muted ml-2">
              {new Date(post.created_at).toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        </div>

        {post.title && <h1 className="text-xl font-bold text-text mb-3">{post.title}</h1>}
        <p className="text-sm text-text-secondary whitespace-pre-wrap leading-relaxed">
          {post.content}
        </p>

        <div className="flex items-center gap-3 mt-4 pt-4 border-t border-border">
          <ReactionButton postId={post.id} count={post.reaction_count} myReaction={post.my_reaction} />
          <span className="text-xs text-text-muted">댓글 {post.comment_count}</span>
        </div>
      </article>

      {/* 댓글 입력 */}
      <div className="card p-4 mb-4">
        {replyTo && (
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-primary">답글 작성 중</span>
            <button
              onClick={() => setReplyTo(null)}
              className="text-xs text-text-muted hover:text-text bg-transparent border-none cursor-pointer"
            >
              취소
            </button>
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="댓글을 입력하세요..."
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleComment()}
            maxLength={2000}
            className="flex-1 px-3 py-2 rounded-lg border border-border bg-bg text-sm text-text placeholder-text-muted outline-none focus:border-primary"
          />
          <button
            onClick={handleComment}
            disabled={!commentText.trim() || submitting}
            className={`px-3 py-2 rounded-lg border-none cursor-pointer ${
              commentText.trim() && !submitting
                ? 'bg-primary text-white'
                : 'bg-bg-hover text-text-muted cursor-not-allowed'
            }`}
          >
            <Send size={16} />
          </button>
        </div>
      </div>

      {/* 댓글 트리 */}
      {comments.length > 0 ? (
        <div className="card p-4">
          <CommentTree comments={comments} onReply={handleReply} />
        </div>
      ) : (
        <div className="text-center py-8">
          <p className="text-sm text-text-muted">아직 댓글이 없습니다. 첫 댓글을 남겨보세요!</p>
        </div>
      )}
    </div>
  );
}
