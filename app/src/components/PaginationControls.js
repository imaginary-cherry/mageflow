import React from 'react';
import styles from './PaginationControls.module.css';

export const PaginationControls = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPrevPage,
  onNextPage,
  onFirstPage,
  onLastPage,
}) => {
  const startItem = currentPage * pageSize + 1;
  const endItem = Math.min((currentPage + 1) * pageSize, totalItems);
  const hasPrev = currentPage > 0;
  const hasNext = currentPage < totalPages - 1;

  const handleClick = (e, callback) => {
    e.stopPropagation();
    callback();
  };

  return (
    <div className={styles.paginationContainer}>
      <button
        className={styles.pageButton}
        onClick={(e) => handleClick(e, onFirstPage)}
        disabled={!hasPrev}
        title="First page"
      >
        ««
      </button>
      <button
        className={styles.pageButton}
        onClick={(e) => handleClick(e, onPrevPage)}
        disabled={!hasPrev}
        title="Previous page"
      >
        «
      </button>

      <span className={styles.pageInfo}>
        {startItem}-{endItem} of {totalItems}
      </span>

      <button
        className={styles.pageButton}
        onClick={(e) => handleClick(e, onNextPage)}
        disabled={!hasNext}
        title="Next page"
      >
        »
      </button>
      <button
        className={styles.pageButton}
        onClick={(e) => handleClick(e, onLastPage)}
        disabled={!hasNext}
        title="Last page"
      >
        »»
      </button>
    </div>
  );
};
