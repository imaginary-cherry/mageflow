import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Onboarding from '@/components/Onboarding';
import { HealthCheckError } from '@/hooks/useAppStartup';

// Mock the settings store
vi.mock('@/stores/settingsStore', () => ({
  saveSettings: vi.fn().mockResolvedValue(undefined),
  isTauriEnvironment: vi.fn().mockReturnValue(false),
}));

import { saveSettings } from '@/stores/settingsStore';

describe('Onboarding', () => {
  const mockOnComplete = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnComplete.mockResolvedValue(undefined);
  });

  it('renders Hatchet API key and Redis URL fields', () => {
    render(<Onboarding onComplete={mockOnComplete} />);

    expect(screen.getByLabelText('Hatchet API Key')).toBeInTheDocument();
    expect(screen.getByLabelText('Redis URL')).toBeInTheDocument();
  });

  it('shows validation error for empty Hatchet API key', async () => {
    render(<Onboarding onComplete={mockOnComplete} />);

    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.clear(hatchetInput);

    // Clear the default Redis URL and type a valid one to isolate hatchet validation
    const redisInput = screen.getByLabelText('Redis URL');
    await user.clear(redisInput);
    await user.type(redisInput, 'redis://localhost:6379');

    const submitButton = screen.getByRole('button', { name: /connect/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Hatchet API key is required')).toBeInTheDocument();
    });
  });

  it('shows validation error for invalid Redis URL', async () => {
    render(<Onboarding onComplete={mockOnComplete} />);

    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.type(hatchetInput, 'some-api-key');

    const redisInput = screen.getByLabelText('Redis URL');
    await user.clear(redisInput);
    await user.type(redisInput, 'not-a-url');

    const submitButton = screen.getByRole('button', { name: /connect/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/redis:\/\/ or rediss:\/\//i)).toBeInTheDocument();
    });
  });

  it('calls onComplete after successful save', async () => {
    render(<Onboarding onComplete={mockOnComplete} />);

    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.type(hatchetInput, 'valid-api-key');

    // Redis URL already has default value 'redis://localhost:6379'
    const submitButton = screen.getByRole('button', { name: /connect/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(saveSettings).toHaveBeenCalledWith({
        hatchetApiKey: 'valid-api-key',
        redisUrl: 'redis://localhost:6379',
      });
      expect(mockOnComplete).toHaveBeenCalled();
    });
  });

  it('disables submit button while saving', async () => {
    // Use a delayed saveSettings to keep isValidating true
    let resolveSettings: () => void;
    const settingsPromise = new Promise<void>((resolve) => {
      resolveSettings = resolve;
    });
    vi.mocked(saveSettings).mockReturnValue(settingsPromise);

    // Also make onComplete hang
    let resolveComplete: () => void;
    const completePromise = new Promise<void>((resolve) => {
      resolveComplete = resolve;
    });
    mockOnComplete.mockReturnValue(completePromise);

    render(<Onboarding onComplete={mockOnComplete} />);

    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.type(hatchetInput, 'valid-api-key');

    const submitButton = screen.getByRole('button', { name: /connect/i });
    await user.click(submitButton);

    // Button should show validating state
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /validating/i })).toBeDisabled();
    });

    // Resolve to clean up
    resolveSettings!();
    resolveComplete!();
  });

  it('shows inline per-service errors when onComplete throws HealthCheckError', async () => {
    mockOnComplete.mockRejectedValue(
      new HealthCheckError(
        'Health check failed',
        'Hatchet auth failed',
        'Redis connection refused',
      ),
    );

    render(<Onboarding onComplete={mockOnComplete} />);

    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.type(hatchetInput, 'bad-api-key');

    const submitButton = screen.getByRole('button', { name: /connect/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Hatchet auth failed')).toBeInTheDocument();
      expect(screen.getByText('Redis connection refused')).toBeInTheDocument();
    });
  });
});
