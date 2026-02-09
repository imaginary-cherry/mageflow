import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Box, Link, Zap } from 'lucide-react';

interface TaskGraphHeaderProps {
  onRefresh?: () => void;
}

const TaskGraphHeader = ({ onRefresh }: TaskGraphHeaderProps) => {
  return (
    <header className="h-16 border-b bg-card/80 backdrop-blur-sm flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-purple-500 bg-clip-text text-transparent">
          Task Graph
        </h1>
        
        <div className="h-6 w-px bg-border" />
        
        {/* Legend */}
        <div className="flex items-center gap-3 text-sm">
          <div className="flex items-center gap-1.5">
            <Box className="h-4 w-4 text-task-simple-accent" />
            <span className="text-muted-foreground">Simple</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Link className="h-4 w-4 text-task-chain-accent" />
            <span className="text-muted-foreground">Chain</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Zap className="h-4 w-4 text-task-swarm-accent" />
            <span className="text-muted-foreground">Swarm</span>
          </div>
        </div>

        <div className="h-6 w-px bg-border" />

        {/* Status Legend */}
        <div className="flex items-center gap-2 text-xs">
          <Badge variant="outline" className="bg-status-completed/20 text-status-completed border-status-completed">
            Completed
          </Badge>
          <Badge variant="outline" className="bg-status-running/20 text-status-running border-status-running">
            Running
          </Badge>
          <Badge variant="outline" className="bg-status-pending/20 text-status-pending border-status-pending">
            Pending
          </Badge>
          <Badge variant="outline" className="bg-status-failed/20 text-status-failed border-status-failed">
            Failed
          </Badge>
        </div>
      </div>

      <Button variant="outline" size="sm" onClick={onRefresh}>
        <RefreshCw className="h-4 w-4 mr-2" />
        Refresh
      </Button>
    </header>
  );
};

export default TaskGraphHeader;
