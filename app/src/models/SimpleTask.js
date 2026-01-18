import { Task } from './Task.js';

/**
 * Simple task implementation for 'task' type
 * These tasks have constant dimensions and simple display logic
 */
export class SimpleTask extends Task {

  /**
   * Calculate dimensions based on label length with constants
   * @param {Map<string, Task>} [allTasks] - Optional parameter (not used by simple tasks)
   * @returns {{width: number, height: number}}
   */
  calculateDimensions(allTasks) {
    // Use explicit dimensions if provided
    if (this.width && this.height) {
      return { width: this.width, height: this.height };
    }

    const baseWidth = 180;
    const baseHeight = 60;
    const charWidth = 7;
    const padding = 40;

    const labelLength = this.name ? this.name.length : 10;
    const calculatedWidth = Math.max(baseWidth, Math.min(300, labelLength * charWidth + padding));

    return {
      width: calculatedWidth,
      height: baseHeight
    };
  }

  /**
   * Get React Flow node type based on task type
   * @returns {string}
   */
  getReactFlowNodeType() {
    return this.type === 'error' ? 'errorNode' : 'taskNode';
  }

  /**
   * Get display icon for this task type
   * @returns {string}
   */
  getDisplayIcon() {
    return '';
  }
}