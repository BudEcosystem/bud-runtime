"use client";

import { useState, useEffect } from 'react';
import { Input, InputNumber, Checkbox, Button, Slider } from 'antd';
import { Image } from "antd";
import { PrimaryButton } from '@/app/components/uiComponents/inputs';
import { getPromptConfig } from '@/app/lib/api';
import { useAuth } from '@/app/context/AuthContext';

interface PromptFormProps {
  promptIds?: string[];
  onSubmit: (data: any) => void;
  onClose?: () => void;
}

export default function PromptForm({ promptIds = [], onSubmit, onClose }: PromptFormProps) {
  const { apiKey, accessKey } = useAuth();
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [inputSchema, setInputSchema] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Fetch prompt configurations on mount
  useEffect(() => {
    const fetchPromptConfigs = async () => {
      if (promptIds.length === 0) {
        setLoading(false);
        return;
      }

      try {
        // Fetch config for the first promptId (you can extend this to handle multiple)
        const config = await getPromptConfig(promptIds[0], apiKey || '', accessKey || '');

        if (config && config.data) {
          setInputSchema(config.data.input_schema || {});

          // Initialize form data with default values
          const initialData: Record<string, any> = {};
          if (config.data.input_schema) {
            Object.keys(config.data.input_schema).forEach(key => {
              const field = config.data.input_schema[key];
              initialData[key] = field.default || '';
            });
          }
          setFormData(initialData);
        }
      } catch (error) {
        console.error('Error fetching prompt config:', error);
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const renderInput = (fieldName: string, fieldSchema: any) => {
    const { type, title, description, placeholder, minimum, maximum, enum: enumValues } = fieldSchema;

    const inputClassName = "bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] px-0 py-2";

    switch (type) {
      case 'string':
        return (
          <Input
            value={formData[fieldName] || ''}
            onChange={(e) => handleChange(fieldName, e.target.value)}
            placeholder={placeholder || `Enter ${title || fieldName}`}
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
            placeholder={placeholder || `Enter ${title || fieldName}`}
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
            placeholder={placeholder || `Enter ${title || fieldName}`}
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
                  {fieldSchema.title || fieldName}
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
                  First Name
                </label>
                <Input
                  value={formData['firstName'] || ''}
                  onChange={(e) => handleChange('firstName', e.target.value)}
                  placeholder="Enter first name"
                  className="bg-transparent !border-b !border-b-[#333333] !rounded-[0] !border-t-0 !border-l-0 !border-r-0 rounded-none text-white placeholder-[#666666] focus:border-[#965CDE] hover:border-[#965CDE] px-0 py-2"
                  style={{ boxShadow: 'none' }}
                />
              </div>
            </>
          )}

          {/* Next Button */}
          <div className="flex justify-end">
            <PrimaryButton classNames='!h-[1.75rem] !px-[.75rem] !mr-0' htmlType="submit">
              <div className='flex items-center'>
                <span>Next</span>
              </div>
            </PrimaryButton>
          </div>
        </form>
      </div>
    </div>
  );
}
