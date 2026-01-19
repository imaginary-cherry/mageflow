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
    isChildrenLoading,
    totalChildren,
    isCallbacksLoading,
    showLoadMoreButton,
    onLoadMore,
  } = data;

  const showPagination = pagination && pagination.totalPages > 1;
  const isLoading = isChildrenLoading || isCallbacksLoading;

  return (
    <div className={styles.swarmNode}>
      <Handle
        type="target"
        position={Position.Left}
        className={styles.swarmHandle}
      />

      <div className={styles.swarmHeader}>
        Swarm: {label}
        {totalChildren > 0 && <span className={styles.childCount}> ({totalChildren})</span>}
      </div>

      {isLoading && (
        <div className={styles.loadingSpinner}>Loading...</div>
      )}

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

      {showLoadMoreButton && !isLoading && (
        <button className={styles.loadButton} onClick={onLoadMore}>
          Load More
        </button>
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
