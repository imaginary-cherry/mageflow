import { memo, useState, useCallback } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Task, TaskStatus } from '@/types/task';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle, Loader2, XCircle, PauseCircle, Clock, Link, Zap, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { mockTasks } from '@/data/mockTasks';
import { 
  CONTAINER_PADDING,
  CONTAINER_HEADER_HEIGHT,
  CONTAINER_FOOTER_HEIGHT,
  TASKS_PER_PAGE,
  calculateTaskDimensions
} from './taskSizeUtils';
import InnerTaskRenderer from './InnerTaskRenderer';

const statusIcons: Record<TaskStatus, React.ReactNode> = {
  pending: <Clock className="h-4 w-4" />,
  running: <Loader2 className="h-4 w-4 animate-spin" />,
  completed: <CheckCircle2 className="h-4 w-4" />,
  failed: <XCircle className="h-4 w-4" />,
  cancelled: <Circle className="h-4 w-4" />,
  paused: <PauseCircle className="h-4 w-4" />,
};

export interface ContainerNodeData extends Record<string, unknown> {
  task: Task;
  onTaskClick?: (task: Task) => void;
  width: number;
  height: number;
}

const ContainerTaskNode = memo(({ data }: NodeProps) => {
  const nodeData = data as ContainerNodeData;
  const { task, onTaskClick, width, height } = nodeData;
  const [currentPage, setCurrentPage] = useState(1);
  
  const isChain = task.type === 'chain';
  
  const childTasks = task.children_ids
    .map(id => mockTasks[id])
    .filter(Boolean);
  
  const totalPages = Math.ceil(childTasks.length / TASKS_PER_PAGE);
  const startIndex = (currentPage - 1) * TASKS_PER_PAGE;
  const paginatedChildren = childTasks.slice(startIndex, startIndex + TASKS_PER_PAGE);
  const needsPagination = childTasks.length > TASKS_PER_PAGE;

  const handlePageChange = useCallback((newPage: number) => {
    setCurrentPage(Math.max(1, Math.min(newPage, totalPages)));
  }, [totalPages]);

  // Recalculate dimensions for current page
  const currentDimensions = calculateTaskDimensions(task, mockTasks, currentPage);

  return (
    <div
      className={cn(
        'rounded-2xl border-2 border-dashed shadow-lg cursor-pointer transition-all duration-200',
        'hover:shadow-xl',
        isChain 
          ? 'bg-task-chain/30 border-task-chain-border' 
          : 'bg-task-swarm/30 border-task-swarm-border'
      )}
      style={{ 
        width: currentDimensions.width, 
        height: currentDimensions.height,
      }}
      onClick={(e) => {
        // Only trigger if clicking the container itself, not children
        if (e.target === e.currentTarget || (e.target as HTMLElement).closest('.container-header')) {
          onTaskClick?.(task);
        }
      }}
    >
      <Handle 
        type="target" 
        position={Position.Top} 
        className={cn(
          '!w-3 !h-3',
          isChain ? '!bg-task-chain-border' : '!bg-task-swarm-border'
        )} 
      />
      
      {/* Header */}
      <div 
        className="container-header flex items-center gap-2 px-4"
        style={{ height: CONTAINER_HEADER_HEIGHT }}
      >
        {isChain ? (
          <Link className="h-4 w-4 text-task-chain-accent" />
        ) : (
          <Zap className="h-4 w-4 text-task-swarm-accent" />
        )}
        <span className={cn(
          'font-bold text-sm uppercase tracking-wide',
          isChain ? 'text-task-chain-accent' : 'text-task-swarm-accent'
        )}>
          {isChain ? 'Chain' : 'Swarm'}: {task.name}
        </span>
        <span className={cn(
          'ml-auto flex-shrink-0',
          task.status === 'completed' && 'text-status-completed',
          task.status === 'running' && 'text-status-running',
          task.status === 'failed' && 'text-status-failed',
          task.status === 'pending' && 'text-status-pending',
          task.status === 'paused' && 'text-status-paused',
          task.status === 'cancelled' && 'text-status-cancelled',
        )}>
          {statusIcons[task.status]}
        </span>
      </div>

      {/* Children container */}
      <div 
        className={cn(
          'flex',
          isChain ? 'flex-row items-center' : 'flex-col',
        )}
        style={{ 
          padding: `0 ${CONTAINER_PADDING}px`,
          gap: `${12}px`,
          paddingBottom: needsPagination ? 0 : CONTAINER_PADDING
        }}
      >
        {paginatedChildren.map(child => (
          <InnerTaskRenderer
            key={child.id}
            task={child}
            tasksMap={mockTasks}
            onTaskClick={onTaskClick}
            currentPage={1}
            depth={1}
          />
        ))}
      </div>

      {/* Pagination footer */}
      {needsPagination && (
        <div 
          className="flex items-center justify-center gap-1 px-2"
          style={{ height: CONTAINER_FOOTER_HEIGHT }}
        >
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={(e) => { e.stopPropagation(); handlePageChange(1); }}
            disabled={currentPage === 1}
          >
            <ChevronsLeft className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={(e) => { e.stopPropagation(); handlePageChange(currentPage - 1); }}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-3 w-3" />
          </Button>
          <span className="text-xs text-muted-foreground px-2">
            {startIndex + 1}-{Math.min(startIndex + TASKS_PER_PAGE, childTasks.length)} of {childTasks.length}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={(e) => { e.stopPropagation(); handlePageChange(currentPage + 1); }}
            disabled={currentPage === totalPages}
          >
            <ChevronRight className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={(e) => { e.stopPropagation(); handlePageChange(totalPages); }}
            disabled={currentPage === totalPages}
          >
            <ChevronsRight className="h-3 w-3" />
          </Button>
        </div>
      )}
      
      <Handle 
        type="source" 
        position={Position.Bottom} 
        className={cn(
          '!w-3 !h-3',
          isChain ? '!bg-task-chain-border' : '!bg-task-swarm-border'
        )} 
      />
    </div>
  );
});

ContainerTaskNode.displayName = 'ContainerTaskNode';

export default ContainerTaskNode;
