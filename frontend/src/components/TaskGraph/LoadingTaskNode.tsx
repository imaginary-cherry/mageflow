import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Loader2 } from 'lucide-react';

const LoadingTaskNode = memo(() => {
  return (
    <div className="px-4 py-3 rounded-xl border-2 border-dashed border-muted-foreground/30 bg-muted/50 flex items-center gap-2 animate-pulse" style={{ width: 200, height: 60 }}>
      <Handle type="target" position={Position.Top} className="!w-3 !h-3 !bg-muted-foreground/30" />
      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      <span className="text-sm text-muted-foreground">Loading...</span>
      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !bg-muted-foreground/30" />
    </div>
  );
});

LoadingTaskNode.displayName = 'LoadingTaskNode';

export default LoadingTaskNode;
