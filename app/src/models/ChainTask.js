import { ContainerTask } from './ContainerTask.js';

/**
 * Chain task implementation for tasks that contain other tasks in a sequential chain
 * Layouts children horizontally and connects them sequentially
 */
export class ChainTask extends ContainerTask {
  static CHILD_SPACING = 20;

  /**
   * Calculate dimensions based on child tasks (uses pageSize for consistent sizing)
   * @param {Map<string, Task>} allTasks - All tasks in the system for lookup
   * @returns {{width: number, height: number}}
   */
  calculateDimensions(allTasks) {
    if (!this.hasTasks()) {
      return { width: 400, height: 150 };
    }

    const paginationFooterHeight = this.needsPagination() ? ContainerTask.PAGINATION_FOOTER_HEIGHT : 0;
    const childrenToMeasure = this.getTasksForPage(0);

    let chainWidth = ContainerTask.CHILD_MARGIN_LEFT * 2;
    let chainHeight = 120;
    let currentX = ContainerTask.CHILD_MARGIN_LEFT;

    childrenToMeasure.forEach(childId => {
      const childTask = allTasks.get(childId);
      if (!childTask) return;

      const childDimensions = childTask.calculateDimensions(allTasks);

      if (childTask instanceof ContainerTask) {
        chainWidth = Math.max(chainWidth, currentX + childDimensions.width + ContainerTask.CHILD_MARGIN_LEFT);
        chainHeight = Math.max(chainHeight, ContainerTask.CHILD_MARGIN_TOP + childDimensions.height + ContainerTask.CHILD_MARGIN_LEFT);
        currentX += childDimensions.width + ChainTask.CHILD_SPACING;
      } else {
        chainWidth = Math.max(chainWidth, currentX + childDimensions.width + ContainerTask.CHILD_MARGIN_LEFT);
        chainHeight = Math.max(chainHeight, ContainerTask.CHILD_MARGIN_TOP + 30 + childDimensions.height + ContainerTask.CHILD_MARGIN_LEFT);
        currentX += childDimensions.width + ChainTask.CHILD_SPACING;
      }
    });

    return { width: chainWidth, height: chainHeight + paginationFooterHeight };
  }

  /**
   * Layout children horizontally with sequential connections
   * @param {Map<string, Task>} allTasks - All tasks in the system for lookup
   * @param {Set<string>} processedContainers - Already processed containers to avoid cycles
   * @param {number} [pageIndex=0] - Current page index for pagination
   * @returns {{nodes: Array, edges: Array}}
   */
  layoutChildren(allTasks, processedContainers, pageIndex = 0) {
    const childNodes = [];
    const childEdges = [];

    if (!this.hasTasks()) {
      return { nodes: childNodes, edges: childEdges };
    }

    let currentX = ContainerTask.CHILD_MARGIN_LEFT;
    const pageChildren = this.getTasksForPage(pageIndex);

    pageChildren.forEach((childId, index) => {
      const childTask = allTasks.get(childId);
      if (!childTask) return;

      const childDimensions = childTask.calculateDimensions(allTasks);

      if (childTask instanceof ContainerTask && !processedContainers.has(childId)) {
        processedContainers.add(childId);

        const containerTask = childTask;
        const nestedPageIndex = 0;
        const nestedLayout = containerTask.layoutChildren(allTasks, processedContainers, nestedPageIndex);

        const containerNode = containerTask.createReactFlowNode({
          x: currentX + childDimensions.width / 2,
          y: ContainerTask.CHILD_MARGIN_TOP + childDimensions.height / 2
        }, allTasks);
        containerNode.parentNode = this.id;
        containerNode.extent = 'parent';

        containerNode.data = {
          ...containerNode.data,
          hasSuccessCallbacks: true,
          hasErrorCallbacks: containerTask.hasErrorCallbacks(),
        };

        childNodes.push(containerNode);
        childNodes.push(...nestedLayout.nodes);
        childEdges.push(...nestedLayout.edges);

        currentX += childDimensions.width + ChainTask.CHILD_SPACING;

      } else if (!childTask.parent || childTask.parent === this.id) {
        const childNode = childTask.createReactFlowNode({
          x: currentX + childDimensions.width / 2,
          y: ContainerTask.CHILD_MARGIN_TOP + 30 + childDimensions.height / 2
        }, allTasks);
        childNode.parentNode = this.id;
        childNode.extent = 'parent';

        childNode.data = {
          ...childNode.data,
          hasSuccessCallbacks: true,
          hasErrorCallbacks: childTask.hasErrorCallbacks(),
        };

        childNodes.push(childNode);
        currentX += childDimensions.width + ChainTask.CHILD_SPACING;
      }

      // Connect children within the current page
      if (index < pageChildren.length - 1) {
        const nextChildId = pageChildren[index + 1];
        childEdges.push({
          id: `${childId}-chain-${nextChildId}`,
          source: childId,
          target: nextChildId,
          type: 'smoothstep',
          animated: true,
          style: {
            stroke: '#64748b',
            strokeWidth: 3,
            zIndex: 10
          },
          markerEnd: {
            type: 'arrowclosed',
            color: '#64748b'
          },
          zIndex: 10
        });
      }
    });

    return { nodes: childNodes, edges: childEdges };
  }

  /**
   * Get display icon for chain tasks
   * @returns {string}
   */
  getDisplayIcon() {
    return '🔗 Chain';
  }

  /**
   * Create React Flow node with chain-specific properties
   * @param {{x: number, y: number}} position
   * @param {Map<string, Task>} allTasks - All tasks for dimension calculation
   * @returns {object}
   */
  createReactFlowNode(position, allTasks) {
    const node = super.createReactFlowNode(position, allTasks);
    
    // Override data for chain-specific properties
    node.data = {
      ...node.data,
      hasSuccessCallbacks: true,  // Chains can have outputs
      hasErrorCallbacks: false,
    };

    return node;
  }
}