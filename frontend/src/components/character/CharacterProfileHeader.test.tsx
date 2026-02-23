import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CharacterProfileHeader } from './CharacterProfileHeader';

const basePage = {
  id: 'p1',
  display_name: '테스트 캐릭터',
  description: '캐릭터 소개입니다.',
  greeting_message: null,
  age_rating: 'all' as const,
  category: 'romance',
  tags: ['판타지', 'RP'],
  background_image_url: null,
  live2d_model_id: null,
  creator_name: 'creator123',
  stats: { post_count: 12, follower_count: 100, like_count: 50, chat_count: 5 },
  is_following: false,
  created_at: '2026-01-01T00:00:00Z',
};

describe('CharacterProfileHeader', () => {
  it('should render display name', () => {
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText('테스트 캐릭터')).toBeInTheDocument();
  });

  it('should render creator name', () => {
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText('@creator123')).toBeInTheDocument();
  });

  it('should render description', () => {
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText('캐릭터 소개입니다.')).toBeInTheDocument();
  });

  it('should render stats', () => {
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText('12')).toBeInTheDocument(); // post_count
    expect(screen.getByText('100')).toBeInTheDocument(); // follower_count
    expect(screen.getByText('50')).toBeInTheDocument(); // like_count
  });

  it('should render category and tags', () => {
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText('romance')).toBeInTheDocument();
    expect(screen.getByText('#판타지')).toBeInTheDocument();
    expect(screen.getByText('#RP')).toBeInTheDocument();
  });

  it('should show follow button when not following', () => {
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText('팔로우')).toBeInTheDocument();
  });

  it('should show following button when already following', () => {
    const followingPage = { ...basePage, is_following: true };
    render(
      <CharacterProfileHeader page={followingPage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText('팔로잉')).toBeInTheDocument();
  });

  it('should call onFollow when follow button clicked', () => {
    const onFollow = vi.fn();
    render(
      <CharacterProfileHeader page={basePage} onFollow={onFollow} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    fireEvent.click(screen.getByText('팔로우'));
    expect(onFollow).toHaveBeenCalledOnce();
  });

  it('should call onUnfollow when following button clicked', () => {
    const onUnfollow = vi.fn();
    const followingPage = { ...basePage, is_following: true };
    render(
      <CharacterProfileHeader page={followingPage} onFollow={vi.fn()} onUnfollow={onUnfollow} onChatRequest={vi.fn()} />,
    );
    fireEvent.click(screen.getByText('팔로잉'));
    expect(onUnfollow).toHaveBeenCalledOnce();
  });

  it('should call onChatRequest when chat button clicked', () => {
    const onChatRequest = vi.fn();
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={onChatRequest} />,
    );
    fireEvent.click(screen.getByText('1:1 대화 요청'));
    expect(onChatRequest).toHaveBeenCalledOnce();
  });

  it('should render age rating badge', () => {
    render(
      <CharacterProfileHeader page={basePage} onFollow={vi.fn()} onUnfollow={vi.fn()} onChatRequest={vi.fn()} />,
    );
    expect(screen.getByText(/전체/)).toBeInTheDocument();
  });
});
