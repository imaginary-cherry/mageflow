import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { saveSettings } from '@/stores/settingsStore';
import { HealthCheckError } from '@/hooks/useAppStartup';

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

interface OnboardingProps {
  onComplete: () => Promise<void>;
}

export default function Onboarding({ onComplete }: OnboardingProps) {
  const [isValidating, setIsValidating] = useState(false);

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      hatchetApiKey: '',
      redisUrl: 'redis://localhost:6379',
    },
  });

  const onSubmit = async (values: SettingsFormValues) => {
    setIsValidating(true);
    try {
      await saveSettings(values);
      await onComplete();
      // If onComplete succeeds, health check passed -- app transitions to ready
    } catch (err) {
      if (err instanceof HealthCheckError) {
        // Per user decision: show per-service errors inline on the form
        if (err.hatchetError) {
          form.setError('hatchetApiKey', { message: err.hatchetError });
        }
        if (err.redisError) {
          form.setError('redisUrl', { message: err.redisError });
        }
        // Credentials remain saved per user decision
      }
      // For non-HealthCheckError (e.g. sidecar spawn failure), the error
      // message is generic -- show it on the first field as a fallback
      else if (err instanceof Error) {
        form.setError('hatchetApiKey', { message: err.message });
      }
    } finally {
      setIsValidating(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center space-y-2">
          <CardTitle className="text-2xl font-bold">Mage Voyance</CardTitle>
          <CardDescription>
            Connect to your infrastructure to get started.
          </CardDescription>
        </CardHeader>
        <CardContent>
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

              <Button type="submit" className="w-full" disabled={isValidating}>
                {isValidating ? 'Validating...' : 'Connect'}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
