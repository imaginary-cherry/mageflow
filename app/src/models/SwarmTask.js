import {ContainerTask} from './ContainerTask.js';

export class SwarmTask extends ContainerTask {
    static CHILD_SPACING = 15;

    calculateDimensions(allTasks) {
        if (!this.hasChildren()) {
            return {width: 250, height: 200};
        }

        const paginationFooterHeight = this.needsPagination() ? ContainerTask.PAGINATION_FOOTER_HEIGHT : 0;
        const childrenToMeasure = this.getChildrenForPage(0);

        let swarmWidth = 200;
        let swarmHeight = ContainerTask.CHILD_MARGIN_TOP;

        childrenToMeasure.forEach(childId => {
            const childTask = allTasks.get(childId);
            if (!childTask) return;

            const childDimensions = childTask.calculateDimensions(allTasks);

            swarmWidth = Math.max(swarmWidth, childDimensions.width + ContainerTask.CHILD_MARGIN_LEFT * 2);
            swarmHeight += childDimensions.height + SwarmTask.CHILD_SPACING;
        });

        swarmHeight += ContainerTask.CHILD_MARGIN_LEFT + paginationFooterHeight;

        return {width: swarmWidth, height: swarmHeight};
    }

    layoutChildren(allTasks, processedContainers, pageIndex = 0) {
        const childNodes = [];
        const childEdges = [];

        if (!this.hasChildren()) {
            return {nodes: childNodes, edges: childEdges};
        }

        const swarmDimensions = this.calculateDimensions(allTasks);
        const pageChildren = this.getChildrenForPage(pageIndex);
        let currentY = ContainerTask.CHILD_MARGIN_TOP;

        pageChildren.forEach(childId => {
            const childTask = allTasks.get(childId);
            if (!childTask) return;

            const childDimensions = childTask.calculateDimensions(allTasks);

            if (childTask instanceof ContainerTask && !processedContainers.has(childId)) {
                processedContainers.add(childId);

                const containerTask = childTask;
                const nestedPageIndex = 0;
                const nestedLayout = containerTask.layoutChildren(allTasks, processedContainers, nestedPageIndex);

                const containerNode = containerTask.createReactFlowNode({
                    x: swarmDimensions.width / 2,
                    y: currentY + childDimensions.height / 2
                }, allTasks);
                containerNode.parentNode = this.id;
                containerNode.extent = 'parent';

                childNodes.push(containerNode);
                childNodes.push(...nestedLayout.nodes);
                childEdges.push(...nestedLayout.edges);

                currentY += childDimensions.height + SwarmTask.CHILD_SPACING;

            } else if (!childTask.parent || childTask.parent === this.id) {
                const childNode = childTask.createReactFlowNode({
                    x: swarmDimensions.width / 2,
                    y: currentY + childDimensions.height / 2
                }, allTasks);
                childNode.parentNode = this.id;
                childNode.extent = 'parent';

                childNode.data = {
                    ...childNode.data,
                    hasSuccessCallbacks: childTask.hasSuccessCallbacks(),
                    hasErrorCallbacks: childTask.hasErrorCallbacks(),
                };

                childNodes.push(childNode);
                currentY += childDimensions.height + SwarmTask.CHILD_SPACING;
            }
        });

        return {nodes: childNodes, edges: childEdges};
    }

    getDisplayIcon() {
        return '🐝 Swarm';
    }

    getReactFlowNodeType() {
        return 'swarmNode';
    }

    createReactFlowNode(position, allTasks) {
        const node = super.createReactFlowNode(position, allTasks);

        node.data = {
            ...node.data,
            hasSuccessCallbacks: this.successCallbacks.length > 0,
            hasErrorCallbacks: this.errorCallbacks.length > 0,
        };

        return node;
    }
}