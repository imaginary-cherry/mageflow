/**
 * Abstract base class for all task types
 * Defines the contract that all tasks must implement
 */
export class Task {
  constructor(data) {
    this.id = data.id;
    this.name = data.name;
    this.type = data.type;
    this.successCallbacks = data.successCallbacks || [];
    this.errorCallbacks = data.errorCallbacks || [];
    this.parent = data.parent || null;

    this.width = data.width;
    this.height = data.height;
  }

  hasCallbacksToLoad() {
    return this.successCallbacks.length > 0 || this.errorCallbacks.length > 0;
  }

  /**
   * Calculate the dimensions this task requires
   * @param {Map<string, Task>} [allTasks] - Optional: all tasks in the system (needed for containers)
   * @returns {{width: number, height: number}}
   */
  calculateDimensions(allTasks) {
    throw new Error('calculateDimensions() must be implemented by subclass');
  }

  /**
   * Get the React Flow node type for this task
   * @returns {string}
   */
  getReactFlowNodeType() {
    throw new Error('getReactFlowNodeType() must be implemented by subclass');
  }

  /**
   * Get the display icon/emoji for this task type
   * @returns {string}
   */
  getDisplayIcon() {
    throw new Error('getDisplayIcon() must be implemented by subclass');
  }
  /**
   * Check if this task has success callbacks
   * @returns {boolean}
   */
  hasSuccessCallbacks() {
    return this.successCallbacks.length > 0;
  }

  /**
   * Check if this task has error callbacks
   * @returns {boolean}
   */
  hasErrorCallbacks() {
    return this.errorCallbacks.length > 0;
  }

  /**
   * Create a React Flow node object for this task
   * @param {{x: number, y: number}} position
   * @param {Map<string, Task>} allTasks - All tasks for containers that need it
   * @returns {object}
   */
  createReactFlowNode(position, allTasks = null) {
    const dimensions = this.calculateDimensions(allTasks);
    
    return {
      id: this.id,
      type: this.getReactFlowNodeType(),
      data: {
        label: this.name,
        taskType: this.type,
        hasSuccessCallbacks: this.hasSuccessCallbacks(),
        hasErrorCallbacks: this.hasErrorCallbacks(),
        width: dimensions.width,
        height: dimensions.height,
        displayIcon: this.getDisplayIcon()
      },
      position: {
        x: position.x - dimensions.width / 2,
        y: position.y - dimensions.height / 2
      },
      style: {
        width: dimensions.width,
        height: dimensions.height,
        zIndex: this.getZIndex()
      },
      targetPosition: 'left',
      sourcePosition: 'right'
    };
  }

  /**
   * Get the z-index for this task type
   * @returns {number}
   */
  getZIndex() {
    return 1;
  }
}