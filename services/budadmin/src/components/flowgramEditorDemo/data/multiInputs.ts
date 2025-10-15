import { FlowDocumentJSON } from '@flowgram.ai/fixed-layout-editor';

export const multiInputs: FlowDocumentJSON = {
  nodes: [
    {
      id: 'multiInputs_0',
      type: 'multiInputs',
      data: {
        title: 'Input',
        inputs: [],
      },
    },
    {
      id: 'cardInput_0',
      type: 'cardInput',
      data: {
        title: 'Card Input',
        description: '',
        inputs: [],
      },
    },
    {
      id: 'systemPrompt_0',
      type: 'systemPrompt',
      data: { title: 'System Prompt', placeholder: 'Enter System Prompt' },
    },
    {
      id: 'promptMessages_0',
      type: 'promptMessages',
      data: { title: 'Prompt Messages', placeholder: 'Enter Prompt Messages' },
    },
    {
      id: 'outputMessages_0',
      type: 'output',
      data: { title: 'Output', placeholder: 'Enter Prompt Messages' },
    },
  ],
  connections: [
    { from: 'multiInputs_0', to: 'cardInput_0' },
    { from: 'cardInput_0', to: 'systemPrompt_0' },
    { from: 'systemPrompt_0', to: 'promptMessages_0' },
    { from: 'promptMessages_0', to: 'outputMessages_0' },
  ],
} as any;
