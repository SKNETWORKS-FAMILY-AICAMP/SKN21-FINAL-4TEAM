import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AdultVerifyModal } from './AdultVerifyModal';

describe('AdultVerifyModal', () => {
  it('should not render when isOpen is false', () => {
    render(<AdultVerifyModal isOpen={false} onClose={vi.fn()} onVerified={vi.fn()} />);
    expect(screen.queryByText('성인인증')).not.toBeInTheDocument();
  });

  it('should render when isOpen is true', () => {
    render(<AdultVerifyModal isOpen={true} onClose={vi.fn()} onVerified={vi.fn()} />);
    expect(screen.getByText('성인인증')).toBeInTheDocument();
  });

  it('should render modal overlay', () => {
    render(<AdultVerifyModal isOpen={true} onClose={vi.fn()} onVerified={vi.fn()} />);
    const overlay = document.querySelector('.modal-overlay');
    expect(overlay).toBeInTheDocument();
  });
});
