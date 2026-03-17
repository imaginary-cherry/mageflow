import { Loader2 } from 'lucide-react';

interface SplashScreenProps {
  statusMessage: string;
}

export default function SplashScreen({ statusMessage }: SplashScreenProps) {
  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-gray-950 transition-opacity duration-500">
      <div className="flex flex-col items-center gap-6">
        {/* App name / branding */}
        <h1 className="text-4xl font-bold tracking-tight text-white">
          Mageflow Viewer
        </h1>

        {/* Animated spinner */}
        <Loader2 className="h-10 w-10 animate-spin text-purple-400" />

        {/* Status message */}
        <p className="text-sm text-gray-400">{statusMessage}</p>
      </div>
    </div>
  );
}
