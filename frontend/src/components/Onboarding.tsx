import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { validateCredentials, saveSettings } from '@/stores/settingsStore';

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
  onComplete: () => void;
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
      onComplete();
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
