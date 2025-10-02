/**
 * Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
 * SPDX-License-Identifier: MIT
 */

import React from 'react';
import { nanoid } from 'nanoid';
import { FlowNodeRegistry } from '@flowgram.ai/fixed-layout-editor';
import { MultiInputCard } from './components/multi-input-card';
import { OutputCard } from './components/output-card';
import { SystemPromptCard } from './components/system-prompt-card';
import { PromptMessagesCard } from './components/prompt-messages-card';

/**
 * 自定义节点注册
 */
export const nodeRegistries: FlowNodeRegistry[] = [
  {
    /**
     * 自定义节点类型
     */
    type: 'condition',
    /**
     * 自定义节点扩展:
     *  - loop: 扩展为循环节点
     *  - start: 扩展为开始节点
     *  - dynamicSplit: 扩展为分支节点
     *  - end: 扩展为结束节点
     *  - tryCatch: 扩展为 tryCatch 节点
     *  - break: 分支断开
     *  - default: 扩展为普通节点 (默认)
     */
    extend: 'dynamicSplit',
    /**
     * 节点配置信息
     */
    meta: {
      // isStart: false, // 是否为开始节点
      // isNodeEnd: false, // 是否为结束节点，结束节点后边无法再添加节点
      // draggable: false, // 是否可拖拽，如开始节点和结束节点无法拖拽
      // selectable: false, // 触发器等开始节点不能被框选
      // deleteDisable: true, // 禁止删除
      // copyDisable: true, // 禁止copy
      // addDisable: true, // 禁止添加
    },
    onAdd() {
      return {
        id: `condition_${nanoid(5)}`,
        type: 'condition',
        data: {
          title: 'Condition',
        },
        blocks: [
          {
            id: nanoid(5),
            type: 'block',
            data: {
              title: 'If_0',
            },
          },
          {
            id: nanoid(5),
            type: 'block',
            data: {
              title: 'If_1',
            },
          },
        ],
      };
    },
  },
  {
    type: 'custom',
    meta: {},
    onAdd() {
      return {
        id: `custom_${nanoid(5)}`,
        type: 'custom',
        data: {
          title: 'Custom',
          content: 'this is custom content',
        },
      };
    },
  },
  {
    type: 'multiInputs',
    meta: {},
    onAdd() {
      return {
        id: `multiInputs_${nanoid(5)}`,
        type: 'multiInputs',
        data: {
          title: 'Input',
          inputs: [],
        },
      };
    },
    formMeta: {
      render: () => <MultiInputCard />,
    },
  },
  {
    type: 'end',
    meta: {},
    onAdd() {
      return {
        id: `end_${nanoid(5)}`,
        type: 'end',
        data: { title: 'End' },
      };
    },
  },
  {
    type: 'drag-node',
    meta: {},
    onAdd() {
      return {
        id: `end_${nanoid(5)}`,
        type: 'end',
        data: { title: 'End' },
      };
    },
  },
  {
    type: 'cardInput',
    meta: {
      defaultExpanded: true,
    },
    onAdd() {
      return {
        id: `cardInput_${nanoid(5)}`,
        type: 'cardInput',
        data: {
          title: 'Card Input',
          description: '',
          inputs: [],
        },
      };
    },
    formMeta: {
      render: () => <MultiInputCard />,
    },
  },
  {
    type: 'systemPrompt',
    meta: {
      defaultExpanded: true,
    },
    onAdd() {
      return {
        id: `systemPrompt_${nanoid(5)}`,
        type: 'systemPrompt',
        data: {
          title: 'System Prompt',
          placeholder: 'Enter System Prompt',
        },
      };
    },
    formMeta: {
      render: () => <SystemPromptCard />,
    },
  },
  {
    type: 'promptMessages',
    meta: {
      defaultExpanded: true,
    },
    onAdd() {
      return {
        id: `promptMessages_${nanoid(5)}`,
        type: 'promptMessages',
        data: {
          title: 'Prompt Messages',
          placeholder: 'Enter Prompt Messages',
        },
      };
    },
    formMeta: {
      render: () => <PromptMessagesCard />,
    },
  },
  {
    type: 'output',
    meta: {
      defaultExpanded: true,
    },
    onAdd() {
      return {
        id: `output_${nanoid(5)}`,
        type: 'output',
        data: {
          title: 'Output',
          placeholder: 'Output will appear here',
        },
      };
    },
    formMeta: {
      render: () => <OutputCard />,
    },
  },
];
