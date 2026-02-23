import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AgeGateModal } from './AgeGateModal';

describe('AgeGateModal', () => {
  it('should not render when isOpen is false', () => {
    render(<AgeGateModal isOpen={false} onClose={vi.fn()} onVerify={vi.fn()} />);
    expect(screen.queryByText('18+ 콘텐츠')).not.toBeInTheDocument();
  });

  it('should render when isOpen is true', () => {
    render(<AgeGateModal isOpen={true} onClose={vi.fn()} onVerify={vi.fn()} />);
    expect(screen.getByText('18+ 콘텐츠')).toBeInTheDocument();
  });

  it('should display adult verification required message', () => {
    render(<AgeGateModal isOpen={true} onClose={vi.fn()} onVerify={vi.fn()} />);
    expect(screen.getByText(/성인인증이 필요합니다/)).toBeInTheDocument();
  });

  it('should call onVerify when verify button is clicked', () => {
    const onVerify = vi.fn();
    render(<AgeGateModal isOpen={true} onClose={vi.fn()} onVerify={onVerify} />);
    fireEvent.click(screen.getByText('성인인증 하기'));
    expect(onVerify).toHaveBeenCalledOnce();
  });

  it('should call onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(<AgeGateModal isOpen={true} onClose={onClose} onVerify={vi.fn()} />);
    fireEvent.click(screen.getByText('닫기'));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
