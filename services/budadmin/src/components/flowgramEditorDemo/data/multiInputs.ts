import { FlowDocumentJSON } from '@flowgram.ai/fixed-layout-editor';

export const multiInputs: FlowDocumentJSON = {
  nodes: [
    {
      id: 'input_0',
      type: 'input',  // this node holds multiple inputs
      data: { title: 'Input' ,
        inputs: [
          { id: 'input_1', label: 'Input 1', value: '' },
          { id: 'input_2', label: 'Input 2', value: '' },
          { id: 'input_3', label: 'Input 3', value: '' },
        ],
      },
      // blocks: [
      //   {
      //     id: 'inputVar_1',
      //     type: 'input', // sub-input inside the main node
      //     data: { title: 'Input Variable 1' },
      //   },
      //   {
      //     id: 'inputVar_2',
      //     type: 'input',
      //     data: { title: 'Input Variable 2' },
      //   },
      //   {
      //     id: 'inputVar_3',
      //     type: 'input',
      //     data: { title: 'Input Variable 3' },
      //   },
      // ],
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
    { from: 'input_0', to: 'systemPrompt_0' },
    { from: 'systemPrompt_0', to: 'promptMessages_0' },
    { from: 'promptMessages_0', to: 'outputMessages_0' },
  ],
} as any;
