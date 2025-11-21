import { usePrompts } from "src/hooks/usePrompts";
import { AgentSession, AgentVariable } from "@/stores/useAgentStore";

/**
 * Generate a unique variable ID
 */
const generateVariableId = (): string => {
  return `var_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
};

/**
 * Transform API variable format to AgentVariable format
 * @param variables - Variables from API response
 * @param type - Variable type ('input' or 'output')
 * @returns Transformed AgentVariable array
 */
function transformVariables(
  variables: any[] | undefined,
  type: "input" | "output"
): AgentVariable[] {
  if (!variables || !Array.isArray(variables) || variables.length === 0) {
    // Return default variable if no data
    return [
      {
        id: generateVariableId(),
        name: type === "input" ? "Input Variable 1" : "Output Variable 1",
        value: "",
        type: type,
        description: "",
        dataType: "string",
        defaultValue: "",
      },
    ];
  }

  return variables.map((variable, index) => ({
    id: generateVariableId(),
    name: variable.name || `${type === "input" ? "Input" : "Output"} Variable ${index + 1}`,
    value: variable.value || "",
    type: type,
    description: variable.description || "",
    dataType: variable.dataType || variable.data_type || "string",
    defaultValue: variable.defaultValue || variable.default_value || "",
    required: variable.required || false,
    validation: variable.validation || "",
  }));
}

/**
 * Load prompt data for editing
 * Fetches prompt details and transforms them into AgentSession format
 */
export async function loadPromptForEditing(
  promptId: string,
  projectId?: string
): Promise<Partial<AgentSession>> {
  try {
    const { getPromptById } = usePrompts.getState();
    const promptData = await getPromptById(promptId, projectId);

    // Transform prompt data into session format
    const sessionData: Partial<AgentSession> = {
      name: promptData?.name || `Agent ${new Date().toLocaleTimeString()}`,
      promptId: promptId,
      modelId: promptData?.model?.id,
      modelName: promptData?.model?.name || promptData?.model_name,
      systemPrompt: promptData?.system_prompt || "",
      promptMessages: promptData?.prompt_messages || "",
      inputVariables: transformVariables(promptData?.input_variables, "input"),
      outputVariables: transformVariables(promptData?.output_variables, "output"),
      selectedDeployment: promptData?.model
        ? {
            id: promptData.model.id,
            name: promptData.model.name,
            model: promptData.model,
          }
        : undefined,
      // Map any additional settings if they exist in the prompt data
      settings: {
        temperature: promptData?.settings?.temperature || 0.7,
        maxTokens: promptData?.settings?.max_tokens || 2000,
        topP: promptData?.settings?.top_p || 1.0,
        stream: promptData?.settings?.stream !== undefined ? promptData.settings.stream : true,
      },
      llm_retry_limit: promptData?.llm_retry_limit || 3,
    };

    return sessionData;
  } catch (error) {
    console.error("Error loading prompt for editing:", error);
    throw error;
  }
}
