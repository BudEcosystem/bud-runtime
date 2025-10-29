import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import PromptForm from '../PromptForm';
import React from 'react';

const mockGetPromptConfig = vi.fn();
const mockUseAuth = vi.fn();

vi.mock('@/app/lib/api', () => ({
  getPromptConfig: (...args: unknown[]) => mockGetPromptConfig(...args),
}));

vi.mock('@/app/context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

const structuredResponse = {
  data: {
    input_schema: {
      place: {
        type: 'string',
        title: 'place',
        description: 'Where should the story happen?',
      },
    },
    deployment_name: 'gpt-4o-mini',
    version: '9',
  },
};

const unstructuredResponse = {
  data: {
    input_schema: null,
    deployment_name: 'gpt-4o-mini',
    version: '1',
  },
};

describe('PromptForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({ apiKey: 'api-key', accessKey: 'access-key' });
  });

  it('fetches prompt config and submits structured variables payload', async () => {
    mockGetPromptConfig.mockResolvedValueOnce(structuredResponse);
    const onSubmit = vi.fn();

    render(<PromptForm promptIds={['pmpt_structured']} onSubmit={onSubmit} />);

    await waitFor(() => {
      expect(mockGetPromptConfig).toHaveBeenCalledWith('pmpt_structured', 'api-key', 'access-key');
    });

    const placeInput = await screen.findByPlaceholderText('place');
    fireEvent.change(placeInput, { target: { value: 'kerala' } });

    const submitButton = screen.getByRole('button', { name: /next/i });
    fireEvent.click(submitButton);

    expect(onSubmit).toHaveBeenCalledWith({
      prompt: {
        id: 'pmpt_structured',
        version: '9',
        variables: {
          place: 'kerala',
        },
      },
      variables: {
        place: 'kerala',
      },
      promptId: 'pmpt_structured',
      model: 'gpt-4o-mini',
    });
  });

  it('submits unstructured payload when schema is absent', async () => {
    mockGetPromptConfig.mockResolvedValueOnce(unstructuredResponse);
    const onSubmit = vi.fn();

    render(<PromptForm promptIds={['39c5a1b2-dcd9-43e5-9562-52d7178f07c5']} onSubmit={onSubmit} />);

    await waitFor(() => {
      expect(mockGetPromptConfig).toHaveBeenCalledWith(
        '39c5a1b2-dcd9-43e5-9562-52d7178f07c5',
        'api-key',
        'access-key',
      );
    });

    const unstructuredInput = await screen.findByPlaceholderText('Enter the details here');
    fireEvent.change(unstructuredInput, {
      target: { value: "Create a person json response with name 'John' and age 30." },
    });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      prompt: {
        id: '39c5a1b2-dcd9-43e5-9562-52d7178f07c5',
        version: '1',
      },
      promptId: '39c5a1b2-dcd9-43e5-9562-52d7178f07c5',
      model: 'gpt-4o-mini',
      input: "Create a person json response with name 'John' and age 30.",
    });
  });
});
