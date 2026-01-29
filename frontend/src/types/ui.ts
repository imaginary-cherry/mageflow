/**
 * UI State Types for MageFlow Graph Visualization
 */

export interface Viewport {
  x: number;
  y: number;
  zoom: number;
}

export interface UIState {
  selectedTaskId: string | null;
  expandedNodeIds: Set<string>;
  activeRootId: string | null;
  viewport: Viewport;
  isLoading: boolean;
  error: string | null;
}

export interface NodePosition {
  x: number;
  y: number;
}

export type LayoutDirection = 'LR' | 'TB' | 'RL' | 'BT';

export interface LayoutOptions {
  direction: LayoutDirection;
  nodeSpacing: number;
  rankSpacing: number;
  edgeSpacing: number;
}

export const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  direction: 'LR',
  nodeSpacing: 50,
  rankSpacing: 100,
  edgeSpacing: 20,
};

export const DEFAULT_VIEWPORT: Viewport = {
  x: 0,
  y: 0,
  zoom: 1,
};
