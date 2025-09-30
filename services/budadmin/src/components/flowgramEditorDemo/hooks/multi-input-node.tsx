import { nanoid } from 'nanoid';
import { FlowNodeRegistry, ValidateTrigger } from '@flowgram.ai/fixed-layout-editor';

export const MultiInputNode: FlowNodeRegistry[] = [
  {
    type: 'multiInputs',
    meta: {},
    onAdd() {
      return {
        id: `multiInputs_${nanoid(5)}`,
        type: 'multiInputs',
        data: {
          title: 'Multiple Inputs Node',
          inputs: [
            { id: nanoid(5), label: 'Input 1', value: '' },
            { id: nanoid(5), label: 'Input 2', value: '' },
            { id: nanoid(5), label: 'Input 3', value: '' },
          ],
        },
      };
    },
    formMeta: {
      validateTrigger: ValidateTrigger.onChange,
      validate: {
        inputs: ({ value }) => (value.length > 0 ? undefined : 'At least one input is required'),
      },
      render: ({ form }) => (
        <>
          {form?.render()}
          <button onClick={() => form?.addInput()}>+ Add Input</button>
        </>
      ),
    },
  },
  // ... other node registries
];
