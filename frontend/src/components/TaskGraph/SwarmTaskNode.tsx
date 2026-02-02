import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { TaskNodeData, TaskStatus } from '@/types/task';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle, Loader2, XCircle, PauseCircle, Clock, Zap } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const statusIcons: Record<TaskStatus, React.ReactNode> = {
  pending: <Clock className="h-4 w-4" />,
  running: <Loader2 className="h-4 w-4 animate-spin" />,
  completed: <CheckCircle2 className="h-4 w-4" />,
  failed: <XCircle className="h-4 w-4" />,
  cancelled: <Circle className="h-4 w-4" />,
  paused: <PauseCircle className="h-4 w-4" />,
};

const SwarmTaskNode = memo(({ data }: NodeProps) => {
  const nodeData = data as TaskNodeData;
  const { task, onTaskClick } = nodeData;

  return (
    <div
      className={cn(
        'px-4 py-3 rounded-xl shadow-lg border-2 cursor-pointer transition-all duration-200',
        'hover:shadow-xl hover:scale-105 min-w-[180px]',
        'bg-task-swarm border-task-swarm-border'
      )}
      onClick={() => onTaskClick?.(task)}
    >
      <Handle type="target" position={Position.Top} className="!bg-task-swarm-border !w-3 !h-3" />
      
      <div className="flex items-center gap-2 mb-2">
        <Zap className="h-4 w-4 text-task-swarm-accent" />
        <Badge variant="outline" className="bg-task-swarm-accent/20 text-task-swarm-accent border-task-swarm-accent text-xs">
          Swarm
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
          {task.children_ids.length} parallel tasks
        </div>
      )}
      
      <Handle type="source" position={Position.Bottom} className="!bg-task-swarm-border !w-3 !h-3" />
    </div>
  );
});

SwarmTaskNode.displayName = 'SwarmTaskNode';

export default SwarmTaskNode;
