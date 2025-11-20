import { usePrompts } from "src/hooks/usePrompts";
import { AgentSession } from "@/stores/useAgentStore";

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
