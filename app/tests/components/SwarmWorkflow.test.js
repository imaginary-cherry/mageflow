import {chainTaskExample} from '../../src/data/chainTaskData';
import {buildChainGraphLayout} from '../../src/utils/chainGraphBuilder';

describe('Swarm Workflow Tests', () => {
  test('verifies_swarm_layout_containment_and_connections_sanity', () => {
    // Arrange
    const { nodes, edges } = buildChainGraphLayout(chainTaskExample);

    // Act
    const task1 = nodes.find(n => n.id === 'task1');
    const task3 = nodes.find(n => n.id === 'task3');
    const parallelSwarm = nodes.find(n => n.id === 'parallelSwarm');
    const workerA = nodes.find(n => n.id === 'workerA');
    const workerB = nodes.find(n => n.id === 'workerB');
    const workerC = nodes.find(n => n.id === 'workerC');

    // Assert - Containment: task1, parallelSwarm, task3 inside mainChain
    expect(task1.parentNode).toBe('mainChain');
    expect(parallelSwarm.parentNode).toBe('mainChain');
    expect(task3.parentNode).toBe('mainChain');

    // Assert - Containment: workers inside parallelSwarm
    expect(workerA.parentNode).toBe('parallelSwarm');
    expect(workerB.parentNode).toBe('parallelSwarm');
    expect(workerC.parentNode).toBe('parallelSwarm');

    // Assert - Chain edge: task1 -> parallelSwarm (on success)
    const task1ToSwarmEdge = edges.find(e => e.id === 'task1-chain-parallelSwarm');
    expect(task1ToSwarmEdge).toBeDefined();
    expect(task1ToSwarmEdge.source).toBe('task1');
    expect(task1ToSwarmEdge.target).toBe('parallelSwarm');

    // Assert - Chain edge: parallelSwarm -> task3 (on success)
    const swarmToTask3Edge = edges.find(e => e.id === 'parallelSwarm-chain-task3');
    expect(swarmToTask3Edge).toBeDefined();
    expect(swarmToTask3Edge.source).toBe('parallelSwarm');
    expect(swarmToTask3Edge.target).toBe('task3');

    // Assert - Callback: workerB -> workerB_notify (on success)
    const workerBSuccessEdge = edges.find(e => e.id === 'workerB-success-workerB_notify');
    expect(workerBSuccessEdge).toBeDefined();
    expect(workerBSuccessEdge.source).toBe('workerB');
    expect(workerBSuccessEdge.target).toBe('workerB_notify');
    expect(workerBSuccessEdge.label).toBe('success');

    // Assert - Callback: workerB -> workerB_error (on failure)
    const workerBErrorEdge = edges.find(e => e.id === 'workerB-error-workerB_error');
    expect(workerBErrorEdge).toBeDefined();
    expect(workerBErrorEdge.source).toBe('workerB');
    expect(workerBErrorEdge.target).toBe('workerB_error');
    expect(workerBErrorEdge.label).toBe('error');
  });
});
