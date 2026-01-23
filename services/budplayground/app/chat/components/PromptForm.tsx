"use client";

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Input, InputNumber, Checkbox, Image } from 'antd';
import { getPromptConfig } from '@/app/lib/api';
import { useAuth } from '@/app/context/AuthContext';
import { useChatStore } from '@/app/store/chat';
import { useEndPoints } from '@/app/components/bud/hooks/useEndPoint';
import { Text_12_400_B3B3B3 } from '@/lib/text';
import { parsePositiveIntParam } from '@/app/lib/query';

interface PromptFormProps {
  promptIds?: string[];
  chatId?: string;
  onSubmit: (data: any) => void;
  onClose?: () => void;
  promptConfig?: any;
}

export default function PromptForm({ promptIds = [], chatId, onSubmit, onClose, promptConfig }: PromptFormProps) {
  const { apiKey, accessKey } = useAuth();
  const getChat = useChatStore((state) => state.getChat);
  const setDeployment = useChatStore((state) => state.setDeployment);
  const setDeploymentLock = useChatStore((state) => state.setDeploymentLock);
  const { endpoints, getEndPoints, isReady } = useEndPoints();
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [inputSchema, setInputSchema] = useState<any>(null);
  const [fieldOrder, setFieldOrder] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const [promptVersion, setPromptVersion] = useState<string | undefined>();
  const [promptDeployment, setPromptDeployment] = useState<string | undefined>();
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const promptVersionParam = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return parsePositiveIntParam(params.get('version'));
  }, []);

  // Storage key for persisting form data across tab switches
  const storageKey = useMemo(() => {
    return promptIds.length > 0 ? `promptForm_${promptIds[0]}` : null;
  }, [promptIds]);

  // Helper to get saved form data from sessionStorage
  const getSavedFormData = useCallback((): Record<string, any> | null => {
    if (!storageKey) return null;
    try {
      const saved = sessionStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : null;
    } catch (error) {
      console.error("Failed to retrieve or parse form data from sessionStorage:", error);
      return null;
    }
  }, [storageKey]);

  // Helper to save form data to sessionStorage
  const saveFormData = useCallback((data: Record<string, any>) => {
    if (!storageKey) return;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(data));
    } catch (error) {
      console.error("Failed to save form data to sessionStorage:", error);
    }
  }, [storageKey]);

  // Helper to clear saved form data from sessionStorage
  const clearSavedFormData = useCallback(() => {
    if (!storageKey) return;
    try {
      sessionStorage.removeItem(storageKey);
    } catch (error) {
      console.error("Failed to remove form data from sessionStorage:", error);
    }
  }, [storageKey]);

  // Listen for multiple events to trigger refresh when returning to playground
  useEffect(() => {
    // Handler for postMessage events
    const handleMessage = (event: MessageEvent) => {
      if (event.data && event.data.type === 'SET_TYPE_FORM') {
        setRefreshTrigger(prev => prev + 1);
      }
    };

    // Handler for visibility change (tab switch)
    const handleVisibilityChange = () => {
      if (!document.hidden && promptIds.length > 0) {
        setRefreshTrigger(prev => prev + 1);
      }
    };

    // Handler for window focus
    const handleFocus = () => {
      if (promptIds.length > 0) {
        setRefreshTrigger(prev => prev + 1);
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

  const applyPromptConfig = useCallback((configData: any) => {
    const version =
      configData?.version ?? configData?.prompt?.version ?? undefined;
    setPromptVersion(
      version !== undefined && version !== null ? String(version) : undefined
    );

    const newDeploymentName = typeof configData?.deployment_name === 'string'
      ? configData.deployment_name
      : undefined;

    // Always update deployment name when API returns a value
    setPromptDeployment(newDeploymentName);

    // Handle JSON schema format - extract properties from $defs
    let schemaToUse: any = configData.input_schema ?? null;
    let requiredFields: string[] = [];

    // If it's a JSON schema with $defs, flatten it for the form
    // Check for both "Input" and "InputSchema" in $defs
    if (schemaToUse && schemaToUse.$defs) {
      if (schemaToUse.$defs.Input) {
        const inputDef = schemaToUse.$defs.Input;
        schemaToUse = inputDef.properties || {};
        requiredFields = inputDef.required || [];
      } else if (schemaToUse.$defs.InputSchema) {
        const inputDef = schemaToUse.$defs.InputSchema;
        schemaToUse = inputDef.properties || {};
        requiredFields = inputDef.required || [];
      }
    }

    if (
      schemaToUse &&
      typeof schemaToUse === 'object' &&
      Object.keys(schemaToUse).length === 0
    ) {
      schemaToUse = null;
    }

    // Determine field order: required fields first, then any remaining properties
    if (schemaToUse && typeof schemaToUse === 'object') {
      const allKeys = Object.keys(schemaToUse);
      const orderedFields = [
        ...requiredFields.filter(key => allKeys.includes(key)),
        ...allKeys.filter(key => !requiredFields.includes(key))
      ];
      setFieldOrder(orderedFields);
    } else {
      setFieldOrder([]);
    }

    setInputSchema(schemaToUse);

    // Initialize form data with default values based on type
    const initialData: Record<string, any> = {};
    if (schemaToUse && typeof schemaToUse === 'object') {
      Object.keys(schemaToUse).forEach((key: string) => {
        const field = schemaToUse[key];
        // Use type-appropriate default values
        if (field?.default !== undefined) {
          initialData[key] = field.default;
        } else {
          switch (field?.type) {
            case 'array':
              initialData[key] = [];
              break;
            case 'object':
              // Initialize as empty object for both cases
              // (with properties or using key-value pair UI)
              initialData[key] = {};
              break;
            case 'boolean':
              initialData[key] = false;
              break;
            case 'number':
            case 'integer':
              initialData[key] = null;
              break;
            default:
              initialData[key] = '';
          }
        }
      });
    } else {
      initialData['unstructuredSchema'] = '';
    }

    // Restore saved form data from sessionStorage (preserves user input across tab switches)
    const savedData = getSavedFormData();
    if (savedData) {
      // Merge saved data with initial data, only for fields that exist in current schema
      const mergedData = { ...initialData };
      Object.keys(savedData).forEach(key => {
        if (key in initialData) {
          mergedData[key] = savedData[key];
        }
      });
      setFormData(mergedData);
    } else {
      setFormData(initialData);
    }
  }, [getSavedFormData]);

  const resetPromptConfigState = useCallback(() => {
    setInputSchema(null);
    setFieldOrder([]);
    setFormData({ unstructuredSchema: '' });
    setPromptVersion(undefined);
    setPromptDeployment(undefined);
  }, []);

  // Fetch prompt configurations - runs when dependencies change or refresh triggered
  useEffect(() => {
    const fetchPromptConfigs = async () => {
      if (promptIds.length === 0) {
        setLoading(false);
        return;
      }

      if (promptConfig) {
        applyPromptConfig(promptConfig);
        setLoading(false);
        return;
      }

      setLoading(true);

      try {
        const config = await getPromptConfig(
          promptIds[0],
          apiKey || '',
          accessKey || '',
          promptVersionParam
        );

        if (config && config.data) {
          applyPromptConfig(config.data);
        } else {
          resetPromptConfigState();
        }
      } catch (error) {
        console.error('Error fetching prompt config:', error);
        resetPromptConfigState();
      } finally {
        setLoading(false);
      }
    };

    fetchPromptConfigs();
  }, [promptIds, apiKey, accessKey, refreshTrigger, promptConfig, promptVersionParam, applyPromptConfig, resetPromptConfigState]);

  // Fetch endpoints when ready and deployment name is available
  useEffect(() => {
    if (isReady && promptDeployment && chatId) {
      getEndPoints({ page: 1, limit: 100 });
    }
  }, [isReady, promptDeployment, chatId, getEndPoints]);

  // Auto-select deployment when endpoints are loaded or deployment name changes
  useEffect(() => {
    if (promptDeployment && endpoints && endpoints.length > 0 && chatId) {
      const chat = getChat(chatId);
      const currentDeploymentName = chat?.selectedDeployment?.name;

      // Find matching endpoint by name or ID
      const matchingEndpoint = endpoints.find(
        (ep) => ep.name === promptDeployment || ep.id === promptDeployment
      );

      if (matchingEndpoint) {
        // Update deployment if it's different from current selection
        if (currentDeploymentName !== matchingEndpoint.name) {
          setDeployment(chatId, matchingEndpoint);
          setDeploymentLock(chatId, true);
        }
      }
    }
  }, [promptDeployment, endpoints, chatId, setDeployment, setDeploymentLock, getChat]);

  const handleChange = (fieldName: string, value: any) => {
    setFormData(prev => {
      const newData = { ...prev, [fieldName]: value };
      saveFormData(newData);
      return newData;
    });
  };

  // Get default value for a given schema type
  const getDefaultForType = (schema: any): any => {
    switch (schema?.type) {
      case 'array': return [];
      case 'object': return {};
      case 'boolean': return false;
      case 'number':
      case 'integer': return null;
      default: return '';
    }
  };

  // Render input for array item based on item schema
  const renderArrayItemInput = (
    fieldName: string,
    index: number,
    value: any,
    itemSchema: any
  ) => {
    const itemType = itemSchema?.type || 'string';
    const inputClassName = "bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] !px-0 py-2";

    const updateArrayItem = (newValue: any) => {
      const currentArray = Array.isArray(formData[fieldName]) ? [...formData[fieldName]] : [];
      currentArray[index] = newValue;
      handleChange(fieldName, currentArray);
    };

    switch (itemType) {
      case 'number':
      case 'integer':
        return (
          <InputNumber
            value={value}
            onChange={(val) => updateArrayItem(val)}
            placeholder={`Item ${index + 1}`}
            controls={false}
            className={inputClassName}
            style={{ boxShadow: 'none', width: '100%', paddingLeft: 0 }}
          />
        );
      case 'boolean':
        return (
          <Checkbox
            checked={value || false}
            onChange={(e) => updateArrayItem(e.target.checked)}
            className="text-white"
          />
        );
      case 'object':
        // For nested objects in arrays, use JSON input for simplicity
        return (
          <Input
            value={typeof value === 'object' ? JSON.stringify(value) : value || ''}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                updateArrayItem(parsed);
              } catch {
                updateArrayItem(e.target.value);
              }
            }}
            placeholder={`{"key": "value"}`}
            className={inputClassName}
            style={{ boxShadow: 'none' }}
          />
        );
      default: // string
        return (
          <Input
            value={value || ''}
            onChange={(e) => updateArrayItem(e.target.value)}
            placeholder={`Item ${index + 1}`}
            className={inputClassName}
            style={{ boxShadow: 'none' }}
          />
        );
    }
  };

  // Render input for object property based on property schema
  const renderObjectPropertyInput = (
    fieldName: string,
    propName: string,
    value: any,
    propSchema: any
  ) => {
    const propType = propSchema?.type || 'string';
    const inputClassName = "bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] !px-0 py-2";

    const updateObjectProperty = (newValue: any) => {
      const currentObj = typeof formData[fieldName] === 'object' && !Array.isArray(formData[fieldName])
        ? { ...formData[fieldName] }
        : {};
      currentObj[propName] = newValue;
      handleChange(fieldName, currentObj);
    };

    switch (propType) {
      case 'number':
      case 'integer':
        return (
          <InputNumber
            value={value}
            onChange={(val) => updateObjectProperty(val)}
            placeholder={propSchema?.placeholder || propName}
            controls={false}
            className={inputClassName}
            style={{ boxShadow: 'none', width: '100%', paddingLeft: 0 }}
          />
        );
      case 'boolean':
        return (
          <Checkbox
            checked={value || false}
            onChange={(e) => updateObjectProperty(e.target.checked)}
            className="text-white"
          />
        );
      case 'array':
        // For nested arrays in objects, use JSON input for simplicity
        return (
          <Input
            value={Array.isArray(value) ? JSON.stringify(value) : value || ''}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                updateObjectProperty(parsed);
              } catch {
                updateObjectProperty(e.target.value);
              }
            }}
            placeholder={`["item1", "item2"]`}
            className={inputClassName}
            style={{ boxShadow: 'none' }}
          />
        );
      default: // string
        return (
          <Input
            value={value || ''}
            onChange={(e) => updateObjectProperty(e.target.value)}
            placeholder={propSchema?.placeholder || propName}
            className={inputClassName}
            style={{ boxShadow: 'none' }}
          />
        );
    }
  };

  // Parse string input to correct type based on schema
  const parseValueByType = (value: any, fieldType: string): any => {
    // If already correct type, return as-is
    if (fieldType === 'array' && Array.isArray(value)) return value;
    if (fieldType === 'object' && typeof value === 'object' && value !== null && !Array.isArray(value)) return value;
    if (fieldType === 'boolean' && typeof value === 'boolean') return value;
    if ((fieldType === 'number' || fieldType === 'integer') && typeof value === 'number') return value;

    // Parse string values
    if (typeof value === 'string') {
      const trimmed = value.trim();

      if (fieldType === 'array' && trimmed.startsWith('[')) {
        try {
          // Handle both single and double quotes
          const normalized = trimmed.replace(/'/g, '"');
          const parsed = JSON.parse(normalized);
          if (Array.isArray(parsed)) return parsed;
        } catch (e) {
          console.warn('Failed to parse array:', trimmed);
        }
      }

      if (fieldType === 'object' && trimmed.startsWith('{')) {
        try {
          const normalized = trimmed.replace(/'/g, '"');
          const parsed = JSON.parse(normalized);
          if (typeof parsed === 'object' && parsed !== null) return parsed;
        } catch (e) {
          console.warn('Failed to parse object:', trimmed);
        }
      }

      if (fieldType === 'boolean') {
        if (trimmed.toLowerCase() === 'true') return true;
        if (trimmed.toLowerCase() === 'false') return false;
      }

      if (fieldType === 'number' || fieldType === 'integer') {
        const num = Number(trimmed);
        if (!isNaN(num)) return fieldType === 'integer' ? Math.floor(num) : num;
      }
    }

    return value;
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
    console.log('=== FORM SUBMIT DEBUG ===');
    console.log('formData:', JSON.stringify(formData, null, 2));
    console.log('inputSchema:', JSON.stringify(inputSchema, null, 2));

    if (inputSchema && Object.keys(inputSchema).length > 0) {
      // Structured input - send variables directly (no content wrapper)
      const variables: Record<string, any> = {};
      Object.keys(formData).forEach(key => {
        const value = formData[key];
        const fieldType = inputSchema[key]?.type;

        console.log(`Processing field "${key}": value="${value}", type="${fieldType}"`);

        // Handle different types appropriately
        if (fieldType === 'array') {
          // Arrays are stored directly, include even if empty
          if (Array.isArray(value)) {
            variables[key] = value;
            console.log(`  -> Added as array:`, value);
          } else if (typeof value === 'string' && value.trim()) {
            // Try parsing if it's a non-empty string (fallback)
            const parsed = parseValueByType(value, fieldType);
            if (Array.isArray(parsed)) {
              variables[key] = parsed;
              console.log(`  -> Parsed and added as array:`, parsed);
            }
          }
        } else if (fieldType === 'object') {
          // Objects are stored directly (both defined properties and key-value pair UI)
          if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            // Only include if object has at least one property
            if (Object.keys(value).length > 0) {
              variables[key] = value;
              console.log(`  -> Added as object:`, value);
            } else {
              console.log(`  -> Skipped empty object`);
            }
          }
        } else if (fieldType === 'boolean') {
          // Include booleans (even false)
          if (typeof value === 'boolean') {
            variables[key] = value;
            console.log(`  -> Added as boolean:`, value);
          }
        } else if (fieldType === 'number' || fieldType === 'integer') {
          // Include numbers (even 0), but not null
          if (typeof value === 'number') {
            variables[key] = value;
            console.log(`  -> Added as number:`, value);
          } else if (value !== null && value !== '') {
            const parsed = parseValueByType(value, fieldType);
            if (typeof parsed === 'number') {
              variables[key] = parsed;
              console.log(`  -> Parsed and added as number:`, parsed);
            }
          }
        } else {
          // Strings and other types
          if (value !== undefined && value !== null && value !== '') {
            variables[key] = value;
            console.log(`  -> Added as string:`, value);
          }
        }
      });

      console.log('Final variables:', JSON.stringify(variables, null, 2));

      if (Object.keys(variables).length > 0) {
        // Send variables directly - NO content wrapper (matches Postman format)
        payload.prompt.variables = variables;
      }
    } else {
      // Unstructured input - send input field
      payload.input = formData['unstructuredSchema'] || '';
    }

    // Clear saved form data from sessionStorage on successful submit
    clearSavedFormData();

    console.log('=== FINAL PAYLOAD ===');
    console.log(JSON.stringify(payload, null, 2));

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
            controls={false}
            className={inputClassName}
            type='number'
            style={{ boxShadow: 'none', width: '100%', paddingLeft: 0 }}
          />
        );

      case 'boolean':
        return (
          <Checkbox
            checked={formData[fieldName] || false}
            onChange={(e) => handleChange(fieldName, e.target.checked)}
            className="text-white"
          >
            <Text_12_400_B3B3B3>{title || fieldName}</Text_12_400_B3B3B3>
          </Checkbox>
        );

      case 'array':
        const itemSchema = fieldSchema.items || { type: 'string' };
        const arrayValue: any[] = Array.isArray(formData[fieldName]) ? formData[fieldName] : [];

        return (
          <div className="space-y-2">
            {arrayValue.map((item, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className="flex-1">
                  {renderArrayItemInput(fieldName, index, item, itemSchema)}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const newArray = arrayValue.filter((_, i) => i !== index);
                    handleChange(fieldName, newArray);
                  }}
                  className="text-[#666666] hover:text-red-500 p-1 transition-colors"
                  title="Remove item"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => {
                const newItem = getDefaultForType(itemSchema);
                handleChange(fieldName, [...arrayValue, newItem]);
              }}
              className="text-[#965CDE] hover:text-[#a76ce8] text-sm flex items-center gap-1 transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M7 1V13M1 7H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Add item
            </button>
          </div>
        );

      case 'object':
        const properties = fieldSchema.properties || {};
        const objectValue = typeof formData[fieldName] === 'object' && !Array.isArray(formData[fieldName])
          ? formData[fieldName]
          : {};
        const propertyNames = Object.keys(properties);

        if (propertyNames.length === 0) {
          // No defined properties - use dynamic key-value pair UI
          // Store as object with user-defined keys
          const currentObj = typeof objectValue === 'object' && !Array.isArray(objectValue)
            ? objectValue
            : {};
          const entries = Object.entries(currentObj);

          const updateObjectKey = (oldKey: string, newKey: string) => {
            const newObj: Record<string, any> = {};
            Object.entries(currentObj).forEach(([k, v]) => {
              if (k === oldKey) {
                if (newKey.trim()) {
                  newObj[newKey] = v;
                }
              } else {
                newObj[k] = v;
              }
            });
            handleChange(fieldName, newObj);
          };

          const updateObjectValue = (key: string, value: string) => {
            handleChange(fieldName, { ...currentObj, [key]: value });
          };

          const removeEntry = (keyToRemove: string) => {
            const newObj: Record<string, any> = {};
            Object.entries(currentObj).forEach(([k, v]) => {
              if (k !== keyToRemove) {
                newObj[k] = v;
              }
            });
            handleChange(fieldName, newObj);
          };

          const addEntry = () => {
            // Find a unique key name
            let newKey = 'key';
            let counter = 1;
            while (currentObj.hasOwnProperty(newKey)) {
              newKey = `key${counter}`;
              counter++;
            }
            handleChange(fieldName, { ...currentObj, [newKey]: '' });
          };

          return (
            <div className="space-y-2">
              {entries.map(([key, value], index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    value={key}
                    onChange={(e) => updateObjectKey(key, e.target.value)}
                    placeholder="Key"
                    className={`${inputClassName} !w-[120px]`}
                    style={{ boxShadow: 'none' }}
                  />
                  <span className="text-[#666666]">:</span>
                  <Input
                    value={String(value || '')}
                    onChange={(e) => updateObjectValue(key, e.target.value)}
                    placeholder="Value"
                    className={`${inputClassName} flex-1`}
                    style={{ boxShadow: 'none' }}
                  />
                  <button
                    type="button"
                    onClick={() => removeEntry(key)}
                    className="text-[#666666] hover:text-red-500 p-1 transition-colors"
                    title="Remove field"
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={addEntry}
                className="text-[#965CDE] hover:text-[#a76ce8] text-sm flex items-center gap-1 transition-colors"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M7 1V13M1 7H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Add field
              </button>
            </div>
          );
        }

        return (
          <div className="space-y-3 pl-4 border-l-2 border-[#333333]">
            {propertyNames.map((propName) => (
              <div key={propName} className="space-y-1">
                <label className="text-[#B3B3B3] text-[0.75rem] block">
                  {properties[propName]?.title || propName}
                </label>
                {renderObjectPropertyInput(fieldName, propName, objectValue[propName], properties[propName])}
              </div>
            ))}
          </div>
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
        {/* Close Button */}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center text-[#666666] hover:text-white hover:bg-[#1F1F1F] rounded-full transition-colors"
            aria-label="Close form"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12 4L4 12M4 4L12 12"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
        <form onSubmit={handleSubmit} className="space-y-6 w-full">
          {/* Title */}
          <h2 className="text-white text-[1.25rem] font-[400] mb-6">
            {inputSchema?.title || 'Please enter the following details'}
          </h2>

          {/* Dynamic Fields - ordered by required array */}
          {inputSchema && fieldOrder.map((fieldName) => {
            const fieldSchema = inputSchema[fieldName];
            if (!fieldSchema || fieldName === 'title') return null; // Skip if field doesn't exist or is title

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
