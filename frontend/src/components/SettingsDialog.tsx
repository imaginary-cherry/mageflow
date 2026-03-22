import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { loadSettings, validateCredentials, saveSettings, isTauriEnvironment } from '@/stores/settingsStore';

const settingsSchema = z.object({
  hatchetApiKey: z.string().min(1, 'Hatchet API key is required'),
  redisUrl: z
    .string()
    .min(1, 'Redis URL is required')
    .refine(
      (val) => val.startsWith('redis://') || val.startsWith('rediss://'),
      'Redis URL must start with redis:// or rediss://'
    ),
});

type SettingsFormValues = z.infer<typeof settingsSchema>;

export interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const [isValidating, setIsValidating] = useState(false);

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      hatchetApiKey: '',
      redisUrl: 'redis://localhost:6379',
    },
  });

  // Load current settings into form when dialog opens
  useEffect(() => {
    if (!open) return;
    loadSettings().then((settings) => {
      if (settings) {
        form.reset({
          hatchetApiKey: settings.hatchetApiKey,
          redisUrl: settings.redisUrl,
        });
      }
    });
  }, [open, form]);

  const onSubmit = async (values: SettingsFormValues) => {
    setIsValidating(true);
    try {
      const result = await validateCredentials(values);
      if (!result.valid) {
        if (result.hatchetError) {
          form.setError('hatchetApiKey', { message: result.hatchetError });
        }
        if (result.redisError) {
          form.setError('redisUrl', { message: result.redisError });
        }
        return;
      }

      await saveSettings(values);

      if (isTauriEnvironment()) {
        try {
          const { invoke } = await import('@tauri-apps/api/core');
          await invoke('restart_sidecar');
        } catch {
          // restart_sidecar may not exist yet — non-fatal during development
        }
      }

      toast.success('Settings saved successfully');
      onOpenChange(false);
    } finally {
      setIsValidating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Update your Hatchet and Redis connection credentials.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="hatchetApiKey"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Hatchet API Key</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      type="text"
                      placeholder="Enter your Hatchet API key"
                      disabled={isValidating}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="redisUrl"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Redis URL</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      type="text"
                      placeholder="redis://localhost:6379"
                      disabled={isValidating}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isValidating}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isValidating}>
                {isValidating ? 'Validating...' : 'Save Settings'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
