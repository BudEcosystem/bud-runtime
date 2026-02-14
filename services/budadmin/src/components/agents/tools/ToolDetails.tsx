'use client';

import React, { useState, useEffect } from 'react';
import { Spin } from 'antd';
import { Text_12_400_EEEEEE, Text_14_400_EEEEEE, Text_10_400_757575, Text_10_400_B3B3B3 } from '@/components/ui/text';
import { AppRequest } from 'src/pages/api/requests';
import { tempApiBaseUrl } from '@/components/environment';
import { errorToast } from '@/components/toast';
import ProjectTags from 'src/flows/components/ProjectTags';

interface ToolDetailsProps {
  toolId: string;
  toolName?: string;
  onBack: () => void;
}

interface PropertyDetail {
  type: string;
  description?: string;
}

interface ToolSchema {
  type: string;
  properties: Record<string, PropertyDetail>;
  required: string[];
  additionalProperties: boolean;
  $schema: string;
}

interface ToolDetailData {
  id: string;
  name: string;
  description?: string;
  schema?: ToolSchema;
  icon?: string;
}

export const ToolDetails: React.FC<ToolDetailsProps> = ({
  toolId,
  toolName,
  onBack,
}) => {
  const [toolData, setToolData] = useState<ToolDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchToolDetails = async () => {
      setIsLoading(true);
      try {
        const response = await AppRequest.Get(`${tempApiBaseUrl}/prompts/tools/${toolId}`);

        if (response.data && response.data.tool) {
          setToolData(response.data.tool);
        }
      } catch (error) {
        errorToast('Failed to fetch tool details');
      } finally {
        setIsLoading(false);
      }
    };

    fetchToolDetails();
  }, [toolId]);

  const getToolIcon = () => {
    if (toolData?.icon) {
      if (toolData.icon.startsWith('http://') || toolData.icon.startsWith('https://')) {
        return <img src={toolData.icon} alt={toolData.name || toolName} className="w-4 h-4 object-contain" />;
      }
      return toolData.icon;
    }
    const name = toolData?.name || toolName || '';
    return name.charAt(0).toUpperCase();
  };

  const formatParamName = (paramName: string) => {
    // Replace special characters with spaces and add space before capital letters for camelCase
    return paramName
      .replace(/([a-z])([A-Z])/g, '$1 $2') // Add space before capital letters in camelCase
      .replace(/[^a-zA-Z0-9\s]/g, ' ') // Replace any special characters (including _ and -) with spaces
      .replace(/\s+/g, ' ') // Replace multiple spaces with single space
      .trim(); // Remove leading/trailing spaces
  };

  if (isLoading) {
    return (
      <div className="flex flex-col h-full text-white items-center justify-center">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full text-white pb-[.5rem]">
      {/* Header */}
      <div className="px-[1.125rem] py-[1.875rem] relative">
        <button
          onClick={onBack}
          className="w-[1.125rem] h-[1.125rem] p-[.1rem] rounded-full flex items-center justify-center bg-[#18191B] hover:bg-[#1A1A1A] transition-colors"
          style={{ transform: 'none' }}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
      </div>

      {/* Tool Icon and Name */}
      <div className="px-[1.125rem] flex items-center gap-3 mb-6">
        <div className="w-[1.5rem] h-[1.5rem] rounded-lg bg-[#1F1F1F] flex items-center justify-center text-lg">
          {getToolIcon()}
        </div>
        <Text_14_400_EEEEEE>{toolData?.name || toolName}</Text_14_400_EEEEEE>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto px-[1.125rem]">
        {/* Description Section */}
        {toolData?.description && (
          <div className="mb-6">
            <Text_12_400_EEEEEE className="mb-1">Description</Text_12_400_EEEEEE>
            <Text_10_400_B3B3B3 className='leading-[140%]'>{toolData.description}</Text_10_400_B3B3B3>
          </div>
        )}

        {/* Parameters Section */}
        {toolData?.schema?.properties && Object.keys(toolData.schema.properties).length > 0 && (
          <div>
            <Text_12_400_EEEEEE className="mb-1">Parameters</Text_12_400_EEEEEE>
            <div className="space-y-2">
              {Object.entries(toolData.schema.properties).map(([paramName, paramDetails]) => {
                const isRequired = toolData.schema?.required?.includes(paramName);
                return (
                  <div
                    key={paramName}
                    className="bg-[#ffffff08] border border-[#1F1F1F] rounded-lg p-[.54rem]"
                  >
                    <div className="flex items-center justify-between">
                      <div className="w-[40%]">
                        <Text_12_400_EEEEEE>{formatParamName(paramName)}</Text_12_400_EEEEEE>
                      </div>
                      <div className="w-[25%]">
                        <Text_10_400_757575>{paramDetails.type}</Text_10_400_757575>
                      </div>
                      <div className="w-[35%]">
                        {isRequired ? (
                          <ProjectTags
                            name='Required'
                            color='#EC7575'
                          />
                        ) : (
                          <ProjectTags
                            name='Not required'
                            color='#d1b854'
                          />
                        )}
                      </div>
                    </div>
                    {/* {paramDetails.description && (
                      <Text_10_400_B3B3B3 className="mt-2">{paramDetails.description}</Text_10_400_B3B3B3>
                    )} */}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
