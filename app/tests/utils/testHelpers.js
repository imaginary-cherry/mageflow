/**
 * Test utility functions for React Flow node analysis
 */

/**
 * Check if one node is a parent/ancestor of another (or vice versa)
 * @param {object} nodeA - First node
 * @param {object} nodeB - Second node
 * @param {Array} allNodes - All nodes for parent lookup
 * @returns {boolean} - True if one is ancestor of the other
 */
function isParentChild(nodeA, nodeB, allNodes) {
  const nodeMap = new Map(allNodes.map(n => [n.id, n]));
  
  // Check if nodeA is ancestor of nodeB
  let current = nodeMap.get(nodeB.parentNode);
  while (current) {
    if (current.id === nodeA.id) return true;
    current = nodeMap.get(current.parentNode);
  }
  
  // Check if nodeB is ancestor of nodeA
  current = nodeMap.get(nodeA.parentNode);
  while (current) {
    if (current.id === nodeB.id) return true;
    current = nodeMap.get(current.parentNode);
  }
  
  return false;
}

/**
 * Check if two rectangular nodes overlap
 * @returns {{x: *, y: *}} - True if nodes overlap
 * @param node
 * @param nodeMap
 */
function getAbsolutePosition(node, nodeMap) {
  let x = node.position.x;
  let y = node.position.y;
  let current = nodeMap.get(node.parentNode);
  while (current) {
    x += current.position.x;
    y += current.position.y;
    current = nodeMap.get(current.parentNode);
  }
  return { x, y };
}

export function nodesOverlap(nodeA, nodeB, allNodes = null) {
  if (!nodeA || !nodeB) return false;
  
  // For React Flow: calculate absolute positions if nodes have parentNode
  let aLeft = nodeA.position.x;
  let aTop = nodeA.position.y;
  let bLeft = nodeB.position.x;
  let bTop = nodeB.position.y;
  
  // If nodes have parents and we have access to all nodes, calculate absolute positions
  if (allNodes) {
    const nodeMap = new Map(allNodes.map(n => [n.id, n]));

    const aAbsolute = getAbsolutePosition(nodeA, nodeMap);
    aLeft = aAbsolute.x;
    aTop = aAbsolute.y;

    const bAbsolute = getAbsolutePosition(nodeB, nodeMap);
    bLeft = bAbsolute.x;
    bTop = bAbsolute.y;
  }
  
  const aRight = aLeft + (nodeA.style?.width || nodeA.data?.width || 180);
  const aBottom = aTop + (nodeA.style?.height || nodeA.data?.height || 60);
  
  const bRight = bLeft + (nodeB.style?.width || nodeB.data?.width || 180);
  const bBottom = bTop + (nodeB.style?.height || nodeB.data?.height || 60);
  
  // Check if rectangles don't overlap (easier to check the inverse)
  const noOverlap = (
    aRight <= bLeft ||   // A is to the left of B
    bRight <= aLeft ||   // B is to the left of A
    aBottom <= bTop ||   // A is above B
    bBottom <= aTop      // B is above A
  );
  
  return !noOverlap;
}

/**
 * Detect all overlapping node pairs in a node list
 * @param {Array} nodes - Array of React Flow nodes
 * @returns {Array<{nodeA: object, nodeB: object}>} - Array of overlapping pairs
 */
export function detectNodeOverlaps(nodes) {
  const overlaps = [];
  
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const nodeA = nodes[i];
      const nodeB = nodes[j];
      
      // Skip if one is a parent/ancestor of the other (containers contain children)
      if (isParentChild(nodeA, nodeB, nodes)) {
        continue;
      }
      
      if (nodesOverlap(nodeA, nodeB, nodes)) {
        overlaps.push({ nodeA, nodeB });
      }
    }
  }
  
  return overlaps;
}

/**
 * Check if all child nodes are properly contained within their parent
 * @param {Array} nodes - Array of React Flow nodes
 * @returns {Array} - Array of nodes that are outside their parent bounds
 */
export function detectNodesOutsideParent(nodes) {
  const outsideNodes = [];
  
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  
  nodes.forEach(node => {
    if (!node.parentNode) return;
    
    const parent = nodeMap.get(node.parentNode);
    if (!parent) return;
    
    // For React Flow: child positions are relative to parent when parentNode is set
    // Calculate absolute positions for comparison
    const childAbsLeft = parent.position.x + node.position.x;
    const childAbsRight = childAbsLeft + (node.style?.width || node.data?.width || 180);
    const childAbsTop = parent.position.y + node.position.y;
    const childAbsBottom = childAbsTop + (node.style?.height || node.data?.height || 60);
    
    const parentLeft = parent.position.x;
    const parentRight = parentLeft + (parent.style?.width || parent.data?.width || 400);
    const parentTop = parent.position.y;
    const parentBottom = parentTop + (parent.style?.height || parent.data?.height || 150);
    
    // Check if child is outside parent bounds (comparing absolute positions)
    if (childAbsLeft < parentLeft || 
        childAbsRight > parentRight || 
        childAbsTop < parentTop || 
        childAbsBottom > parentBottom) {
      outsideNodes.push({
        child: node,
        parent,
        bounds: {
          child: { left: childAbsLeft, right: childAbsRight, top: childAbsTop, bottom: childAbsBottom },
          parent: { left: parentLeft, right: parentRight, top: parentTop, bottom: parentBottom }
        }
      });
    }
  });
  
  return outsideNodes;
}

/**
 * Format node positions for debugging
 * @param {Array} nodes - Array of React Flow nodes
 * @returns {string} - Formatted string of node positions
 */
export function formatNodePositions(nodes) {
  return nodes
    .map(node => {
      const width = node.style?.width || node.data?.width || 'auto';
      const height = node.style?.height || node.data?.height || 'auto';
      const parent = node.parentNode ? ` parent:${node.parentNode}` : '';
      return `${node.id}: pos(${node.position.x}, ${node.position.y}) size(${width}, ${height})${parent}`;
    })
    .join('\n');
}

/**
 * Check minimum spacing between sibling nodes (same parent)
 * @param {Array} nodes - Array of React Flow nodes
 * @param {number} minSpacing - Minimum required spacing in pixels
 * @returns {Array} - Array of node pairs that are too close
 */
export function detectInsufficientSpacing(nodes, minSpacing = 20) {
  const tooClose = [];
  
  // Group nodes by parent
  const nodesByParent = new Map();
  nodes.forEach(node => {
    const parentId = node.parentNode || 'root';
    if (!nodesByParent.has(parentId)) {
      nodesByParent.set(parentId, []);
    }
    nodesByParent.get(parentId).push(node);
  });
  
  // Check spacing within each parent group
  nodesByParent.forEach((siblings, parentId) => {
    for (let i = 0; i < siblings.length; i++) {
      for (let j = i + 1; j < siblings.length; j++) {
        const nodeA = siblings[i];
        const nodeB = siblings[j];
        
        const aRight = nodeA.position.x + (nodeA.style?.width || nodeA.data?.width || 180);
        const bLeft = nodeB.position.x;
        const bRight = nodeB.position.x + (nodeB.style?.width || nodeB.data?.width || 180);
        const aLeft = nodeA.position.x;
        
        // Calculate horizontal spacing (assuming horizontal layout)
        let spacing;
        if (aRight <= bLeft) {
          spacing = bLeft - aRight; // A is to the left of B
        } else if (bRight <= aLeft) {
          spacing = aLeft - bRight; // B is to the left of A
        } else {
          spacing = -1; // They overlap
        }
        
        if (spacing >= 0 && spacing < minSpacing) {
          tooClose.push({
            nodeA,
            nodeB,
            actualSpacing: spacing,
            requiredSpacing: minSpacing,
            parentId
          });
        }
      }
    }
  });
  
  return tooClose;
}