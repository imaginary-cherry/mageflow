import { Task } from '@/types/task';

// Constants for sizing
export const SIMPLE_TASK_WIDTH = 180;
export const SIMPLE_TASK_HEIGHT = 60;
export const CONTAINER_PADDING = 24;
export const CONTAINER_HEADER_HEIGHT = 40;
export const CONTAINER_FOOTER_HEIGHT = 36; // For pagination
export const INNER_TASK_GAP = 12;
export const TASKS_PER_PAGE = 5;

export interface TaskDimensions {
  width: number;
  height: number;
}

/**
 * Recursively calculate the dimensions a task will take.
 * - Simple tasks have fixed size
 * - Chain tasks arrange children horizontally (sequential flow)
 * - Swarm tasks arrange children vertically (parallel flow)
 */
export const calculateTaskDimensions = (
  task: Task,
  tasksMap: Record<string, Task>,
  currentPage: number = 1
): TaskDimensions => {
  if (task.type === 'simple') {
    return { width: SIMPLE_TASK_WIDTH, height: SIMPLE_TASK_HEIGHT };
  }

  const childTasks = task.children_ids
    .map(id => tasksMap[id])
    .filter(Boolean);

  if (childTasks.length === 0) {
    // Empty container
    return { 
      width: SIMPLE_TASK_WIDTH + CONTAINER_PADDING * 2, 
      height: SIMPLE_TASK_HEIGHT + CONTAINER_HEADER_HEIGHT + CONTAINER_PADDING * 2 
    };
  }

  // Apply pagination - only show tasks for current page
  const totalPages = Math.ceil(childTasks.length / TASKS_PER_PAGE);
  const startIndex = (currentPage - 1) * TASKS_PER_PAGE;
  const paginatedChildren = childTasks.slice(startIndex, startIndex + TASKS_PER_PAGE);

  // Calculate dimensions for visible children
  const childDimensions = paginatedChildren.map(child => 
    calculateTaskDimensions(child, tasksMap, 1) // Reset to page 1 for nested
  );

  let contentWidth: number;
  let contentHeight: number;

  if (task.type === 'chain') {
    // Chain: horizontal layout (sequential)
    contentWidth = childDimensions.reduce((sum, dim) => sum + dim.width, 0) 
      + (childDimensions.length - 1) * INNER_TASK_GAP;
    contentHeight = Math.max(...childDimensions.map(dim => dim.height));
  } else {
    // Swarm: vertical layout (parallel)
    contentWidth = Math.max(...childDimensions.map(dim => dim.width));
    contentHeight = childDimensions.reduce((sum, dim) => sum + dim.height, 0)
      + (childDimensions.length - 1) * INNER_TASK_GAP;
  }

  const needsPagination = childTasks.length > TASKS_PER_PAGE;

  return {
    width: contentWidth + CONTAINER_PADDING * 2,
    height: contentHeight + CONTAINER_HEADER_HEIGHT + CONTAINER_PADDING * 2 
      + (needsPagination ? CONTAINER_FOOTER_HEIGHT : 0),
  };
};
