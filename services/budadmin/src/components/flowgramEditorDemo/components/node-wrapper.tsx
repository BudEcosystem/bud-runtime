/**
 * Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
 * SPDX-License-Identifier: MIT
 */

import React from 'react';
import { FlowNodeEntity } from '@flowgram.ai/fixed-layout-editor';
import { BaseNode } from './base-node';

interface NodeWrapperProps {
  node: FlowNodeEntity;
  onNodeClick?: (nodeType: string, nodeId: string, nodeData: any) => void;
}

export const NodeWrapper: React.FC<NodeWrapperProps> = ({ node, onNodeClick, ...props }) => {
  const handleClick = (e: React.MouseEvent) => {
    // Don't interfere with node deletion or other interactions
    if ((e.target as HTMLElement).closest('.delete-node')) {
      return;
    }

    if (onNodeClick && node) {
      const nodeType = node.type || 'unknown';
      const nodeId = node.id;
      const nodeData = {
        type: nodeType,
        title: (node as any).data?.title,
        fullNode: node
      };

      onNodeClick(nodeType, nodeId, nodeData);
    }
  };

  return (
    <div onClick={handleClick} style={{ cursor: 'pointer', width: '100%', height: '100%' }}>
      <BaseNode node={node} {...props} />
    </div>
  );
};
