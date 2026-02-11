import { memo } from 'react';
import { Task, TaskStatus } from '@/types/task';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle, Loader2, XCircle, PauseCircle, Clock, Link, Zap } from 'lucide-react';
import { 
  SIMPLE_TASK_WIDTH, 
  SIMPLE_TASK_HEIGHT,
  CONTAINER_PADDING,
  CONTAINER_HEADER_HEIGHT,
  CONTAINER_FOOTER_HEIGHT,
  INNER_TASK_GAP,
  TASKS_PER_PAGE,
  calculateTaskDimensions
} from './taskSizeUtils';

const statusIcons: Record<TaskStatus, React.ReactNode> = {
  pending: <Clock className="h-3.5 w-3.5" />,
  running: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
  completed: <CheckCircle2 className="h-3.5 w-3.5" />,
  failed: <XCircle className="h-3.5 w-3.5" />,
  cancelled: <Circle className="h-3.5 w-3.5" />,
  paused: <PauseCircle className="h-3.5 w-3.5" />,
};

interface InnerTaskRendererProps {
  task: Task;
  tasksMap: Record<string, Task>;
  onTaskClick?: (task: Task) => void;
  currentPage?: number;
  depth?: number;
}

const InnerTaskRenderer = memo(({ 
  task, 
  tasksMap, 
  onTaskClick,
  currentPage = 1,
  depth = 0
}: InnerTaskRendererProps) => {
  const dimensions = calculateTaskDimensions(task, tasksMap, currentPage);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onTaskClick?.(task);
  };

  if (task.type === 'simple') {
    return (
      <div
        className={cn(
          'px-3 py-2 rounded-lg border-2 cursor-pointer transition-all duration-200',
          'hover:shadow-md hover:scale-[1.02]',
          'bg-task-simple border-task-simple-border'
        )}
        style={{ width: SIMPLE_TASK_WIDTH, height: SIMPLE_TASK_HEIGHT }}
        onClick={handleClick}
      >
        <div className="flex items-center gap-2 h-full">
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
      </div>
    );
  }

  // Container task (Chain or Swarm)
  const isChain = task.type === 'chain';
  const childTasks = task.children_ids
    .map(id => tasksMap[id])
    .filter(Boolean);

  const totalPages = Math.ceil(childTasks.length / TASKS_PER_PAGE);
  const startIndex = (currentPage - 1) * TASKS_PER_PAGE;
  const paginatedChildren = childTasks.slice(startIndex, startIndex + TASKS_PER_PAGE);
  const needsPagination = childTasks.length > TASKS_PER_PAGE;

  return (
    <div
      className={cn(
        'rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200',
        'hover:shadow-lg',
        isChain ? 'bg-task-chain/50 border-task-chain-border' : 'bg-task-swarm/50 border-task-swarm-border'
      )}
      style={{ 
        width: dimensions.width, 
        height: dimensions.height,
        minWidth: SIMPLE_TASK_WIDTH + CONTAINER_PADDING * 2
      }}
      onClick={handleClick}
    >
      {/* Header */}
      <div 
        className="flex items-center gap-2 px-3"
        style={{ height: CONTAINER_HEADER_HEIGHT }}
      >
        {isChain ? (
          <Link className="h-3.5 w-3.5 text-task-chain-accent" />
        ) : (
          <Zap className="h-3.5 w-3.5 text-task-swarm-accent" />
        )}
        <span className={cn(
          'font-semibold text-xs uppercase tracking-wide',
          isChain ? 'text-task-chain-accent' : 'text-task-swarm-accent'
        )}>
          {isChain ? 'Chain' : 'Swarm'}: {task.name}
        </span>
      </div>

      {/* Children container */}
      <div 
        className={cn(
          'flex gap-3',
          isChain ? 'flex-row items-center' : 'flex-col'
        )}
        style={{ 
          padding: `0 ${CONTAINER_PADDING}px`,
          paddingBottom: needsPagination ? 0 : CONTAINER_PADDING
        }}
      >
        {paginatedChildren.map(child => (
          <InnerTaskRenderer
            key={child.id}
            task={child}
            tasksMap={tasksMap}
            onTaskClick={onTaskClick}
            currentPage={1}
            depth={depth + 1}
          />
        ))}
      </div>

      {/* Pagination footer */}
      {needsPagination && (
        <div 
          className="flex items-center justify-center gap-2 text-xs text-muted-foreground"
          style={{ height: CONTAINER_FOOTER_HEIGHT }}
        >
          <span>
            {startIndex + 1}-{Math.min(startIndex + TASKS_PER_PAGE, childTasks.length)} of {childTasks.length}
          </span>
        </div>
      )}
    </div>
  );
});

InnerTaskRenderer.displayName = 'InnerTaskRenderer';

export default InnerTaskRenderer;
