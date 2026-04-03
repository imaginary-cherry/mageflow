import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ConnectionBanner from '@/components/ConnectionBanner';

describe('ConnectionBanner', () => {
  const mockOnOpenSettings = vi.fn();

  it('renders warning message when visible is true', () => {
    render(
      <ConnectionBanner visible={true} message="Connection lost" onOpenSettings={mockOnOpenSettings} />,
    );

    expect(screen.getByText('Connection lost')).toBeInTheDocument();
  });

  it('does not render when visible is false', () => {
    const { container } = render(
      <ConnectionBanner visible={false} message="hidden msg" onOpenSettings={mockOnOpenSettings} />,
    );

    // The component uses aria-hidden="true" when not visible
    const banner = container.firstElementChild;
    expect(banner).toHaveAttribute('aria-hidden', 'true');
  });

  it('calls onOpenSettings when Check Settings clicked', async () => {
    const user = userEvent.setup();

    render(
      <ConnectionBanner visible={true} message="test" onOpenSettings={mockOnOpenSettings} />,
    );

    const button = screen.getByRole('button', { name: /check settings/i });
    await user.click(button);

    expect(mockOnOpenSettings).toHaveBeenCalled();
  });

  it('displays the provided message text', () => {
    render(
      <ConnectionBanner visible={true} message="Custom error message" onOpenSettings={mockOnOpenSettings} />,
    );

    expect(screen.getByText('Custom error message')).toBeInTheDocument();
  });
});
