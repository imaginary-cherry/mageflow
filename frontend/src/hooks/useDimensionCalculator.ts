/**
 * Dimension Calculator Hook
 *
 * Each node calculates and reports its own dimensions.
 * Uses ResizeObserver for efficient tracking.
 */

import { useEffect, useRef, useCallback } from 'react';
import { useGraphStore } from '../stores/graphStore';
import { TaskDimensions } from '../types';

// ============================================================================
// Types
// ============================================================================

interface UseDimensionCalculatorOptions {
  debounceMs?: number;
  minWidth?: number;
  minHeight?: number;
}

interface UseDimensionCalculatorResult {
  ref: React.RefObject<HTMLDivElement>;
  dimensions: TaskDimensions | null;
  recalculate: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_DEBOUNCE_MS = 100;
const DEFAULT_MIN_WIDTH = 100;
const DEFAULT_MIN_HEIGHT = 40;

// ============================================================================
// Hook Implementation
// ============================================================================

export function useDimensionCalculator(
  taskId: string,
  options: UseDimensionCalculatorOptions = {}
): UseDimensionCalculatorResult {
  const {
    debounceMs = DEFAULT_DEBOUNCE_MS,
    minWidth = DEFAULT_MIN_WIDTH,
    minHeight = DEFAULT_MIN_HEIGHT,
  } = options;

  const nodeRef = useRef<HTMLDivElement>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateDimensions = useGraphStore(
    (state) => state.actions.updateTaskDimensions
  );
  const dimensions = useGraphStore(
    (state) => state.tasks[taskId]?.dimensions ?? null
  );

  // Debounced update function
  const updateDimensionsDebounced = useCallback(
    (width: number, height: number) => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }

      debounceTimer.current = setTimeout(() => {
        const finalWidth = Math.max(width, minWidth);
        const finalHeight = Math.max(height, minHeight);

        updateDimensions(taskId, {
          width: finalWidth,
          height: finalHeight,
          calculatedAt: Date.now(),
        });
      }, debounceMs);
    },
    [taskId, updateDimensions, debounceMs, minWidth, minHeight]
  );

  // Manual recalculation
  const recalculate = useCallback(() => {
    if (!nodeRef.current) return;

    const rect = nodeRef.current.getBoundingClientRect();
    updateDimensionsDebounced(rect.width, rect.height);
  }, [updateDimensionsDebounced]);

  // Set up ResizeObserver
  useEffect(() => {
    const node = nodeRef.current;
    if (!node) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        const { width, height } = entry.contentRect;
        updateDimensionsDebounced(width, height);
      }
    });

    observer.observe(node);

    // Initial calculation
    const rect = node.getBoundingClientRect();
    updateDimensionsDebounced(rect.width, rect.height);

    return () => {
      observer.disconnect();
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, [updateDimensionsDebounced]);

  return {
    ref: nodeRef,
    dimensions,
    recalculate,
  };
}

// ============================================================================
// Utility: Batch Dimension Calculator
// ============================================================================

/**
 * Calculate dimensions for multiple nodes at once
 * Useful for initial layout calculation
 */
export function useBatchDimensionCalculator(taskIds: string[]) {
  const updateDimensions = useGraphStore(
    (state) => state.actions.updateTaskDimensions
  );

  const calculateAll = useCallback(
    (nodeRefs: Map<string, HTMLDivElement>) => {
      for (const [taskId, node] of nodeRefs) {
        if (!node) continue;
        const rect = node.getBoundingClientRect();
        updateDimensions(taskId, {
          width: Math.max(rect.width, DEFAULT_MIN_WIDTH),
          height: Math.max(rect.height, DEFAULT_MIN_HEIGHT),
          calculatedAt: Date.now(),
        });
      }
    },
    [updateDimensions]
  );

  return { calculateAll };
}

// ============================================================================
// Utility: Text-Based Dimension Estimation
// ============================================================================

/**
 * Estimate dimensions based on text content
 * Useful for calculating dimensions before render
 */
export function estimateTextDimensions(
  text: string,
  options: {
    fontSize?: number;
    fontFamily?: string;
    padding?: number;
    maxWidth?: number;
  } = {}
): { width: number; height: number } {
  const {
    fontSize = 14,
    fontFamily = 'sans-serif',
    padding = 16,
    maxWidth = 300,
  } = options;

  // Create off-screen canvas for text measurement
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');

  if (!ctx) {
    // Fallback estimation
    const estimatedWidth = Math.min(text.length * fontSize * 0.6, maxWidth);
    return {
      width: estimatedWidth + padding * 2,
      height: fontSize * 1.5 + padding * 2,
    };
  }

  ctx.font = `${fontSize}px ${fontFamily}`;
  const metrics = ctx.measureText(text);
  const textWidth = Math.min(metrics.width, maxWidth);

  // Calculate number of lines if text wraps
  const lines = Math.ceil(metrics.width / maxWidth);
  const textHeight = lines * fontSize * 1.5;

  return {
    width: textWidth + padding * 2,
    height: textHeight + padding * 2,
  };
}
