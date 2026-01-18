import React from 'react';
import { Handle, Position } from 'reactflow';
import styles from './CustomNodes.module.css';

export const TaskNode = ({ data }) => {
  return (
    <div className={styles.taskNode}>
      <Handle
        type="target"
        position={Position.Left}
        className={styles.handle}
      />

      <div className={styles.taskLabel}>{data.label}</div>

      {(data.hasSuccessCallbacks || data.hasErrorCallbacks) && (
        <>
          {data.hasSuccessCallbacks && (
            <Handle
              type="source"
              position={Position.Right}
              id="success"
              className={styles.handleSuccess}
            />
          )}
          {data.hasErrorCallbacks && (
            <Handle
              type="source"
              position={Position.Right}
              id="error"
              className={styles.handleError}
            />
          )}
        </>
      )}
    </div>
  );
};

export const ErrorNode = ({ data }) => {
  return (
    <div className={styles.errorNode}>
      <Handle 
        type="target" 
        position={Position.Left}
        className={styles.handleErrorTarget}
      />
      
      <div>⚠️ {data.label}</div>
      
      {data.hasSuccessCallbacks && (
        <Handle
          type="source"
          position={Position.Right}
          className={styles.handleError}
        />
      )}
    </div>
  );
};