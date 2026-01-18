import { useState, useCallback, useMemo } from 'react';

export function usePaginationState(initialPageStates = {}) {
  const [pageStates, setPageStates] = useState(initialPageStates);

  const getPage = useCallback((containerId) => {
    return pageStates[containerId] ?? 0;
  }, [pageStates]);

  const setPage = useCallback((containerId, page) => {
    setPageStates(prev => ({
      ...prev,
      [containerId]: page
    }));
  }, []);

  const goToNextPage = useCallback((containerId, totalPages) => {
    setPageStates(prev => {
      const currentPage = prev[containerId] ?? 0;
      const nextPage = Math.min(currentPage + 1, totalPages - 1);
      return { ...prev, [containerId]: nextPage };
    });
  }, []);

  const goToPrevPage = useCallback((containerId) => {
    setPageStates(prev => {
      const currentPage = prev[containerId] ?? 0;
      const prevPage = Math.max(currentPage - 1, 0);
      return { ...prev, [containerId]: prevPage };
    });
  }, []);

  const goToFirstPage = useCallback((containerId) => {
    setPageStates(prev => ({ ...prev, [containerId]: 0 }));
  }, []);

  const goToLastPage = useCallback((containerId, totalPages) => {
    setPageStates(prev => ({ ...prev, [containerId]: totalPages - 1 }));
  }, []);

  const actions = useMemo(() => ({
    getPage,
    setPage,
    goToNextPage,
    goToPrevPage,
    goToFirstPage,
    goToLastPage,
  }), [getPage, setPage, goToNextPage, goToPrevPage, goToFirstPage, goToLastPage]);

  return [pageStates, actions];
}
