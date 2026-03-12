import { useEffect, useRef, useState } from 'react';
import { Toaster } from '@/components/ui/toaster';
import { Toaster as Sonner, toast } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { TaskClientProvider, HttpTaskClient } from '@/services';
import { Settings } from 'lucide-react';
import { isTauriEnvironment } from '@/stores/settingsStore';
import { useAppStartup } from '@/hooks/useAppStartup';
import SplashScreen from '@/components/SplashScreen';
import ConnectionBanner from '@/components/ConnectionBanner';
import Onboarding from '@/components/Onboarding';
import SettingsDialog from '@/components/SettingsDialog';
import Index from './pages/Index';
import NotFound from './pages/NotFound';

const queryClient = new QueryClient();

// Startup-error screen shown when the backend cannot start or services are unreachable.
function StartupErrorScreen({
  errorMessage,
  onRetry,
  onOpenSettings,
}: {
  errorMessage: string;
  onRetry: () => void;
  onOpenSettings: () => void;
}) {
  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-gray-950 text-white gap-4">
      <h2 className="text-2xl font-semibold">Startup Failed</h2>
      <p className="text-gray-400 text-sm max-w-sm text-center">{errorMessage}</p>
      <div className="flex gap-3 mt-2">
        <button
          type="button"
          onClick={onRetry}
          className="px-4 py-2 rounded-md bg-indigo-600 hover:bg-indigo-500 text-sm font-medium transition-colors"
        >
          Retry
        </button>
        <button
          type="button"
          onClick={onOpenSettings}
          className="px-4 py-2 rounded-md bg-gray-700 hover:bg-gray-600 text-sm font-medium transition-colors"
        >
          Settings
        </button>
      </div>
    </div>
  );
}

// Main app content once startup is complete.
function MainApp({
  port,
  onOpenSettings,
  settingsOpen,
  setSettingsOpen,
  retrySidecar,
}: {
  port: number;
  onOpenSettings: () => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  retrySidecar: () => Promise<void>;
}) {
  const taskClient = useRef(new HttpTaskClient(`http://127.0.0.1:${port}`)).current;

  // Post-launch health banner state
  const [bannerVisible, setBannerVisible] = useState(false);
  const [bannerMessage, setBannerMessage] = useState('');

  // Sidecar crash detection and periodic health polling
  useEffect(() => {
    let sidecarExitUnlisten: (() => void) | null = null;
    let healthInterval: ReturnType<typeof setInterval> | null = null;
    let crashed = false;

    // Listen for sidecar-exit event from Tauri (if Rust emits it)
    async function setupSidecarExitListener() {
      if (!isTauriEnvironment()) return;
      try {
        const { listen } = await import('@tauri-apps/api/event');
        sidecarExitUnlisten = await listen('sidecar-exit', () => {
          if (crashed) return;
          crashed = true;
          void updateTray('disconnected');
          toast.error('Backend stopped unexpectedly', {
            action: {
              label: 'Restart',
              onClick: () => {
                crashed = false;
                void retrySidecar();
              },
            },
            duration: Infinity,
          });
        });
      } catch {
        // listen unavailable — fall through to polling
      }
    }

    async function updateTray(status: string) {
      if (!isTauriEnvironment()) return;
      try {
        const { invoke } = await import('@tauri-apps/api/core');
        await invoke('set_tray_status', { status });
      } catch {
        // ignore tray errors
      }
    }

    async function checkHealth() {
      try {
        const resp = await fetch(`http://127.0.0.1:${port}/api/health`);
        if (resp.ok) {
          if (bannerVisible) {
            setBannerVisible(false);
            void updateTray('connected');
          }
        } else {
          throw new Error(`HTTP ${resp.status}`);
        }
      } catch {
        setBannerMessage('Unable to reach backend service');
        setBannerVisible(true);
        void updateTray('disconnected');
      }
    }

    void setupSidecarExitListener();
    healthInterval = setInterval(() => { void checkHealth(); }, 30_000);

    return () => {
      if (sidecarExitUnlisten) sidecarExitUnlisten();
      if (healthInterval) clearInterval(healthInterval);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port]);

  return (
    <QueryClientProvider client={queryClient}>
      <TaskClientProvider client={taskClient}>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <div className="flex flex-col min-h-screen">
            {/* Persistent connection warning banner */}
            <ConnectionBanner
              visible={bannerVisible}
              message={bannerMessage}
              onOpenSettings={onOpenSettings}
            />

            {/* Minimal header with settings gear */}
            <header className="flex items-center justify-end px-4 py-2 border-b border-gray-800 bg-gray-950">
              <button
                type="button"
                onClick={onOpenSettings}
                aria-label="Open settings"
                className="p-2 rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
              >
                <Settings className="h-5 w-5" />
              </button>
            </header>

            <main className="flex-1">
              <BrowserRouter>
                <Routes>
                  <Route path="/" element={<Index />} />
                  {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </BrowserRouter>
            </main>
          </div>

          <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
        </TooltipProvider>
      </TaskClientProvider>
    </QueryClientProvider>
  );
}

// Root component — gates all UI on startup phase.
const App = () => {
  const { phase, port, statusMessage, errorMessage, onOnboardingComplete, retrySidecar } =
    useAppStartup();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const isSplashPhase =
    phase === 'loading-settings' ||
    phase === 'starting-sidecar' ||
    phase === 'connecting-hatchet' ||
    phase === 'connecting-redis';

  return (
    <>
      {/* Splash phases */}
      <div
        className={`transition-opacity duration-500 ease-in-out ${
          isSplashPhase ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none fixed inset-0'
        }`}
      >
        {isSplashPhase && <SplashScreen statusMessage={statusMessage} />}
      </div>

      {/* Onboarding */}
      {phase === 'onboarding' && (
        <Onboarding onComplete={onOnboardingComplete} />
      )}

      {/* Startup error */}
      {phase === 'startup-error' && (
        <StartupErrorScreen
          errorMessage={errorMessage}
          onRetry={retrySidecar}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      )}

      {/* Startup error also shows settings dialog */}
      {phase === 'startup-error' && (
        <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      )}

      {/* Main UI — fades in when ready */}
      <div
        className={`transition-opacity duration-500 ease-in-out ${
          phase === 'ready' ? 'opacity-100' : 'opacity-0 pointer-events-none fixed inset-0'
        }`}
      >
        {phase === 'ready' && (
          <MainApp
            port={port}
            onOpenSettings={() => setSettingsOpen(true)}
            settingsOpen={settingsOpen}
            setSettingsOpen={setSettingsOpen}
            retrySidecar={retrySidecar}
          />
        )}
      </div>
    </>
  );
};

export default App;
