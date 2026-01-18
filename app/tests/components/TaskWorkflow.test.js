import React, {useCallback, useMemo} from 'react';
import {render, waitFor} from '@testing-library/react';
import ReactFlow, {addEdge, Background, Controls, MiniMap, useEdgesState, useNodesState} from 'reactflow';
import 'reactflow/dist/style.css';
import {ErrorNode, TaskNode} from '../../src/components/CustomNodes';
import {buildGraphLayout} from '../../src/utils/graphBuilder';
import {detectOverlaps, getNodeBounds, verifyLeftToRightFlow, waitForReactFlow} from '../test-utils/testHelpers';
import {branchingTasks, complexWorkflowTasks, currentTasksLayoutSnapshot, simpleLinearTasks, variableSizeTasks} from '../test-utils/testData';

const nodeTypes = {
    taskNode: TaskNode,
    errorNode: ErrorNode
};

const TestTaskWorkflow = ({tasks}) => {
    const {nodes: initialNodes, edges: initialEdges} = useMemo(
        () => buildGraphLayout(tasks),
        [tasks]
    );

    const [nodes, , onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    const onConnect = useCallback(
        (params) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    );

    return (
        <div style={{width: '100vw', height: '100vh'}}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{padding: 0.2}}
            >
                <Controls/>
                <MiniMap nodeColor={() => '#4299e1'}/>
                <Background variant="dots" gap={12} size={1}/>
            </ReactFlow>
        </div>
    );
};

describe('TaskWorkflow Rendered App Tests', () => {
    describe('Root Node Detection', () => {
        test('identifies root nodes visually by position', async () => {
            const {container} = render(<TestTaskWorkflow tasks={simpleLinearTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(3);
            });

            await waitForReactFlow();

            const allNodes = container.querySelectorAll('.react-flow__node');
            const allBounds = Array.from(allNodes).map(getNodeBounds);

            const leftmostNode = allBounds.reduce((leftmost, current) =>
                current.centerX < leftmost.centerX ? current : leftmost
            );

            expect(leftmostNode.id).toBe('task1');
        });

        test('root node exists and is positioned on the left', async () => {
            const {container} = render(<TestTaskWorkflow tasks={branchingTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(6);
            });

            await waitForReactFlow();

            const rootNode = container.querySelector('[data-id="root"]');
            expect(rootNode).toBeInTheDocument();

            const allNodes = container.querySelectorAll('.react-flow__node');
            const allBounds = Array.from(allNodes).map(getNodeBounds);
            const rootBounds = allBounds.find(b => b.id === 'root');

            const isLeftmost = allBounds.every(bounds =>
                bounds.id === 'root' || bounds.centerX >= rootBounds.centerX
            );
            expect(isLeftmost).toBe(true);
        });
    });

    describe('Task Connection Verification', () => {
        test('renders correct number of nodes for task data', async () => {
            const {container} = render(<TestTaskWorkflow tasks={branchingTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(Object.keys(branchingTasks).length);
            });

            await waitForReactFlow();

            Object.keys(branchingTasks).forEach(taskId => {
                const node = container.querySelector(`[data-id="${taskId}"]`);
                expect(node).toBeInTheDocument();
            });
        });

        test('renders SVG edges container for connections', async () => {
            const {container} = render(<TestTaskWorkflow tasks={simpleLinearTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(3);
            });

            await waitForReactFlow();

            const edgesContainer = container.querySelector('.react-flow__edges');
            expect(edgesContainer).toBeInTheDocument();

            const svg = container.querySelector('svg.react-flow__edges');
            expect(svg).toBeInTheDocument();
        });

        test('displays task names correctly in nodes', async () => {
            const {container} = render(<TestTaskWorkflow tasks={branchingTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(6);
            });

            await waitForReactFlow();

            expect(container).toHaveTextContent('Root Task');
            expect(container).toHaveTextContent('Branch A');
            expect(container).toHaveTextContent('Branch B');
            expect(container).toHaveTextContent('Error Handler');
        });
    });

    describe('Node Overlap Prevention', () => {
        test('ensures no nodes overlap in simple workflow', async () => {
            const {container} = render(<TestTaskWorkflow tasks={simpleLinearTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(3);
            });

            await waitForReactFlow();

            const allNodes = container.querySelectorAll('.react-flow__node');
            const nodeBounds = Array.from(allNodes).map(getNodeBounds);
            const overlaps = detectOverlaps(nodeBounds);

            expect(overlaps).toHaveLength(0);
        });

        test('handles variable-sized nodes without overlap', async () => {
            const {container} = render(<TestTaskWorkflow tasks={variableSizeTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(4);
            });

            await waitForReactFlow();

            const allNodes = container.querySelectorAll('.react-flow__node');
            const nodeBounds = Array.from(allNodes).map(getNodeBounds);
            const overlaps = detectOverlaps(nodeBounds);

            expect(overlaps).toHaveLength(0);

            const largeNode = container.querySelector('[data-id="large"]');
            const smallNode = container.querySelector('[data-id="small"]');

            expect(largeNode).toBeInTheDocument();
            expect(smallNode).toBeInTheDocument();
            expect(largeNode.textContent).toContain('Very Long Task Name');
            expect(smallNode.textContent).toContain('S');
        });

        test('maintains proper spacing in complex workflow', async () => {
            const {container} = render(<TestTaskWorkflow tasks={complexWorkflowTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBeGreaterThan(0);
            });

            await waitForReactFlow();

            const allNodes = container.querySelectorAll('.react-flow__node');
            const nodeBounds = Array.from(allNodes).map(getNodeBounds);
            const overlaps = detectOverlaps(nodeBounds);

            if (overlaps.length > 0) {
                console.error('Overlapping nodes detected:', overlaps);
                overlaps.forEach(overlap => {
                    console.error(`Overlap between ${overlap.nodeA} and ${overlap.nodeB}:`);
                    console.error(`  Node A bounds:`, overlap.boundsA);
                    console.error(`  Node B bounds:`, overlap.boundsB);
                });
            }

            expect(overlaps).toHaveLength(0);
        });

        test('maintains left-to-right flow ordering', async () => {
            const {container} = render(<TestTaskWorkflow tasks={branchingTasks}/>);

            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(6);
            });

            await waitForReactFlow();

            const allNodes = container.querySelectorAll('.react-flow__node');
            const nodeBounds = Array.from(allNodes).map(getNodeBounds);
            const flowViolations = verifyLeftToRightFlow(nodeBounds);

            if (flowViolations.length > 0) {
                console.error('Left-to-right flow violations:', flowViolations);
            }

            expect(flowViolations).toHaveLength(0);
        });

        test('ensures current tasks layout renders without node overlap', async () => {
            // Arrange
            const {container} = render(<TestTaskWorkflow tasks={currentTasksLayoutSnapshot}/>);
            
            // Act
            await waitFor(() => {
                const renderedNodes = container.querySelectorAll('.react-flow__node');
                expect(renderedNodes.length).toBe(Object.keys(currentTasksLayoutSnapshot).length);
            });

            await waitForReactFlow();

            // Assert
            const allNodes = container.querySelectorAll('.react-flow__node');
            const nodeBounds = Array.from(allNodes).map(getNodeBounds);
            const overlaps = detectOverlaps(nodeBounds);

            if (overlaps.length > 0) {
                console.error('Node overlaps detected in current tasks layout:', overlaps);
                overlaps.forEach(overlap => {
                    console.error(`Overlap between ${overlap.nodeA} and ${overlap.nodeB}:`);
                    console.error(`  Node A bounds:`, overlap.boundsA);
                    console.error(`  Node B bounds:`, overlap.boundsB);
                });
            }

            expect(overlaps).toHaveLength(0);
        });
    });
});