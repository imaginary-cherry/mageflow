import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SettingsDialog from '@/components/SettingsDialog';

// Mock the settings store
vi.mock('@/stores/settingsStore', () => ({
  loadSettings: vi.fn().mockResolvedValue(null),
  saveSettings: vi.fn().mockResolvedValue(undefined),
  isTauriEnvironment: vi.fn().mockReturnValue(false),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { loadSettings, saveSettings } from '@/stores/settingsStore';
import { toast } from 'sonner';

describe('SettingsDialog', () => {
  const mockOnOpenChange = vi.fn();
  const mockOnSave = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnSave.mockResolvedValue(undefined);
  });

  it('loads and displays current settings when opened', async () => {
    vi.mocked(loadSettings).mockResolvedValue({
      hatchetApiKey: 'existing-key',
      redisUrl: 'redis://my-redis:6379',
    });

    render(
      <SettingsDialog open={true} onOpenChange={mockOnOpenChange} onSave={mockOnSave} />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Hatchet API Key')).toHaveValue('existing-key');
      expect(screen.getByLabelText('Redis URL')).toHaveValue('redis://my-redis:6379');
    });
  });

  it('validates fields before saving', async () => {
    vi.mocked(loadSettings).mockResolvedValue(null);

    render(
      <SettingsDialog open={true} onOpenChange={mockOnOpenChange} onSave={mockOnSave} />,
    );

    // Clear the hatchet key field
    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.clear(hatchetInput);

    // Ensure Redis URL is valid
    const redisInput = screen.getByLabelText('Redis URL');
    await user.clear(redisInput);
    await user.type(redisInput, 'redis://localhost:6379');

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText('Hatchet API key is required')).toBeInTheDocument();
    });

    expect(saveSettings).not.toHaveBeenCalled();
  });

  it('calls onSave after saving new settings', async () => {
    vi.mocked(loadSettings).mockResolvedValue(null);

    render(
      <SettingsDialog open={true} onOpenChange={mockOnOpenChange} onSave={mockOnSave} />,
    );

    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.type(hatchetInput, 'new-api-key');

    // Redis URL has default value
    const saveButton = screen.getByRole('button', { name: /save settings/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(saveSettings).toHaveBeenCalledWith({
        hatchetApiKey: 'new-api-key',
        redisUrl: 'redis://localhost:6379',
      });
      expect(mockOnSave).toHaveBeenCalled();
    });
  });

  it('closes dialog on cancel without saving', async () => {
    vi.mocked(loadSettings).mockResolvedValue(null);

    render(
      <SettingsDialog open={true} onOpenChange={mockOnOpenChange} onSave={mockOnSave} />,
    );

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    expect(saveSettings).not.toHaveBeenCalled();
  });

  it('shows success toast after save', async () => {
    vi.mocked(loadSettings).mockResolvedValue(null);

    render(
      <SettingsDialog open={true} onOpenChange={mockOnOpenChange} onSave={mockOnSave} />,
    );

    const hatchetInput = screen.getByLabelText('Hatchet API Key');
    await user.type(hatchetInput, 'toast-test-key');

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('saved'));
    });
  });
});
