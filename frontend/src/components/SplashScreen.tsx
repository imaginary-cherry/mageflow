import { Loader2 } from 'lucide-react';

interface SplashScreenProps {
  statusMessage: string;
}

export default function SplashScreen({ statusMessage }: SplashScreenProps) {
  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-background transition-opacity duration-500">
      <div className="flex flex-col items-center gap-6">
        {/* App name / branding */}
        <h1 className="text-4xl font-bold tracking-tight text-foreground">
          Mage Voyance
        </h1>

        {/* Animated spinner */}
        <Loader2 className="h-10 w-10 animate-spin text-primary" />

        {/* Status message */}
        <p className="text-sm text-muted-foreground">{statusMessage}</p>
      </div>
    </div>
  );
}
