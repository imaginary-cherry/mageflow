import {Task} from './Task.js';

/**
 * Abstract base class for container tasks that have children
 * Provides common functionality for tasks that contain other tasks
 */
export class ContainerTask extends Task {
    static DEFAULT_PAGE_SIZE = 10;
    static CHILD_MARGIN_TOP = 40;
    static CHILD_MARGIN_LEFT = 20;
    static PAGINATION_FOOTER_HEIGHT = 35;

    constructor(data) {
        super(data);
        this.tasks = data.tasks || [];
        this.pageSize = data.pageSize ?? ContainerTask.DEFAULT_PAGE_SIZE;

        // Lazy loading properties for children
        this.totalChildren = data.totalChildren ?? this.tasks.length;
        this.childrenLoaded = data.childrenLoaded !== false;
        this.childrenPage = data.childrenPage ?? 0;
        this.childrenHasMore = data.childrenHasMore ?? false;
    }

    needsChildrenLoad() {
        return !this.childrenLoaded && this.totalChildren > 0;
    }

    hasMoreChildrenToLoad() {
        return this.childrenHasMore || (!this.childrenLoaded && this.totalChildren > this.tasks.length);
    }

    getTotalPages() {
        return Math.max(1, Math.ceil(this.tasks.length / this.pageSize));
    }

    getTasksForPage(pageIndex) {
        const startIndex = pageIndex * this.pageSize;
        const endIndex = Math.min(startIndex + this.pageSize, this.tasks.length);
        return this.tasks.slice(startIndex, endIndex);
    }

    needsPagination() {
        return this.tasks.length > this.pageSize;
    }

    hasTasks() {
        return this.tasks.length > 0;
    }

    /**
     * Calculate dimensions based on children - must be implemented by subclass
     * @param {Map<string, Task>} allTasks - All tasks in the system for lookup
     * @returns {{width: number, height: number}}
     */
    calculateDimensions(allTasks) {
        throw new Error('calculateDimensions(allTasks) must be implemented by container subclass');
    }

    /**
     * Layout children within this container - must be implemented by subclass
     * @param {Map<string, Task>} allTasks - All tasks in the system for lookup
     * @param {Set<string>} processedContainers - Already processed containers to avoid cycles
     * @returns {{nodes: Array, edges: Array}}
     */
    layoutChildren(allTasks, processedContainers, pageIndex = 0) {
        throw new Error('layoutChildren(allTasks, processedContainers) must be implemented by container subclass');
    }

    /**
     * Container tasks have lower z-index so children appear on top
     * @returns {number}
     */
    getZIndex() {
        return 0;
    }

    /**
     * Get React Flow node type for containers
     * @returns {string}
     */
    getReactFlowNodeType() {
        return 'chainNode'; // Default container node type
    }
}