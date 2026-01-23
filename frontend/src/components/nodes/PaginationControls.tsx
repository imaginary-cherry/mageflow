/**
 * PaginationControls Component
 *
 * Reusable pagination controls for container nodes.
 */

import React, { memo, useCallback } from 'react';
import './PaginationControls.css';

// ============================================================================
// Types
// ============================================================================

interface PaginationControlsProps {
  currentPage: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  isLoading?: boolean;
}

// ============================================================================
// PaginationControls Component
// ============================================================================

export const PaginationControls = memo(function PaginationControls({
  currentPage,
  totalPages,
  totalCount,
  pageSize,
  onPageChange,
  isLoading = false,
}: PaginationControlsProps) {
  const isFirstPage = currentPage === 0;
  const isLastPage = currentPage >= totalPages - 1;

  const startItem = currentPage * pageSize + 1;
  const endItem = Math.min((currentPage + 1) * pageSize, totalCount);

  const handlePrevious = useCallback(() => {
    if (!isFirstPage && !isLoading) {
      onPageChange(currentPage - 1);
    }
  }, [currentPage, isFirstPage, isLoading, onPageChange]);

  const handleNext = useCallback(() => {
    if (!isLastPage && !isLoading) {
      onPageChange(currentPage + 1);
    }
  }, [currentPage, isLastPage, isLoading, onPageChange]);

  const handleFirst = useCallback(() => {
    if (!isFirstPage && !isLoading) {
      onPageChange(0);
    }
  }, [isFirstPage, isLoading, onPageChange]);

  const handleLast = useCallback(() => {
    if (!isLastPage && !isLoading) {
      onPageChange(totalPages - 1);
    }
  }, [isLastPage, isLoading, totalPages, onPageChange]);

  return (
    <div className="pagination">
      <div className="pagination__info">
        <span className="pagination__range">
          {startItem}-{endItem}
        </span>
        <span className="pagination__total">of {totalCount}</span>
      </div>

      <div className="pagination__controls">
        {/* First page button */}
        <button
          className="pagination__btn pagination__btn--first"
          onClick={handleFirst}
          disabled={isFirstPage || isLoading}
          title="First page"
        >
          ««
        </button>

        {/* Previous button */}
        <button
          className="pagination__btn pagination__btn--prev"
          onClick={handlePrevious}
          disabled={isFirstPage || isLoading}
          title="Previous page"
        >
          «
        </button>

        {/* Page indicator */}
        <span className="pagination__page">
          {isLoading ? (
            <span className="pagination__loading">...</span>
          ) : (
            <>
              <span className="pagination__current">{currentPage + 1}</span>
              <span className="pagination__separator">/</span>
              <span className="pagination__total-pages">{totalPages}</span>
            </>
          )}
        </span>

        {/* Next button */}
        <button
          className="pagination__btn pagination__btn--next"
          onClick={handleNext}
          disabled={isLastPage || isLoading}
          title="Next page"
        >
          »
        </button>

        {/* Last page button */}
        <button
          className="pagination__btn pagination__btn--last"
          onClick={handleLast}
          disabled={isLastPage || isLoading}
          title="Last page"
        >
          »»
        </button>
      </div>
    </div>
  );
});

// ============================================================================
// Default Export
// ============================================================================

export default PaginationControls;
