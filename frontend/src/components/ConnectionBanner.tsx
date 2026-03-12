import { AlertTriangle } from 'lucide-react';

interface ConnectionBannerProps {
  visible: boolean;
  message: string;
  onOpenSettings: () => void;
}

export default function ConnectionBanner({ visible, message, onOpenSettings }: ConnectionBannerProps) {
  return (
    <div
      className={[
        'w-full overflow-hidden transition-all duration-300 ease-in-out',
        visible ? 'max-h-16 opacity-100' : 'max-h-0 opacity-0',
      ].join(' ')}
      aria-hidden={!visible}
    >
      <div className="flex items-center gap-3 bg-amber-500/10 border-b border-amber-500/30 px-4 py-2 text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
        <span className="flex-1 text-amber-200">{message}</span>
        <button
          type="button"
          onClick={onOpenSettings}
          className="shrink-0 text-amber-400 underline hover:text-amber-300 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-1 focus:ring-offset-transparent"
        >
          Check Settings
        </button>
      </div>
    </div>
  );
}
