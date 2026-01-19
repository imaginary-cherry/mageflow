import React from 'react';
import { Handle, Position } from 'reactflow';
import styles from './ChainNode.module.css';
import { PaginationControls } from './PaginationControls';

export const ChainNode = ({ data }) => {
  const {
    label,
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
    <div className={styles.chainNode}>
      <Handle
        type="target"
        position={Position.Left}
        className={styles.chainHandle}
      />

      <div className={styles.chainHeader}>
        Chain: {label}
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

      <Handle
        type="source"
        position={Position.Right}
        className={styles.chainHandleSource}
      />
    </div>
  );
};
