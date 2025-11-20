"use client";

import { useState, useEffect } from 'react';
import { Input, InputNumber, Checkbox, Image, message } from 'antd';
import { getPromptConfig } from '@/app/lib/api';
import { useAuth } from '@/app/context/AuthContext';
import { useChatStore } from '@/app/store/chat';
import { useEndPoints } from '@/app/components/bud/hooks/useEndPoint';

interface PromptFormProps {
  promptIds?: string[];
  chatId?: string;
  onSubmit: (data: any) => void;
  onClose?: () => void;
}

export default function PromptForm({ promptIds = [], chatId, onSubmit, onClose: _onClose }: PromptFormProps) {
  const { apiKey, accessKey } = useAuth();
  const getChat = useChatStore((state) => state.getChat);
  const setDeployment = useChatStore((state) => state.setDeployment);
  const setDeploymentLock = useChatStore((state) => state.setDeploymentLock);
  const { endpoints, getEndPoints, isReady } = useEndPoints();
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [inputSchema, setInputSchema] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const [promptVersion, setPromptVersion] = useState<string | undefined>();
  const [promptDeployment, setPromptDeployment] = useState<string | undefined>();
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Listen for multiple events to trigger refresh when returning to playground
  useEffect(() => {
    // Handler for postMessage events
    const handleMessage = (event: MessageEvent) => {
      if (event.data && event.data.type === 'SET_TYPE_FORM') {
        setRefreshTrigger(prev => prev + 1);
        console.log('[PromptForm] Received SET_TYPE_FORM postMessage, triggering refresh');
      }
    };

    // Handler for visibility change (tab switch)
    const handleVisibilityChange = () => {
      if (!document.hidden && promptIds.length > 0) {
        setRefreshTrigger(prev => prev + 1);
        console.log('[PromptForm] Window became visible, triggering refresh');
      }
    };

    // Handler for window focus
    const handleFocus = () => {
      if (promptIds.length > 0) {
        setRefreshTrigger(prev => prev + 1);
        console.log('[PromptForm] Window focused, triggering refresh');
      }
    };

    // Add all event listeners
    window.addEventListener('message', handleMessage);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);

    // Cleanup
    return () => {
      window.removeEventListener('message', handleMessage);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [promptIds]);

  // Fetch prompt configurations - runs when dependencies change or refresh triggered
  useEffect(() => {
    const fetchPromptConfigs = async () => {
      if (promptIds.length === 0) {
        setLoading(false);
        return;
      }

      try {
        console.log('[PromptForm] Fetching prompt config for:', promptIds[0]);
        const config = await getPromptConfig(promptIds[0], apiKey || '', accessKey || '');

        if (config && config.data) {
          const version =
            config.data?.version ?? config.data?.prompt?.version ?? undefined;
          setPromptVersion(
            version !== undefined && version !== null ? String(version) : undefined
          );

          const newDeploymentName = typeof config.data?.deployment_name === 'string'
            ? config.data.deployment_name
            : undefined;

          console.log('[PromptForm] API returned deployment_name:', newDeploymentName);

          // Always update deployment name when API returns a value
          setPromptDeployment(newDeploymentName);

          // Handle JSON schema format - extract properties from $defs
          let schemaToUse: any = config.data.input_schema ?? null;

          // If it's a JSON schema with $defs, flatten it for the form
          // Check for both "Input" and "InputSchema" in $defs
          if (schemaToUse && schemaToUse.$defs) {
            if (schemaToUse.$defs.Input) {
              schemaToUse = schemaToUse.$defs.Input.properties || {};
            } else if (schemaToUse.$defs.InputSchema) {
              schemaToUse = schemaToUse.$defs.InputSchema.properties || {};
            }
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
  }, [promptIds, apiKey, accessKey, refreshTrigger]);

  // Fetch endpoints when ready and deployment name is available
  useEffect(() => {
    if (isReady && promptDeployment && chatId) {
      getEndPoints({ page: 1, limit: 100 });
    }
  }, [isReady, promptDeployment, chatId, getEndPoints]);

  // Auto-select deployment when endpoints are loaded or deployment name changes
  useEffect(() => {
    console.log('[PromptForm Auto-select] Triggered with:', {
      promptDeployment,
      endpointsCount: endpoints?.length,
      chatId
    });

    if (promptDeployment && endpoints && endpoints.length > 0 && chatId) {
      const chat = getChat(chatId);
      const currentDeploymentName = chat?.selectedDeployment?.name;

      console.log('[PromptForm Auto-select] Current deployment:', currentDeploymentName);
      console.log('[PromptForm Auto-select] Target deployment:', promptDeployment);

      // Find matching endpoint by name or ID
      const matchingEndpoint = endpoints.find(
        (ep) => ep.name === promptDeployment || ep.id === promptDeployment
      );

      if (matchingEndpoint) {
        console.log('[PromptForm Auto-select] Found matching endpoint:', matchingEndpoint.name);

        // Update deployment if it's different from current selection
        if (currentDeploymentName !== matchingEndpoint.name) {
          console.log('[PromptForm Auto-select] Updating deployment from', currentDeploymentName, 'to', matchingEndpoint.name);
          setDeployment(chatId, matchingEndpoint);
          setDeploymentLock(chatId, true);
        } else {
          console.log('[PromptForm Auto-select] Deployment already set, no update needed');
        }
      } else {
        console.warn('[PromptForm Auto-select] Deployment not found in endpoints:', promptDeployment);
        console.warn('[PromptForm Auto-select] Available endpoints:', endpoints.map(ep => ep.name));
      }
    }
  }, [promptDeployment, endpoints, chatId, setDeployment, setDeploymentLock, getChat]);

  const handleChange = (fieldName: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [fieldName]: value
    }));
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
      // Structured input - send variables wrapped in content object
      const variables: Record<string, any> = {};
      Object.keys(formData).forEach(key => {
        if (formData[key] !== undefined && formData[key] !== '') {
          variables[key] = formData[key];
        }
      });

      if (Object.keys(variables).length > 0) {
        // Wrap variables in content object to match schema structure
        const wrappedVariables = { content: variables };
        payload.prompt.variables = wrappedVariables;
        payload.variables = wrappedVariables;
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

    const inputClassName = "bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] !px-0 py-2";

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
      <div className="chat-message-form p-[2.5rem] pb-[1.5rem]  w-full  flex items-center justify-center  border-t-2 hover:border-[#333333] rounded-[0.625rem] bg-[#101010] relative z-10 overflow-hidden max-w-5xl">
        <form onSubmit={handleSubmit} className="space-y-6 w-full">
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
                  Message
                </label>
                <Input
                  value={formData['unstructuredSchema'] || ''}
                  onChange={(e) => handleChange('unstructuredSchema', e.target.value)}
                  placeholder="Enter the details here"
                  className="bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] !px-0 py-2"
                  style={{ boxShadow: 'none' }}
                />
              </div>
            </>
          )}

          {/* Buttons */}
          <div className="flex justify-end items-center">
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
