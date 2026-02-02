import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { TaskNodeData, TaskStatus } from '@/types/task';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle, Loader2, XCircle, PauseCircle, Clock, Link } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const statusIcons: Record<TaskStatus, React.ReactNode> = {
  pending: <Clock className="h-4 w-4" />,
  running: <Loader2 className="h-4 w-4 animate-spin" />,
  completed: <CheckCircle2 className="h-4 w-4" />,
  failed: <XCircle className="h-4 w-4" />,
  cancelled: <Circle className="h-4 w-4" />,
  paused: <PauseCircle className="h-4 w-4" />,
};

const ChainTaskNode = memo(({ data }: NodeProps) => {
  const nodeData = data as TaskNodeData;
  const { task, onTaskClick } = nodeData;

  return (
    <div
      className={cn(
        'px-4 py-3 rounded-xl shadow-lg border-2 cursor-pointer transition-all duration-200',
        'hover:shadow-xl hover:scale-105 min-w-[180px]',
        'bg-task-chain border-task-chain-border'
      )}
      onClick={() => onTaskClick?.(task)}
    >
      <Handle type="target" position={Position.Top} className="!bg-task-chain-border !w-3 !h-3" />
      
      <div className="flex items-center gap-2 mb-2">
        <Link className="h-4 w-4 text-task-chain-accent" />
        <Badge variant="outline" className="bg-task-chain-accent/20 text-task-chain-accent border-task-chain-accent text-xs">
          Chain
        </Badge>
      </div>
      
      <div className="flex items-center gap-2">
        <span className={cn(
          'flex-shrink-0',
          task.status === 'completed' && 'text-status-completed',
          task.status === 'running' && 'text-status-running',
          task.status === 'failed' && 'text-status-failed',
          task.status === 'pending' && 'text-status-pending',
          task.status === 'paused' && 'text-status-paused',
          task.status === 'cancelled' && 'text-status-cancelled',
        )}>
          {statusIcons[task.status]}
        </span>
        <span className="font-medium text-sm text-foreground truncate">
          {task.name}
        </span>
      </div>

      {task.children_ids.length > 0 && (
        <div className="mt-2 text-xs text-muted-foreground">
          {task.children_ids.length} sequential tasks
        </div>
      )}
      
      <Handle type="source" position={Position.Bottom} className="!bg-task-chain-border !w-3 !h-3" />
    </div>
  );
});

ChainTaskNode.displayName = 'ChainTaskNode';

export default ChainTaskNode;
