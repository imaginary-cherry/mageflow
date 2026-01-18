import { mixedLargeExample } from '../../src/data/largePaginatedTaskData';
import { buildChainGraphLayout } from '../../src/utils/chainGraphBuilder';
import { TaskFactory } from '../../src/models/TaskFactory';
import { detectNodeOverlaps, detectNodesOutsideParent } from '../utils/testHelpers';

describe('Pagination Calculation Tests', () => {
  const tasks = TaskFactory.createTasksFromData(mixedLargeExample);
  const swarmTask = tasks.get('mixedSwarm');
  const chainTask = tasks.get('mixedChain');

  describe('getTotalPages calculation', () => {
    test.each([
      ['mixedSwarm', 25, 8, 4],
      ['mixedChain', 15, 4, 4],
    ])('%s with %i children and pageSize %i returns %i pages_sanity', (taskId, childCount, pageSize, expectedPages) => {
      // Arrange
      const task = tasks.get(taskId);

      // Act
      const totalPages = task.getTotalPages();

      // Assert
      expect(task.children).toHaveLength(childCount);
      expect(task.pageSize).toBe(pageSize);
      expect(totalPages).toBe(expectedPages);
    });

    test.each([
      [8, 8, 1],
      [0, 10, 1],
      [1, 10, 1],
      [100, 10, 10],
    ])('container with %i children and pageSize %i returns %i pages_edge_case', (childCount, pageSize, expectedPages) => {
      // Arrange
      const mockTask = {
        children: Array(childCount).fill('id'),
        pageSize,
        getTotalPages() {
          return Math.max(1, Math.ceil(this.children.length / this.pageSize));
        },
      };

      // Act
      const totalPages = mockTask.getTotalPages();

      // Assert
      expect(totalPages).toBe(expectedPages);
    });
  });

  describe('getChildrenForPage slicing', () => {
    test.each([
      ['mixedSwarm', 0, 8, 0, 7],
      ['mixedSwarm', 1, 8, 8, 15],
      ['mixedSwarm', 2, 8, 16, 23],
      ['mixedSwarm', 3, 1, 24, 24],
      ['mixedChain', 0, 4, 0, 3],
      ['mixedChain', 1, 4, 4, 7],
      ['mixedChain', 2, 4, 8, 11],
      ['mixedChain', 3, 3, 12, 14],
    ])('%s page %i returns %i children (indices %i to %i)_sanity', (taskId, pageIndex, expectedCount, startIdx, endIdx) => {
      // Arrange
      const task = tasks.get(taskId);

      // Act
      const pageChildren = task.getChildrenForPage(pageIndex);

      // Assert
      expect(pageChildren).toHaveLength(expectedCount);
      expect(pageChildren[0]).toBe(task.children[startIdx]);
      expect(pageChildren[pageChildren.length - 1]).toBe(task.children[endIdx]);
    });
  });

  describe('needsPagination flag', () => {
    test.each([
      ['mixedSwarm', 25, 8, true],
      ['mixedChain', 15, 4, true],
    ])('%s with %i children and pageSize %i returns needsPagination=%s_sanity', (taskId, childCount, pageSize, expected) => {
      // Arrange
      const task = tasks.get(taskId);

      // Act
      const needsPagination = task.needsPagination();

      // Assert
      expect(task.children).toHaveLength(childCount);
      expect(task.pageSize).toBe(pageSize);
      expect(needsPagination).toBe(expected);
    });

    test.each([
      [8, 8, false],
      [3, 10, false],
      [10, 10, false],
    ])('container with %i children and pageSize %i returns needsPagination=%s_edge_case', (childCount, pageSize, expected) => {
      // Arrange
      const mockTask = {
        children: Array(childCount).fill('id'),
        pageSize,
        needsPagination() {
          return this.children.length > this.pageSize;
        },
      };

      // Act
      const needsPagination = mockTask.needsPagination();

      // Assert
      expect(needsPagination).toBe(expected);
    });
  });
});

describe('Layout Integration Tests', () => {
  describe('SwarmTask renders correct children per page', () => {
    test.each([
      [0, 8, 'mixedSwarm_parallel1', 'mixedSwarm_parallel8', 'mixedSwarm_parallel9'],
      [1, 8, 'mixedSwarm_parallel9', 'mixedSwarm_parallel16', 'mixedSwarm_parallel1'],
      [2, 8, 'mixedSwarm_parallel17', 'mixedSwarm_parallel24', 'mixedSwarm_parallel25'],
      [3, 1, 'mixedSwarm_parallel25', 'mixedSwarm_parallel25', 'mixedSwarm_parallel24'],
    ])('SwarmTask page %i renders %i children with correct IDs_sanity', (pageIndex, expectedCount, firstId, lastId, notIncludedId) => {
      // Arrange
      const paginationState = { mixedSwarm: pageIndex, mixedChain: 0 };

      // Act
      const { nodes } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
      const swarmChildren = nodes.filter(n => n.parentNode === 'mixedSwarm');
      const childIds = swarmChildren.map(n => n.id);

      // Assert
      expect(swarmChildren).toHaveLength(expectedCount);
      expect(childIds).toContain(firstId);
      expect(childIds).toContain(lastId);
      expect(childIds).not.toContain(notIncludedId);
    });
  });

  describe('ChainTask renders correct children per page', () => {
    test.each([
      [0, 4, 'mixedChain_sequential1', 'mixedChain_sequential4', 'mixedChain_sequential5'],
      [1, 4, 'mixedChain_sequential5', 'mixedChain_sequential8', 'mixedChain_sequential1'],
      [2, 4, 'mixedChain_sequential9', 'mixedChain_sequential12', 'mixedChain_sequential13'],
      [3, 3, 'mixedChain_sequential13', 'mixedChain_sequential15', 'mixedChain_sequential12'],
    ])('ChainTask page %i renders %i children with correct IDs_sanity', (pageIndex, expectedCount, firstId, lastId, notIncludedId) => {
      // Arrange
      const paginationState = { mixedSwarm: 0, mixedChain: pageIndex };

      // Act
      const { nodes } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
      const chainChildren = nodes.filter(n => n.parentNode === 'mixedChain');
      const childIds = chainChildren.map(n => n.id);

      // Assert
      expect(chainChildren).toHaveLength(expectedCount);
      expect(childIds).toContain(firstId);
      expect(childIds).toContain(lastId);
      expect(childIds).not.toContain(notIncludedId);
    });
  });
});

describe('Graph Builder Integration Tests', () => {
  describe('Pagination data attached to nodes', () => {
    test.each([
      ['mixedSwarm', 0, 4, 25, 8],
      ['mixedSwarm', 2, 4, 25, 8],
      ['mixedChain', 0, 4, 15, 4],
      ['mixedChain', 3, 4, 15, 4],
    ])('%s with page %i has correct pagination metadata_sanity', (containerId, currentPage, totalPages, totalItems, pageSize) => {
      // Arrange
      const paginationState = { [containerId]: currentPage };

      // Act
      const { nodes } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
      const containerNode = nodes.find(n => n.id === containerId);

      // Assert
      expect(containerNode.data.pagination).toBeDefined();
      expect(containerNode.data.pagination.currentPage).toBe(currentPage);
      expect(containerNode.data.pagination.totalPages).toBe(totalPages);
      expect(containerNode.data.pagination.totalItems).toBe(totalItems);
      expect(containerNode.data.pagination.pageSize).toBe(pageSize);
    });
  });

  describe('Pagination callbacks are functions', () => {
    test('container nodes have pagination callback functions_sanity', () => {
      // Arrange
      const mockCallbacks = {
        goToPrevPage: jest.fn(),
        goToNextPage: jest.fn(),
        goToFirstPage: jest.fn(),
        goToLastPage: jest.fn(),
      };

      // Act
      const { nodes } = buildChainGraphLayout(mixedLargeExample, {}, mockCallbacks);
      const swarmNode = nodes.find(n => n.id === 'mixedSwarm');

      // Assert
      expect(typeof swarmNode.data.onPrevPage).toBe('function');
      expect(typeof swarmNode.data.onNextPage).toBe('function');
      expect(typeof swarmNode.data.onFirstPage).toBe('function');
      expect(typeof swarmNode.data.onLastPage).toBe('function');
    });

    test('pagination callbacks invoke correct actions_sanity', () => {
      // Arrange
      const mockCallbacks = {
        goToPrevPage: jest.fn(),
        goToNextPage: jest.fn(),
        goToFirstPage: jest.fn(),
        goToLastPage: jest.fn(),
      };

      // Act
      const { nodes } = buildChainGraphLayout(mixedLargeExample, {}, mockCallbacks);
      const swarmNode = nodes.find(n => n.id === 'mixedSwarm');

      swarmNode.data.onPrevPage();
      swarmNode.data.onNextPage();
      swarmNode.data.onFirstPage();
      swarmNode.data.onLastPage();

      // Assert
      expect(mockCallbacks.goToPrevPage).toHaveBeenCalledWith('mixedSwarm');
      expect(mockCallbacks.goToNextPage).toHaveBeenCalledWith('mixedSwarm', 4);
      expect(mockCallbacks.goToFirstPage).toHaveBeenCalledWith('mixedSwarm');
      expect(mockCallbacks.goToLastPage).toHaveBeenCalledWith('mixedSwarm', 4);
    });
  });

  describe('No pagination for small containers', () => {
    test('startTask has no pagination data_sanity', () => {
      // Arrange & Act
      const { nodes } = buildChainGraphLayout(mixedLargeExample, {}, {});
      const startTaskNode = nodes.find(n => n.id === 'startTask');

      // Assert
      expect(startTaskNode.data.pagination).toBeUndefined();
    });
  });
});

describe('Edge Connections Tests', () => {
  test('ChainTask edges connect only children on current page_sanity', () => {
    // Arrange
    const paginationState = { mixedSwarm: 0, mixedChain: 0 };

    // Act
    const { edges } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
    const chainEdges = edges.filter(e => e.id.includes('mixedChain_sequential'));

    // Assert - should have edges connecting sequential 1->2->3->4
    const edge1to2 = chainEdges.find(e => e.source === 'mixedChain_sequential1' && e.target === 'mixedChain_sequential2');
    const edge2to3 = chainEdges.find(e => e.source === 'mixedChain_sequential2' && e.target === 'mixedChain_sequential3');
    const edge3to4 = chainEdges.find(e => e.source === 'mixedChain_sequential3' && e.target === 'mixedChain_sequential4');

    expect(edge1to2).toBeDefined();
    expect(edge2to3).toBeDefined();
    expect(edge3to4).toBeDefined();

    // Should NOT have edge to sequential5 (on page 1)
    const edge4to5 = chainEdges.find(e => e.source === 'mixedChain_sequential4' && e.target === 'mixedChain_sequential5');
    expect(edge4to5).toBeUndefined();
  });

  test('ChainTask page 1 edges connect correct children_sanity', () => {
    // Arrange
    const paginationState = { mixedSwarm: 0, mixedChain: 1 };

    // Act
    const { edges } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
    const chainEdges = edges.filter(e => e.id.includes('mixedChain_sequential'));

    // Assert - should have edges connecting sequential 5->6->7->8
    const edge5to6 = chainEdges.find(e => e.source === 'mixedChain_sequential5' && e.target === 'mixedChain_sequential6');
    const edge6to7 = chainEdges.find(e => e.source === 'mixedChain_sequential6' && e.target === 'mixedChain_sequential7');
    const edge7to8 = chainEdges.find(e => e.source === 'mixedChain_sequential7' && e.target === 'mixedChain_sequential8');

    expect(edge5to6).toBeDefined();
    expect(edge6to7).toBeDefined();
    expect(edge7to8).toBeDefined();

    // Should NOT have edge from page 0 children
    const edge1to2 = chainEdges.find(e => e.source === 'mixedChain_sequential1' && e.target === 'mixedChain_sequential2');
    expect(edge1to2).toBeUndefined();
  });
});

describe('Bounds and Overlap Tests', () => {
  test.each([0, 1, 2, 3])('no overlapping nodes on swarm page %i_sanity', (pageIndex) => {
    // Arrange
    const paginationState = { mixedSwarm: pageIndex, mixedChain: 0 };

    // Act
    const { nodes } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
    const overlaps = detectNodeOverlaps(nodes);

    // Assert
    expect(overlaps).toHaveLength(0);
  });

  test.each([0, 1, 2, 3])('no overlapping nodes on chain page %i_sanity', (pageIndex) => {
    // Arrange
    const paginationState = { mixedSwarm: 0, mixedChain: pageIndex };

    // Act
    const { nodes } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
    const overlaps = detectNodeOverlaps(nodes);

    // Assert
    expect(overlaps).toHaveLength(0);
  });

  test.each([0, 1, 2, 3])('all children within parent bounds on swarm page %i_sanity', (pageIndex) => {
    // Arrange
    const paginationState = { mixedSwarm: pageIndex, mixedChain: 0 };

    // Act
    const { nodes } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
    const outsideNodes = detectNodesOutsideParent(nodes);

    // Assert
    expect(outsideNodes).toHaveLength(0);
  });

  test.each([0, 1, 2, 3])('all children within parent bounds on chain page %i_sanity', (pageIndex) => {
    // Arrange
    const paginationState = { mixedSwarm: 0, mixedChain: pageIndex };

    // Act
    const { nodes } = buildChainGraphLayout(mixedLargeExample, paginationState, {});
    const outsideNodes = detectNodesOutsideParent(nodes);

    // Assert
    expect(outsideNodes).toHaveLength(0);
  });
});

describe('Container Dimension Consistency Tests', () => {
  test.each([
    [0, 1],
    [0, 2],
    [0, 3],
  ])('SwarmTask dimensions same on page %i as page %i_sanity', (pageA, pageB) => {
    // Arrange
    const stateA = { mixedSwarm: pageA, mixedChain: 0 };
    const stateB = { mixedSwarm: pageB, mixedChain: 0 };

    // Act
    const { nodes: nodesA } = buildChainGraphLayout(mixedLargeExample, stateA, {});
    const { nodes: nodesB } = buildChainGraphLayout(mixedLargeExample, stateB, {});

    const swarmA = nodesA.find(n => n.id === 'mixedSwarm');
    const swarmB = nodesB.find(n => n.id === 'mixedSwarm');

    // Assert - dimensions should be the same across pages
    expect(swarmA.style.width).toBe(swarmB.style.width);
    expect(swarmA.style.height).toBe(swarmB.style.height);
  });

  test.each([
    [0, 1],
    [0, 2],
    [0, 3],
  ])('ChainTask dimensions same on page %i as page %i_sanity', (pageA, pageB) => {
    // Arrange
    const stateA = { mixedSwarm: 0, mixedChain: pageA };
    const stateB = { mixedSwarm: 0, mixedChain: pageB };

    // Act
    const { nodes: nodesA } = buildChainGraphLayout(mixedLargeExample, stateA, {});
    const { nodes: nodesB } = buildChainGraphLayout(mixedLargeExample, stateB, {});

    const chainA = nodesA.find(n => n.id === 'mixedChain');
    const chainB = nodesB.find(n => n.id === 'mixedChain');

    // Assert - dimensions should be the same across pages
    expect(chainA.style.width).toBe(chainB.style.width);
    expect(chainA.style.height).toBe(chainB.style.height);
  });
});
