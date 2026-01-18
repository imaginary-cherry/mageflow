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
  } = data;

  const showPagination = pagination && pagination.totalPages > 1;

  return (
    <div className={styles.chainNode}>
      <Handle
        type="target"
        position={Position.Left}
        className={styles.chainHandle}
      />

      <div className={styles.chainHeader}>Chain: {label}</div>

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

      <Handle
        type="source"
        position={Position.Right}
        className={styles.chainHandleSource}
      />
    </div>
  );
};