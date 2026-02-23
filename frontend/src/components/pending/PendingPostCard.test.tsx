import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PendingPostCard } from './PendingPostCard';

const basePending = {
  id: 'pending-1',
  persona_id: 'p1',
  persona_display_name: '테스트 캐릭터',
  content_type: 'post' as const,
  title: '오늘의 이야기',
  content: 'AI가 생성한 게시물 내용입니다.',
  target_post_id: null,
  target_comment_id: null,
  status: 'pending',
  input_tokens: 100,
  output_tokens: 50,
  cost: 0.0002,
  created_at: '2026-01-01T00:00:00Z',
  reviewed_at: null,
};

describe('PendingPostCard', () => {
  it('should render post content', () => {
    render(<PendingPostCard pending={basePending} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('AI가 생성한 게시물 내용입니다.')).toBeInTheDocument();
  });

  it('should render title', () => {
    render(<PendingPostCard pending={basePending} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('오늘의 이야기')).toBeInTheDocument();
  });

  it('should render persona name', () => {
    render(<PendingPostCard pending={basePending} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('테스트 캐릭터')).toBeInTheDocument();
  });

  it('should show content type as 게시물 for post', () => {
    render(<PendingPostCard pending={basePending} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('게시물')).toBeInTheDocument();
  });

  it('should show content type as 댓글 for comment', () => {
    const comment = { ...basePending, content_type: 'comment' };
    render(<PendingPostCard pending={comment} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('댓글')).toBeInTheDocument();
  });

  it('should show token and cost info', () => {
    render(<PendingPostCard pending={basePending} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText(/150/)).toBeInTheDocument(); // 100 + 50
    expect(screen.getByText(/0\.0002/)).toBeInTheDocument();
  });

  it('should show approve and reject buttons for pending status', () => {
    render(<PendingPostCard pending={basePending} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('승인')).toBeInTheDocument();
    expect(screen.getByText('거절')).toBeInTheDocument();
  });

  it('should call onApprove with pending id', () => {
    const onApprove = vi.fn();
    render(<PendingPostCard pending={basePending} onApprove={onApprove} onReject={vi.fn()} />);
    fireEvent.click(screen.getByText('승인'));
    expect(onApprove).toHaveBeenCalledWith('pending-1');
  });

  it('should call onReject with pending id', () => {
    const onReject = vi.fn();
    render(<PendingPostCard pending={basePending} onApprove={vi.fn()} onReject={onReject} />);
    fireEvent.click(screen.getByText('거절'));
    expect(onReject).toHaveBeenCalledWith('pending-1');
  });

  it('should show approved badge for approved status', () => {
    const approved = { ...basePending, status: 'approved' };
    render(<PendingPostCard pending={approved} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('승인됨')).toBeInTheDocument();
    expect(screen.queryByText('거절')).not.toBeInTheDocument();
  });

  it('should show rejected badge for rejected status', () => {
    const rejected = { ...basePending, status: 'rejected' };
    render(<PendingPostCard pending={rejected} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('거절됨')).toBeInTheDocument();
    expect(screen.queryByText('승인')).not.toBeInTheDocument();
  });
});
