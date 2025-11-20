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
  console.log(`=== transformVariables for ${type} ===`);
  console.log("Raw variables received:", variables);
  console.log("Is array?", Array.isArray(variables));
  console.log("Length:", variables?.length);

  if (!variables || !Array.isArray(variables) || variables.length === 0) {
    console.log(`⚠️ No valid ${type} variables array - returning default variable`);
    console.log("Reason: variables is", !variables ? "null/undefined" : !Array.isArray(variables) ? "not an array" : "empty array");
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

  console.log(`✓ Transforming ${variables.length} ${type} variable(s)`);
  const transformed = variables.map((variable, index) => {
    const transformedVar = {
      id: generateVariableId(),
      name: variable.name || `${type === "input" ? "Input" : "Output"} Variable ${index + 1}`,
      value: variable.value || "",
      type: type,
      description: variable.description || "",
      dataType: variable.dataType || variable.data_type || "string",
      defaultValue: variable.defaultValue || variable.default_value || "",
      required: variable.required || false,
      validation: variable.validation || "",
    };
    console.log(`Variable ${index}:`, {
      originalName: variable.name,
      transformedName: transformedVar.name,
      usedDefault: !variable.name
    });
    return transformedVar;
  });

  console.log("=== End transformVariables ===");
  return transformed;
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

    console.log("=== loadPromptForEditing Debug ===");
    console.log("Prompt ID:", promptId);
    console.log("Raw prompt data:", promptData);
    console.log("Input variables from API:", promptData?.input_variables);
    console.log("Output variables from API:", promptData?.output_variables);

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

    console.log("Transformed input variables:", sessionData.inputVariables);
    console.log("Transformed output variables:", sessionData.outputVariables);
    console.log("=== End loadPromptForEditing Debug ===");

    return sessionData;
  } catch (error) {
    console.error("Error loading prompt for editing:", error);
    throw error;
  }
}
