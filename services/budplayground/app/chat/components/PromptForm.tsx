"use client";

import { useState, useEffect } from 'react';
import { Input, InputNumber, Checkbox, Image, message } from 'antd';
import { getPromptConfig } from '@/app/lib/api';
import { useAuth } from '@/app/context/AuthContext';
import { useChatStore } from '@/app/store/chat';

interface PromptFormProps {
  promptIds?: string[];
  chatId?: string;
  onSubmit: (data: any) => void;
  onClose?: () => void;
}

export default function PromptForm({ promptIds = [], chatId, onSubmit, onClose: _onClose }: PromptFormProps) {
  const { apiKey, accessKey } = useAuth();
  const getChat = useChatStore((state) => state.getChat);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [inputSchema, setInputSchema] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const [isTestHovered, setIsTestHovered] = useState<boolean>(false);
  const [testLoading, setTestLoading] = useState<boolean>(false);
  const [promptVersion, setPromptVersion] = useState<string | undefined>();
  const [promptDeployment, setPromptDeployment] = useState<string | undefined>();

  // Fetch prompt configurations on mount
  useEffect(() => {
    const fetchPromptConfigs = async () => {
      if (promptIds.length === 0) {
        setLoading(false);
        return;
      }

      try {
        const config = await getPromptConfig(promptIds[0], apiKey || '', accessKey || '');

        if (config && config.data) {
          const version =
            config.data?.version ?? config.data?.prompt?.version ?? undefined;
          setPromptVersion(
            version !== undefined && version !== null ? String(version) : undefined
          );

          setPromptDeployment(
            typeof config.data?.deployment_name === 'string'
              ? config.data.deployment_name
              : undefined
          );

          // Handle JSON schema format - extract properties from $defs
          let schemaToUse: any = config.data.input_schema ?? null;

          // If it's a JSON schema with $defs, flatten it for the form
          if (schemaToUse && schemaToUse.$defs && schemaToUse.$defs.InputSchema) {
            schemaToUse = schemaToUse.$defs.InputSchema.properties || {};
          }

          if (
            schemaToUse &&
            typeof schemaToUse === 'object' &&
            Object.keys(schemaToUse).length === 0
          ) {
            schemaToUse = null;
          }

          setInputSchema(schemaToUse);

          // Initialize form data with default values
          const initialData: Record<string, any> = {};
          if (schemaToUse && typeof schemaToUse === 'object') {
            Object.keys(schemaToUse).forEach((key: string) => {
              const field = schemaToUse[key];
              initialData[key] = field?.default || '';
            });
          } else {
            initialData['unstructuredSchema'] = '';
          }
          setFormData(initialData);
        } else {
          setInputSchema(null);
          setFormData({ unstructuredSchema: '' });
          setPromptVersion(undefined);
        }
      } catch (error) {
        console.error('Error fetching prompt config:', error);
        setInputSchema(null);
        setFormData({ unstructuredSchema: '' });
        setPromptVersion(undefined);
        setPromptDeployment(undefined);
      } finally {
        setLoading(false);
      }
    };

    fetchPromptConfigs();
  }, [promptIds, apiKey, accessKey]);

  const handleChange = (fieldName: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [fieldName]: value
    }));
  };

  const handleTestOpenAIResponses = async () => {
    setTestLoading(true);

    try {
      // Get the selected deployment from chat store
      let modelToUse = 'gpt-4o'; // fallback

      if (chatId) {
        const chat = getChat(chatId);
        if (chat?.selectedDeployment) {
          // Use the deployment name (which is the model identifier)
          modelToUse = chat.selectedDeployment.name;
          console.log('[PromptForm] Using selected deployment:', chat.selectedDeployment);
        }
      }

      // Fallback to prompt deployment if no chat deployment selected
      if (!chatId && promptDeployment) {
        modelToUse = promptDeployment;
      }

      const testData = {
        prompt: 'Explain the concept of quantum entanglement in simple terms.',
        model: modelToUse,
        metadata: {
          project_id: 'test-project-id',
        },
      };

      console.log('[PromptForm] Testing OpenAI Responses with data:', testData);
      console.log('[PromptForm] Using model/deployment:', modelToUse);

      // Build headers
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (accessKey) {
        headers['Authorization'] = `Bearer ${accessKey}`;
      }
      if (apiKey) {
        headers['api-key'] = apiKey;
      }

      const response = await fetch('/api/test-openai-responses', {
        method: 'POST',
        headers,
        body: JSON.stringify(testData),
      });

      const result = await response.json();

      if (response.ok && result.success) {
        message.success('OpenAI Responses test successful!');
        console.log('[PromptForm] Test result:', result);
        console.log('[PromptForm] Generated text:', result.text);
        console.log('[PromptForm] Usage:', result.usage);
        console.log('[PromptForm] Provider metadata:', result.providerMetadata);
      } else {
        message.error(`Test failed: ${result.error || 'Unknown error'}`);
        console.error('[PromptForm] Test failed:', result);
      }
    } catch (error: any) {
      message.error(`Test error: ${error?.message || 'Unknown error'}`);
      console.error('[PromptForm] Test error:', error);
    } finally {
      setTestLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (promptIds.length === 0) {
      console.error('No prompt ID available');
      return;
    }

    const promptId = promptIds[0];

    const payload: {
      prompt: {
        id: string;
        version?: string;
        variables?: Record<string, any>;
      };
      input?: string;
      model?: string;
      promptId?: string;
      variables?: Record<string, any>;
    } = {
      prompt: {
        id: promptId,
      },
      promptId,
    };

    if (promptVersion) {
      payload.prompt.version = promptVersion;
    }
    if (promptDeployment) {
      payload.model = promptDeployment;
    }

    // Check if it's structured or unstructured input
    if (inputSchema && Object.keys(inputSchema).length > 0) {
      // Structured input - send variables
      const variables: Record<string, any> = {};
      Object.keys(formData).forEach(key => {
        if (formData[key] !== undefined && formData[key] !== '') {
          variables[key] = formData[key];
        }
      });

      if (Object.keys(variables).length > 0) {
        payload.prompt.variables = variables;
        payload.variables = variables;
      }
    } else {
      // Unstructured input - send input field
      payload.input = formData['unstructuredSchema'] || '';
    }

    // Pass the prompt data to parent to initiate chat
    onSubmit(payload);
  };

  const renderInput = (fieldName: string, fieldSchema: any) => {
    const { type, title, placeholder, minimum, maximum } = fieldSchema;

    const inputClassName = "bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] px-0 py-2";

    switch (type) {
      case 'string':
        return (
          <Input
            value={formData[fieldName] || ''}
            onChange={(e) => handleChange(fieldName, e.target.value)}
            placeholder={placeholder || title || fieldName}
            className={inputClassName}
            style={{ boxShadow: 'none' }}
          />
        );

      case 'number':
      case 'integer':
        return (
          <InputNumber
            value={formData[fieldName]}
            onChange={(value) => handleChange(fieldName, value)}
            placeholder={placeholder || title || fieldName}
            min={minimum}
            max={maximum}
            className={inputClassName}
            style={{ boxShadow: 'none', width: '100%' }}
          />
        );

      case 'boolean':
        return (
          <Checkbox
            checked={formData[fieldName] || false}
            onChange={(e) => handleChange(fieldName, e.target.checked)}
            className="text-white"
          >
            {title || fieldName}
          </Checkbox>
        );

      default:
        return (
          <Input
            value={formData[fieldName] || ''}
            onChange={(e) => handleChange(fieldName, e.target.value)}
            placeholder={placeholder || title || fieldName}
            className={inputClassName}
            style={{ boxShadow: 'none' }}
          />
        );
    }
  };

  if (loading) {
    return (
      <div className="absolute bottom-0 left-0 right-0 z-50 flex items-end justify-center p-[0.9375rem] pb-[.5rem]">
        <div className="w-full max-w-[800px] bg-[#0c0c0d] rounded-[1rem] border border-[#1F1F1F] p-8 shadow-2xl">
          <div className="text-white text-center">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 z-50 flex items-end justify-center p-[0.9375rem] pb-[.5rem]">
      <div className="w-full max-w-[800px] bg-[#0c0c0d] rounded-[1rem] border border-[#1F1F1F] p-8 shadow-2xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Title */}
          <h2 className="text-white text-[1.25rem] font-[400] mb-6">
            {inputSchema?.title || 'Please enter the following details'}
          </h2>

          {/* Dynamic Fields */}
          {inputSchema && Object.keys(inputSchema).map((fieldName) => {
            const fieldSchema = inputSchema[fieldName];
            if (fieldName === 'title') return null; // Skip title field

            return (
              <div key={fieldName} className="space-y-2">
                <label className="text-white text-[0.875rem] font-[400] block">
                  {fieldName}
                </label>
                {renderInput(fieldName, fieldSchema)}
                {fieldSchema.description && (
                  <p className="text-[#666666] text-[0.75rem]">{fieldSchema.description}</p>
                )}
              </div>
            );
          })}

          {/* Fallback to default fields if no input schema */}

          {!inputSchema && (
            <>
              <div className="space-y-2">
                <label className="text-white text-[0.875rem] font-[400] block">
                  Unstructured Input
                </label>
                <Input
                  value={formData['unstructuredSchema'] || ''}
                  onChange={(e) => handleChange('unstructuredSchema', e.target.value)}
                  placeholder="Enter the details here"
                  className="bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] px-0 py-2"
                  style={{ boxShadow: 'none' }}
                />
              </div>
            </>
          )}

          {/* Buttons */}
          <div className="flex justify-between items-center">
            {/* Test OpenAI Responses Button */}
            <button
              className="Open-Sans cursor-pointer text-[400] text-[.75rem] text-[#EEEEEE] border-[#757575] border-[1px] rounded-[6px] p-[.2rem] hover:bg-[#1F1F1F4D] hover:text-[#FFFFFF] flex items-center gap-[.5rem] px-[.8rem] py-[.15rem] bg-[#1F1F1F] hover:bg-[#4CAF50] hover:text-[#FFFFFF] disabled:opacity-50 disabled:cursor-not-allowed"
              type="button"
              onClick={handleTestOpenAIResponses}
              disabled={testLoading}
              onMouseEnter={() => setIsTestHovered(true)}
              onMouseLeave={() => setIsTestHovered(false)}
            >
              {testLoading ? 'Testing...' : 'Test OpenAI Responses'}
            </button>

            {/* Next Button */}
            <button
              className="Open-Sans cursor-pointer text-[400] text-[.75rem] text-[#EEEEEE] border-[#757575] border-[1px] rounded-[6px] p-[.2rem] hover:bg-[#1F1F1F4D] hover:text-[#FFFFFF] flex items-center gap-[.5rem] px-[.8rem] py-[.15rem] bg-[#1F1F1F] hover:bg-[#965CDE] hover:text-[#FFFFFF]"
              type="submit"
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
            >
              Next
              <div className="w-[1.25rem] h-[1.25rem]">
                <Image
                  src={isHovered ? "icons/send-white.png" : "icons/send.png"}
                  alt="send"
                  preview={false}
                />
              </div>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
