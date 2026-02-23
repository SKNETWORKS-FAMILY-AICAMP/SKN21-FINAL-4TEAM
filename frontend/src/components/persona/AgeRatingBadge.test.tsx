import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AgeRatingBadge } from './AgeRatingBadge';

describe('AgeRatingBadge', () => {
  it('should render "전체" label for "all" rating', () => {
    render(<AgeRatingBadge rating="all" />);
    expect(screen.getByText(/전체/)).toBeInTheDocument();
  });

  it('should render "15+" label for 15+ rating', () => {
    render(<AgeRatingBadge rating="15+" />);
    expect(screen.getByText(/15\+/)).toBeInTheDocument();
  });

  it('should render "18+" label for 18+ rating', () => {
    render(<AgeRatingBadge rating="18+" />);
    expect(screen.getByText(/18\+/)).toBeInTheDocument();
  });

  it('should apply green classes for "all" rating', () => {
    render(<AgeRatingBadge rating="all" />);
    const badge = screen.getByText(/전체/);
    expect(badge).toHaveClass('bg-green-900/30');
    expect(badge).toHaveClass('text-green-400');
  });

  it('should apply yellow classes for "15+" rating', () => {
    render(<AgeRatingBadge rating="15+" />);
    const badge = screen.getByText(/15\+/);
    expect(badge).toHaveClass('bg-yellow-900/30');
    expect(badge).toHaveClass('text-yellow-400');
  });

  it('should apply red classes for "18+" rating', () => {
    render(<AgeRatingBadge rating="18+" />);
    const badge = screen.getByText(/18\+/);
    expect(badge).toHaveClass('bg-red-900/30');
    expect(badge).toHaveClass('text-red-400');
  });

  it('should show lock icon when locked=true', () => {
    render(<AgeRatingBadge rating="18+" locked />);
    expect(screen.getByText(/🔒/)).toBeInTheDocument();
  });

  it('should apply opacity-50 class when locked=true', () => {
    render(<AgeRatingBadge rating="18+" locked />);
    const badge = screen.getByText(/18\+/);
    expect(badge).toHaveClass('opacity-50');
  });

  it('should apply opacity-100 class when not locked', () => {
    render(<AgeRatingBadge rating="18+" />);
    const badge = screen.getByText(/18\+/);
    expect(badge).toHaveClass('opacity-100');
  });

  it('should not show lock icon when locked=false', () => {
    render(<AgeRatingBadge rating="18+" locked={false} />);
    expect(screen.queryByText(/🔒/)).not.toBeInTheDocument();
  });
});
