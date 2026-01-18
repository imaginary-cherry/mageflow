export const parseNodePosition = (nodeElement) => {
  const transform = nodeElement.style.transform;
  if (!transform) return { x: 0, y: 0 };
  
  const match = transform.match(/translate\(([\d.-]+)px,\s*([\d.-]+)px\)/);
  if (!match) return { x: 0, y: 0 };
  
  return {
    x: parseFloat(match[1]),
    y: parseFloat(match[2])
  };
};

export const getNodeBounds = (nodeElement) => {
  const position = parseNodePosition(nodeElement);
  const rect = nodeElement.getBoundingClientRect();
  
  return {
    id: nodeElement.getAttribute('data-id'),
    left: position.x,
    right: position.x + rect.width,
    top: position.y,
    bottom: position.y + rect.height,
    width: rect.width,
    height: rect.height,
    centerX: position.x + rect.width / 2,
    centerY: position.y + rect.height / 2
  };
};

export const detectOverlaps = (nodeBounds) => {
  const overlaps = [];
  
  for (let i = 0; i < nodeBounds.length; i++) {
    for (let j = i + 1; j < nodeBounds.length; j++) {
      const a = nodeBounds[i];
      const b = nodeBounds[j];
      
      const hasOverlap = !(
        a.right <= b.left ||
        a.left >= b.right ||
        a.bottom <= b.top ||
        a.top >= b.bottom
      );
      
      if (hasOverlap) {
        overlaps.push({
          nodeA: a.id,
          nodeB: b.id,
          boundsA: { left: a.left, right: a.right, top: a.top, bottom: a.bottom },
          boundsB: { left: b.left, right: b.right, top: b.top, bottom: b.bottom }
        });
      }
    }
  }
  
  return overlaps;
};

export const findRootNodes = (container) => {
  const nodes = container.querySelectorAll('.react-flow__node');
  const nodeIds = Array.from(nodes).map(node => node.getAttribute('data-id'));
  
  const edges = container.querySelectorAll('.react-flow__edge-path');
  const targetNodes = new Set();
  
  edges.forEach(edge => {
    const edgeElement = edge.closest('.react-flow__edge');
    if (edgeElement) {
      const target = edgeElement.getAttribute('data-target');
      if (target) {
        targetNodes.add(target);
      }
    }
  });
  
  return nodeIds.filter(nodeId => !targetNodes.has(nodeId));
};

export const verifyConnection = (sourceId, targetId, container) => {
  const edges = container.querySelectorAll('.react-flow__edge');
  
  return Array.from(edges).some(edge => {
    const source = edge.getAttribute('data-source');
    const target = edge.getAttribute('data-target');
    return source === sourceId && target === targetId;
  });
};

export const getConnectionsByType = (container) => {
  const edges = container.querySelectorAll('.react-flow__edge');
  const connections = {
    success: [],
    error: []
  };
  
  Array.from(edges).forEach(edge => {
    const edgeId = edge.getAttribute('data-id');
    const source = edge.getAttribute('data-source');
    const target = edge.getAttribute('data-target');
    
    if (edgeId && source && target) {
      if (edgeId.includes('-success-')) {
        connections.success.push({ source, target, element: edge });
      } else if (edgeId.includes('-error-')) {
        connections.error.push({ source, target, element: edge });
      }
    }
  });
  
  return connections;
};

export const verifyLeftToRightFlow = (nodeBounds) => {
  const violations = [];
  
  const levels = {};
  nodeBounds.forEach(bounds => {
    const level = Math.round(bounds.centerX / 10) * 10;
    if (!levels[level]) {
      levels[level] = [];
    }
    levels[level].push(bounds);
  });
  
  const sortedLevels = Object.keys(levels).sort((a, b) => parseInt(a) - parseInt(b));
  
  for (let i = 0; i < sortedLevels.length - 1; i++) {
    const currentLevel = levels[sortedLevels[i]];
    const nextLevel = levels[sortedLevels[i + 1]];
    
    const currentMaxX = Math.max(...currentLevel.map(b => b.centerX));
    const nextMinX = Math.min(...nextLevel.map(b => b.centerX));
    
    if (currentMaxX > nextMinX) {
      violations.push({
        message: `Level ${i} extends beyond level ${i + 1}: ${currentMaxX} > ${nextMinX}`,
        level: i
      });
    }
  }
  
  return violations;
};

export const waitForReactFlow = async () => {
  return new Promise((resolve) => {
    setTimeout(resolve, 100);
  });
};