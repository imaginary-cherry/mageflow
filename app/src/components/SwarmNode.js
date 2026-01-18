import React from 'react';
import { Handle, Position } from 'reactflow';
import styles from './SwarmNode.module.css';
import { PaginationControls } from './PaginationControls';

export const SwarmNode = ({ data }) => {
  const {
    label,
    hasSuccessCallbacks,
    hasErrorCallbacks,
    pagination,
    onPrevPage,
    onNextPage,
    onFirstPage,
    onLastPage,
  } = data;

  const showPagination = pagination && pagination.totalPages > 1;

  return (
    <div className={styles.swarmNode}>
      <Handle
        type="target"
        position={Position.Left}
        className={styles.swarmHandle}
      />

      <div className={styles.swarmHeader}>Swarm: {label}</div>

      {showPagination && (
        <PaginationControls
          currentPage={pagination.currentPage}
          totalPages={pagination.totalPages}
          totalItems={pagination.totalItems}
          pageSize={pagination.pageSize}
          onPrevPage={onPrevPage}
          onNextPage={onNextPage}
          onFirstPage={onFirstPage}
          onLastPage={onLastPage}
        />
      )}

      {hasSuccessCallbacks && (
        <Handle
          type="source"
          position={Position.Right}
          id="success"
          className={styles.swarmHandleSuccess}
          style={{ top: '40%' }}
        />
      )}

      {hasErrorCallbacks && (
        <Handle
          type="source"
          position={Position.Right}
          id="error"
          className={styles.swarmHandleError}
          style={{ top: '60%' }}
        />
      )}
    </div>
  );
};
