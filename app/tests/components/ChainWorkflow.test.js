import {chainTaskExample} from '../../src/data/chainTaskData';
import {buildChainGraphLayout} from '../../src/utils/chainGraphBuilder';
import {
  detectInsufficientSpacing,
  detectNodeOverlaps,
  detectNodesOutsideParent,
  formatNodePositions
} from '../utils/testHelpers';

describe('Chain Task Workflow Tests', () => {
  test('creates nested group nodes for chain tasks', () => {
    const { nodes } = buildChainGraphLayout(chainTaskExample);
    
    // Find the main chain node
    const mainChain = nodes.find(n => n.id === 'mainChain');
    expect(mainChain).toBeDefined();
    expect(mainChain.type).toBe('chainNode');

    // Find the swarm node inside the main chain
    const parallelSwarm = nodes.find(n => n.id === 'parallelSwarm');
    expect(parallelSwarm).toBeDefined();
    expect(parallelSwarm.type).toBe('swarmNode');
    expect(parallelSwarm.parentNode).toBe('mainChain');

    // Find tasks inside main chain
    const task1 = nodes.find(n => n.id === 'task1');
    expect(task1).toBeDefined();
    expect(task1.parentNode).toBe('mainChain');
    
    const task3 = nodes.find(n => n.id === 'task3');
    expect(task3).toBeDefined();
    expect(task3.parentNode).toBe('mainChain');

    // Find workers inside parallelSwarm
    const workerA = nodes.find(n => n.id === 'workerA');
    expect(workerA).toBeDefined();
    expect(workerA.parentNode).toBe('parallelSwarm');

    const workerB = nodes.find(n => n.id === 'workerB');
    expect(workerB).toBeDefined();
    expect(workerB.parentNode).toBe('parallelSwarm');

    // Verify final task is outside chains
    const finalTask = nodes.find(n => n.id === 'finalTask');
    expect(finalTask).toBeDefined();
    expect(finalTask.parentNode).toBeUndefined();
  });
  
  test('creates connections between chain elements', () => {
    const { edges } = buildChainGraphLayout(chainTaskExample);

    // Check internal chain connections (task1 -> parallelSwarm in children order)
    const task1ToSwarm = edges.find(e =>
      e.source === 'task1' && e.target === 'parallelSwarm'
    );
    expect(task1ToSwarm).toBeDefined();

    const swarmToTask3 = edges.find(e =>
      e.source === 'parallelSwarm' && e.target === 'task3'
    );
    expect(swarmToTask3).toBeDefined();

    // Check external connections (mainChain -> chainSwarm via successCallbacks)
    const mainChainToChainSwarm = edges.find(e =>
      e.source === 'mainChain' && e.target === 'chainSwarm'
    );
    expect(mainChainToChainSwarm).toBeDefined();
  });
  
  test('sets extent property to lock children in parent', () => {
    const { nodes } = buildChainGraphLayout(chainTaskExample);
    
    // All children should have extent: 'parent'
    const childNodes = nodes.filter(n => n.parentNode);
    childNodes.forEach(node => {
      expect(node.extent).toBe('parent');
    });
  });

  test('detects no overlapping nodes', () => {
    const { nodes } = buildChainGraphLayout(chainTaskExample);
    
    const overlaps = detectNodeOverlaps(nodes);
    
    if (overlaps.length > 0) {
      console.error('Node overlaps detected:');
      overlaps.forEach(({ nodeA, nodeB }) => {
        console.error(`  ${nodeA.id} overlaps with ${nodeB.id}`);
        console.error(`    ${nodeA.id}: pos(${nodeA.position.x}, ${nodeA.position.y}) size(${nodeA.style?.width}, ${nodeA.style?.height})`);
        console.error(`    ${nodeB.id}: pos(${nodeB.position.x}, ${nodeB.position.y}) size(${nodeB.style?.width}, ${nodeB.style?.height})`);
      });
      console.error('\nAll node positions:');
      console.error(formatNodePositions(nodes));
    }
    
    expect(overlaps).toHaveLength(0);
  });

  test('ensures all child nodes are within parent boundaries', () => {
    const { nodes } = buildChainGraphLayout(chainTaskExample);
    
    const outsideNodes = detectNodesOutsideParent(nodes);
    
    if (outsideNodes.length > 0) {
      console.error('Nodes outside parent boundaries:');
      outsideNodes.forEach(({ child, parent, bounds }) => {
        console.error(`  ${child.id} is outside ${parent.id}`);
        console.error(`    Child bounds: ${JSON.stringify(bounds.child)}`);
        console.error(`    Parent bounds: ${JSON.stringify(bounds.parent)}`);
      });
    }
    
    expect(outsideNodes).toHaveLength(0);
  });

  test('ensures sufficient spacing between sibling nodes', () => {
    const { nodes } = buildChainGraphLayout(chainTaskExample);
    
    const tooClose = detectInsufficientSpacing(nodes, 20);
    
    if (tooClose.length > 0) {
      console.error('Insufficient spacing between nodes:');
      tooClose.forEach(({ nodeA, nodeB, actualSpacing, requiredSpacing, parentId }) => {
        console.error(`  ${nodeA.id} and ${nodeB.id} in ${parentId}: ${actualSpacing}px < ${requiredSpacing}px required`);
      });
    }
    
    expect(tooClose).toHaveLength(0);
  });

  test('verifies parallelSwarm children are properly contained', () => {
    const { nodes } = buildChainGraphLayout(chainTaskExample);

    // Find nested container and its children
    const parallelSwarm = nodes.find(n => n.id === 'parallelSwarm');
    const workerA = nodes.find(n => n.id === 'workerA');
    const workerB = nodes.find(n => n.id === 'workerB');
    const task3 = nodes.find(n => n.id === 'task3');

    expect(parallelSwarm).toBeDefined();
    expect(workerA).toBeDefined();
    expect(workerB).toBeDefined();
    expect(task3).toBeDefined();

    // Calculate absolute positions for nested children (React Flow uses relative positions)
    const workerAAbsLeft = parallelSwarm.position.x + workerA.position.x;
    const workerAAbsRight = workerAAbsLeft + workerA.style.width;
    const workerBAbsLeft = parallelSwarm.position.x + workerB.position.x;
    const workerBAbsRight = workerBAbsLeft + workerB.style.width;

    const swarmLeft = parallelSwarm.position.x;
    const swarmRight = swarmLeft + parallelSwarm.style.width;

    // Verify workers are within parallelSwarm bounds
    expect(workerAAbsLeft).toBeGreaterThanOrEqual(swarmLeft);
    expect(workerAAbsRight).toBeLessThanOrEqual(swarmRight);
    expect(workerBAbsLeft).toBeGreaterThanOrEqual(swarmLeft);
    expect(workerBAbsRight).toBeLessThanOrEqual(swarmRight);
  });

  test('verifies expected positioning layout', () => {
    const { nodes } = buildChainGraphLayout(chainTaskExample);

    // Find key nodes
    const task1 = nodes.find(n => n.id === 'task1');
    const parallelSwarm = nodes.find(n => n.id === 'parallelSwarm');
    const task3 = nodes.find(n => n.id === 'task3');
    const workerA = nodes.find(n => n.id === 'workerA');

    // Verify nodes exist
    expect(task1).toBeDefined();
    expect(parallelSwarm).toBeDefined();
    expect(task3).toBeDefined();
    expect(workerA).toBeDefined();

    // Verify horizontal ordering within mainChain (left to right)
    expect(task1.position.x).toBeLessThan(parallelSwarm.position.x);
    expect(parallelSwarm.position.x).toBeLessThan(task3.position.x);

    // For relative positions, check that workerA is positioned within relative bounds
    expect(workerA.position.x).toBeGreaterThanOrEqual(0);
    expect(workerA.position.x + (workerA.style?.width || 180))
      .toBeLessThanOrEqual(parallelSwarm.style.width);
  });
});