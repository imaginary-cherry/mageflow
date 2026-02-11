import { Task } from '@/types/task';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Pause, XCircle, RotateCcw, Link, Zap, Box } from 'lucide-react';

interface TaskDetailPanelProps {
  task: Task | null;
  onClose: () => void;
}

const typeIcons = {
  simple: Box,
  chain: Link,
  swarm: Zap,
};

const statusColors: Record<string, string> = {
  pending: 'bg-status-pending/20 text-status-pending border-status-pending',
  running: 'bg-status-running/20 text-status-running border-status-running',
  completed: 'bg-status-completed/20 text-status-completed border-status-completed',
  failed: 'bg-status-failed/20 text-status-failed border-status-failed',
  cancelled: 'bg-status-cancelled/20 text-status-cancelled border-status-cancelled',
  paused: 'bg-status-paused/20 text-status-paused border-status-paused',
};

const TaskDetailPanel = ({ task, onClose }: TaskDetailPanelProps) => {
  const TypeIcon = task ? typeIcons[task.type] : Box;

  const handlePause = () => {
    console.log('Pause task:', task?.id);
  };

  const handleCancel = () => {
    console.log('Cancel task:', task?.id);
  };

  const handleRetry = () => {
    console.log('Retry task:', task?.id);
  };

  return (
    <Sheet open={!!task} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-[400px] sm:max-w-[400px]">
        <SheetHeader>
          <div className="flex items-center gap-2 mb-2">
            <TypeIcon className="h-5 w-5 text-primary" />
            <Badge variant="outline" className="capitalize">
              {task?.type}
            </Badge>
          </div>
          <SheetTitle className="text-xl">{task?.name}</SheetTitle>
          <SheetDescription>
            Task ID: {task?.id}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Status */}
          <div>
            <h4 className="text-sm font-medium text-muted-foreground mb-2">Status</h4>
            <Badge 
              variant="outline" 
              className={cn('capitalize', task && statusColors[task.status])}
            >
              {task?.status}
            </Badge>
          </div>

          {/* Children */}
          {task && task.children_ids.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">
                {task.type === 'chain' ? 'Sequential Tasks' : 'Parallel Tasks'}
              </h4>
              <p className="text-sm">{task.children_ids.length} child tasks</p>
            </div>
          )}

          {/* Callbacks */}
          {task && (task.success_callback_ids.length > 0 || task.error_callback_ids.length > 0) && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Callbacks</h4>
              <div className="space-y-1 text-sm">
                {task.success_callback_ids.length > 0 && (
                  <p className="text-status-completed">
                    ✓ {task.success_callback_ids.length} success callback(s)
                  </p>
                )}
                {task.error_callback_ids.length > 0 && (
                  <p className="text-status-failed">
                    ✗ {task.error_callback_ids.length} error callback(s)
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Metadata */}
          {task?.metadata && Object.keys(task.metadata).length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Metadata</h4>
              <pre className="text-xs bg-muted p-3 rounded-lg overflow-auto">
                {JSON.stringify(task.metadata, null, 2)}
              </pre>
            </div>
          )}

          {/* Controls */}
          <div className="pt-4 border-t">
            <h4 className="text-sm font-medium text-muted-foreground mb-3">Actions</h4>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                size="sm"
                onClick={handlePause}
                disabled={task?.status !== 'running'}
              >
                <Pause className="h-4 w-4 mr-1" />
                Pause
              </Button>
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleCancel}
                disabled={task?.status !== 'running' && task?.status !== 'paused'}
                className="text-destructive hover:text-destructive"
              >
                <XCircle className="h-4 w-4 mr-1" />
                Cancel
              </Button>
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleRetry}
                disabled={task?.status !== 'failed'}
              >
                <RotateCcw className="h-4 w-4 mr-1" />
                Retry
              </Button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default TaskDetailPanel;
