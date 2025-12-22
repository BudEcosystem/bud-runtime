import { AgentVariable } from "@/stores/useAgentStore";

// Schema interface for prompt config
export interface PromptSchema {
  $defs?: {
    Input?: { properties?: Record<string, { type?: string; title?: string; default?: string }> };
    Output?: { properties?: Record<string, { type?: string; title?: string; default?: string }> };
  };
}

// Helper to generate variable ID
export const generateVarId = () => `var_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;

// Valid data types for schema variables
const validDataTypes = ['string', 'number', 'boolean', 'object', 'array'] as const;
type DataType = typeof validDataTypes[number];

/**
 * Helper to parse schema properties into AgentVariable array
 * Used to convert API response schema format to frontend variable format
 */
export const parseSchemaToVariables = (
  schema: PromptSchema | null | undefined,
  defKey: 'Input' | 'Output',
  type: 'input' | 'output'
): AgentVariable[] => {
  try {
    const properties = schema?.$defs?.[defKey]?.properties;
    if (!properties || typeof properties !== 'object') return [];

    return Object.entries(properties).map(([name, prop]) => ({
      id: generateVarId(),
      name: name,
      value: '',
      type: type,
      description: prop?.title || '',
      dataType: (validDataTypes.includes(prop?.type as DataType) ? prop?.type : 'string') as DataType,
      defaultValue: prop?.default || '',
    }));
  } catch (error) {
    console.error("Failed to parse schema to variables:", error);
    return [];
  }
};
