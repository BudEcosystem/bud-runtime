'use client';

import React, { useState } from "react";
import { Dropdown, Tooltip, Switch } from "antd";
import {
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useAgentStore, AgentSession, AgentVariable } from "@/stores/useAgentStore";
import LoadModel from "./LoadModel";
import { Editor } from "../flowgramEditorDemo/editor";
import { SessionProvider } from "../flowgramEditorDemo/contexts/SessionContext";
import { SettingsSidebar, SettingsType } from "./schema/SettingsSidebar";
import { SettingsProvider, useSettings } from "./contexts/SettingsContext";
import { ToolsSidebar } from "./tools/ToolsSidebar";
import { ToolsProvider, useTools } from "./contexts/ToolsContext";
import { SettingsSidebar as ModelSettingsSidebar } from "./settings/SettingsSidebar";
import { ModelSettingsProvider, useModelSettings } from "./contexts/ModelSettingsContext";
import { PrimaryButton } from "../ui/bud/form/Buttons";
import { buildPromptSchemaFromSession } from "@/utils/promptSchemaBuilder";
import { successToast, errorToast } from "@/components/toast";
import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import { usePromptSchemaWorkflow } from "@/hooks/usePromptSchemaWorkflow";

interface AgentBoxProps {
  session: AgentSession;
  index: number;
  totalSessions: number;
  isActive: boolean;
  onActivate: () => void;
}

function AgentBoxInner({
  session,
  index,
  totalSessions,
  isActive,
  onActivate
}: AgentBoxProps) {
  // All hooks must be called before any conditional returns
  const {
    sessions,
    updateSession,
    deleteSession,
    duplicateSession,
    addInputVariable,
    addOutputVariable,
    updateVariable,
    deleteVariable,
    createSession,
    closeAgentDrawer,
    addDeletedPromptId,
  } = useAgentStore();

  // Ensure session has a promptId (migration for old sessions)
  React.useEffect(() => {
    if (session && !session.promptId) {
      const newPromptId = `prompt_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
      console.log("Session missing promptId, generating new one:", newPromptId);
      updateSession(session.id, { promptId: newPromptId });
    }
  }, [session, updateSession]);

  const [localSystemPrompt, setLocalSystemPrompt] = useState(session?.systemPrompt || "");
  // Ensure promptMessages is always a string, even if it comes as an array from corrupted data
  const [localPromptMessages, setLocalPromptMessages] = useState(
    typeof session?.promptMessages === 'string'
      ? session.promptMessages
      : ""
  );
  const [openLoadModel, setOpenLoadModel] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSavingOutput, setIsSavingOutput] = useState(false);
  const [isSavingSystemPrompt, setIsSavingSystemPrompt] = useState(false);
  const [isSavingPromptMessages, setIsSavingPromptMessages] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [structuredInputEnabled, setStructuredInputEnabled] = useState(false);
  const [structuredOutputEnabled, setStructuredOutputEnabled] = useState(false);
  const [streamEnabled, setStreamEnabled] = useState(session?.settings?.stream ?? false);

  // Custom hook to create workflow handlers with consistent behavior
  const useWorkflowHandler = (name: string, workflowId?: string) => {
    const resetStatusRef = React.useRef<(() => void) | null>(null);

    const workflow = usePromptSchemaWorkflow({
      workflowId,
      onCompleted: () => {
        console.log(`${name} workflow completed successfully`);
        setTimeout(() => resetStatusRef.current?.(), 3000);
      },
      onFailed: () => {
        console.error(`${name} workflow failed`);
        errorToast(`${name} workflow execution failed`);
        setTimeout(() => resetStatusRef.current?.(), 3000);
      },
    });

    resetStatusRef.current = workflow.resetStatus;

    return workflow;
  };

  // Initialize all workflow handlers
  const inputWorkflow = useWorkflowHandler('Input', session?.workflowId);
  const outputWorkflow = useWorkflowHandler('Output', session?.workflowId);
  const systemPromptWorkflow = useWorkflowHandler('System prompt', session?.workflowId);
  const promptMessagesWorkflow = useWorkflowHandler('Prompt messages', session?.workflowId);

  // Destructure for backward compatibility (resetStatus handled internally by useWorkflowHandler)
  const { status: workflowStatus, startWorkflow } = inputWorkflow;
  const { status: outputWorkflowStatus, startWorkflow: startOutputWorkflow } = outputWorkflow;
  const { status: systemPromptWorkflowStatus, startWorkflow: startSystemPromptWorkflow } = systemPromptWorkflow;
  const { status: promptMessagesWorkflowStatus, startWorkflow: startPromptMessagesWorkflow } = promptMessagesWorkflow;

  // Use the settings context (schema settings)
  const { isOpen: isSettingsOpen, activeSettings, openSettings, closeSettings, toggleSettings: toggleSettingsOriginal } = useSettings();

  // Use the tools context
  const { isOpen: isToolsOpen, toggleTools: toggleToolsOriginal, closeTools } = useTools();

  // Use the model settings context
  const { isOpen: isModelSettingsOpen, toggleModelSettings: toggleModelSettingsOriginal, closeModelSettings } = useModelSettings();

  // Determine which sidebar is open
  const isRightSidebarOpen = isSettingsOpen || isToolsOpen;

  // Custom toggle functions that close the other sidebar
  const toggleSettings = React.useCallback(() => {
    if (isToolsOpen) {
      closeTools();
    }
    if (isModelSettingsOpen) {
      closeModelSettings();
    }
    toggleSettingsOriginal();
  }, [isToolsOpen, closeTools, toggleSettingsOriginal]);

  const toggleTools = React.useCallback(() => {
    if (isSettingsOpen) {
      closeSettings();
    }
    if (isModelSettingsOpen) {
      closeModelSettings();
    }
    toggleToolsOriginal();
  }, [isSettingsOpen, closeSettings, toggleToolsOriginal]);

  const toggleModelSettings = () => {
    if (isSettingsOpen) {
      closeSettings();
    }
    if (isToolsOpen) {
      closeTools();
    }
    toggleModelSettingsOriginal();
  };

  // Update local state when session changes
  React.useEffect(() => {
    setLocalSystemPrompt(session?.systemPrompt || "");
    setLocalPromptMessages(
      typeof session?.promptMessages === 'string'
        ? session.promptMessages
        : ""
    );
    setStreamEnabled(session?.settings?.stream ?? false);
  }, [session?.systemPrompt, session?.promptMessages, session?.settings?.stream]);

  // Handle case where session is null early
  if (!session) {
    return (
      <div className="agent-box flex flex-col bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg min-w-[400px] h-full overflow-hidden justify-center items-center">
        <span className="text-[#808080]">No session data available</span>
      </div>
    );
  }

  const handleAddVariable = () => {
    if (session) addInputVariable(session.id);
  };

  const handleVariableChange = (variableId: string, field: keyof AgentVariable, value: string) => {
    if (session) updateVariable(session.id, variableId, { [field]: value });
  };

  const handleDeleteVariable = (variableId: string) => {
    if (session) deleteVariable(session.id, variableId);
  };

  const handleAddOutputVariable = () => {
    if (session) addOutputVariable(session.id);
  };

  const handleSystemPromptChange = (value: string) => {
    setLocalSystemPrompt(value);
    if (session) updateSession(session.id, { systemPrompt: value });
  };

  const handlePromptMessagesChange = (value: string) => {
    setLocalPromptMessages(value);
    if (session) updateSession(session.id, { promptMessages: value });
  };

  const handleStreamToggle = (checked: boolean) => {
    setStreamEnabled(checked);
    if (session) {
      updateSession(session.id, {
        settings: {
          ...session.settings,
          stream: checked
        }
      });
    }
  };

  // Handler for close button with cleanup API call
  const handleCloseSession = async () => {
    if (!session) return;

    // Call cleanup API if promptId exists
    if (session.promptId) {
      try {
        const payload = {
          prompts: [
            {
              prompt_id: session.promptId
            }
          ]
        };

        await AppRequest.Post(
          `${tempApiBaseUrl}/prompts/prompt-cleanup`,
          payload
        );

        // Record the deleted prompt ID in Zustand store
        addDeletedPromptId(session.id, session.promptId);

        // Note: No success toast as per requirements
      } catch (error: any) {
        console.error("Error calling prompt cleanup:", error);
        // Don't show error toast either, just log it
      }
    }

    // Delete the session
    deleteSession(session.id);
  };

  // Handler for when a flowgram card is clicked
  const handleNodeClick = (nodeType: string, nodeId: string, nodeData: any) => {
    // The openSettings function in context already handles the mapping
    openSettings(nodeType, nodeId, nodeData);
  };

  // Helper function to generate default model settings from session
  const getDefaultModelSettings = (session: AgentSession) => ({
    temperature: session.settings?.temperature ?? 0.7,
    max_tokens: session.settings?.maxTokens ?? 2000,
    top_p: session.settings?.topP ?? 0.9,
    frequency_penalty: 0,
    presence_penalty: 0,
    stop_sequences: [],
    seed: 0,
    timeout: 0,
    parallel_tool_calls: true,
    logprobs: true,
    logit_bias: {},
    extra_headers: {},
    max_completion_tokens: 0,
    stream_options: {},
    response_format: {},
    tool_choice: "string",
    chat_template: "string",
    chat_template_kwargs: {},
    mm_processor_kwargs: {},
    guided_json: {},
    guided_regex: "string",
    guided_choice: [],
    guided_grammar: "string",
    structural_tag: "string",
    guided_decoding_backend: "string",
    guided_whitespace_pattern: "string"
  });

  // Get current stream setting
  const getStreamSetting = () => streamEnabled;

  const handleSavePromptSchema = async () => {
    if (!session) {
      errorToast("No session data available");
      return;
    }

    // Check if deployment is selected
    if (!session.selectedDeployment?.name) {
      errorToast("Please select a deployment model first");
      return;
    }

    // Note: workflow_id is not required for input schema
    setIsSaving(true);

    try {
      // This function is for saving input schema, so type should always be "input"
      const type = "input";

      // Build the payload using the utility function with required parameters
      const payload = buildPromptSchemaFromSession(
        session,
        type,
        1,     // step_number
        0,     // workflow_total_steps (0 for single step save)
        true   // trigger_workflow
      );

      console.log("=== Input Schema Save Debug ===");
      console.log("Session promptId:", session.promptId);
      console.log("Built payload:", payload);
      console.log("Payload includes prompt_id:", payload.prompt_id);

      // Start workflow status tracking
      startWorkflow();

      // Make the API call
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-schema`,
        payload
      );

      if (response && response.data) {
        console.log("Input schema save response:", response.data);
        console.log("Using promptId from session:", session.promptId);

        // Extract workflow_id from response
        const workflowId = response.data.workflow_id;

        if (workflowId) {
          console.log("Got workflow_id from response:", workflowId);

          // Make GET call to /workflows/{workflow_id}
          try {
            const workflowResponse = await AppRequest.Get(
              `${tempApiBaseUrl}/workflows/${workflowId}`
            );
            console.log("Workflow status response:", workflowResponse.data);
          } catch (workflowError) {
            console.error("Error fetching workflow status:", workflowError);
          }
        }

        successToast("Input schema saved successfully");

        // promptId is already set when session was created, no need to extract from response
        // Just verify it exists
        if (!session.promptId) {
          console.error("WARNING: Session does not have a promptId!");
        }
      }
    } catch (error: any) {
      console.error("Error saving prompt schema:", error);
      // Handle validation errors better
      if (error?.response?.data?.detail && Array.isArray(error.response.data.detail)) {
        const firstError = error.response.data.detail[0];
        errorToast(firstError.msg || "Failed to save prompt schema");
      } else {
        errorToast(error?.response?.data?.detail || "Failed to save prompt schema");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveOutputSchema = async () => {
    if (!session) {
      errorToast("No session data available");
      return;
    }

    // Check if deployment is selected
    if (!session.selectedDeployment?.name) {
      errorToast("Please select a deployment model first");
      return;
    }

    // Note: workflow_id is not required for output schema
    setIsSavingOutput(true);

    try {
      // Build the payload with output type
      const payload = buildPromptSchemaFromSession(
        session,
        "output",  // Explicitly use output type
        1,         // step_number
        0,         // workflow_total_steps (0 for single step save)
        true       // trigger_workflow
      );

      // Start workflow status tracking for output
      startOutputWorkflow();

      // Make the API call
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-schema`,
        payload
      );

      if (response && response.data) {
        console.log("Output schema save response:", response.data);
        console.log("Using promptId from session:", session.promptId);

        // Extract workflow_id from response
        const workflowId = response.data.workflow_id;

        if (workflowId) {
          console.log("Got workflow_id from response:", workflowId);

          // Make GET call to /workflows/{workflow_id}
          try {
            const workflowResponse = await AppRequest.Get(
              `${tempApiBaseUrl}/workflows/${workflowId}`
            );
            console.log("Workflow status response:", workflowResponse.data);
          } catch (workflowError) {
            console.error("Error fetching workflow status:", workflowError);
          }
        }

        successToast("Output schema saved successfully");

        // promptId is already set when session was created, no need to extract from response
        // Just verify it exists
        if (!session.promptId) {
          console.error("WARNING: Session does not have a promptId!");
        }
      }
    } catch (error: any) {
      console.error("Error saving output schema:", error);
      // Handle validation errors better
      if (error?.response?.data?.detail && Array.isArray(error.response.data.detail)) {
        const firstError = error.response.data.detail[0];
        errorToast(firstError.msg || "Failed to save output schema");
      } else {
        errorToast(error?.response?.data?.detail || "Failed to save output schema");
      }
    } finally {
      setIsSavingOutput(false);
    }
  };

  const handleSaveSystemPrompt = async () => {
    if (!session) {
      errorToast("No session data available");
      return;
    }

    console.log("=== handleSaveSystemPrompt Debug ===");
    console.log("Full session object:", session);
    console.log("session.promptId:", session.promptId);
    console.log("session.workflowId:", session.workflowId);
    console.log("session.selectedDeployment:", session.selectedDeployment);

    // Check if deployment is selected
    if (!session.selectedDeployment?.name) {
      errorToast("Please select a deployment model first");
      return;
    }

    // Check if system prompt is not empty
    if (!session.systemPrompt || session.systemPrompt.trim() === "") {
      errorToast("System prompt cannot be empty");
      return;
    }

    // Check if prompt_id exists (it should be auto-generated)
    if (!session.promptId) {
      console.error("promptId is missing from session! This should not happen.");
      errorToast("Session error: promptId is missing. Please try creating a new agent.");
      return;
    }

    console.log("Using promptId:", session.promptId);

    setIsSavingSystemPrompt(true);

    try {
      // Build the payload for prompt-config endpoint
      const payload = {
        prompt_id: session.promptId,
        version: 1,
        set_default: false,
        deployment_name: session.selectedDeployment.model.name,
        // model_settings: getDefaultModelSettings(session),
        stream: getStreamSetting(),
        messages: [
          {
            role: "system",
            content: session.systemPrompt
          }
        ],
        llm_retry_limit: 0,
        enable_tools: true,
        allow_multiple_calls: true,
        system_prompt_role: "system"
      };

      console.log("=== System Prompt Save Payload ===");
      console.log("Stream enabled:", getStreamSetting());
      console.log("Full payload:", payload);

      // Start workflow status tracking
      startSystemPromptWorkflow();

      // Make the API call
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-config`,
        payload
      );

      if (response && response.data) {
        console.log("System prompt save response:", response.data);

        // Extract workflow_id from response
        const workflowId = response.data.workflow_id;

        if (workflowId) {
          console.log("Got workflow_id from response:", workflowId);

          // Make GET call to /workflows/{workflow_id}
          try {
            const workflowResponse = await AppRequest.Get(
              `${tempApiBaseUrl}/workflows/${workflowId}`
            );
            console.log("Workflow status response:", workflowResponse.data);
          } catch (workflowError) {
            console.error("Error fetching workflow status:", workflowError);
          }
        }

        successToast("System prompt saved successfully");
      }
    } catch (error: any) {
      console.error("Error saving system prompt:", error);
      // Handle validation errors better
      if (error?.response?.data?.detail && Array.isArray(error.response.data.detail)) {
        const firstError = error.response.data.detail[0];
        errorToast(firstError.msg || "Failed to save system prompt");
      } else {
        errorToast(error?.response?.data?.detail || "Failed to save system prompt");
      }
    } finally {
      setIsSavingSystemPrompt(false);
    }
  };

  const handleSavePromptMessages = async () => {
    if (!session) {
      errorToast("No session data available");
      return;
    }

    // Check if deployment is selected
    if (!session.selectedDeployment?.name) {
      errorToast("Please select a deployment model first");
      return;
    }

    // Check if prompt_id exists (it should be auto-generated)
    if (!session.promptId) {
      console.error("promptId is missing from session! This should not happen.");
      errorToast("Session error: promptId is missing. Please try creating a new agent.");
      return;
    }

    // Parse prompt messages
    let messages: any[] = [];
    try {
      if (session.promptMessages && typeof session.promptMessages === 'string') {
        messages = JSON.parse(session.promptMessages);
      }
    } catch (e) {
      errorToast("Invalid prompt messages format");
      return;
    }

    // Check if there are any messages
    if (!messages || messages.length === 0) {
      errorToast("Prompt messages cannot be empty");
      return;
    }

    setIsSavingPromptMessages(true);

    try {
      // Build the payload for prompt-config endpoint
      const payload = {
        prompt_id: session.promptId,
        version: 1,
        set_default: false,
        deployment_name: session.selectedDeployment.model.name,
        // model_settings: getDefaultModelSettings(session),
        stream: getStreamSetting(),
        messages: messages.map((msg: any) => ({
          role: msg.role,
          content: msg.content
        })),
        llm_retry_limit: 0,
        enable_tools: true,
        allow_multiple_calls: true,
        system_prompt_role: "system"
      };

      console.log("=== Prompt Messages Save Payload ===");
      console.log("Stream enabled:", getStreamSetting());
      console.log("Full payload:", payload);

      // Start workflow status tracking
      startPromptMessagesWorkflow();

      // Make the API call
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-config`,
        payload
      );

      if (response && response.data) {
        console.log("Prompt messages save response:", response.data);

        // Extract workflow_id from response
        const workflowId = response.data.workflow_id;

        if (workflowId) {
          console.log("Got workflow_id from response:", workflowId);

          // Make GET call to /workflows/{workflow_id}
          try {
            const workflowResponse = await AppRequest.Get(
              `${tempApiBaseUrl}/workflows/${workflowId}`
            );
            console.log("Workflow status response:", workflowResponse.data);
          } catch (workflowError) {
            console.error("Error fetching workflow status:", workflowError);
          }
        }

        successToast("Prompt messages saved successfully");
      }
    } catch (error: any) {
      console.error("Error saving prompt messages:", error);
      // Handle validation errors better
      if (error?.response?.data?.detail && Array.isArray(error.response.data.detail)) {
        const firstError = error.response.data.detail[0];
        errorToast(firstError.msg || "Failed to save prompt messages");
      } else {
        errorToast(error?.response?.data?.detail || "Failed to save prompt messages");
      }
    } finally {
      setIsSavingPromptMessages(false);
    }
  };

  const menuItems = [
    {
      key: 'stream',
      label: (
        <div
          className="flex items-center justify-between gap-3 py-1"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="text-[#B3B3B3]">Stream</span>
          <Switch
            size="small"
            checked={streamEnabled}
            onChange={handleStreamToggle}
          />
        </div>
      ),
      onClick: (e: any) => {
        e.domEvent?.stopPropagation();
      }
    },
    {
      key: 'delete',
      icon: '',
      // icon: <DeleteOutlined />,
      label: 'Close',
      danger: true,
      onClick: () => session && handleCloseSession()
    }
  ];

  return (
    <div
      className="agent-box flex flex-col bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg h-full overflow-hidden w-full relative"
      style={{ transition: "width 0.3s ease" }}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Overlay for inactive boxes - prevents scroll capture by flowgram */}
      {!isActive && (
        <div
          className="absolute inset-0 z-50 cursor-pointer bg-transparent"
          onClick={onActivate}
          title="Click to activate this agent box"
        />
      )}

      {/* Navigation Bar */}
      <div className="topBg text-white p-4 flex justify-between items-center h-[3.625rem] relative sticky top-0 z-10 bg-[#101010] border-b border-[#1F1F1F]">
        {/* Left Section - Session Info */}
        <div className="flex items-center gap-3 min-w-[100px]">
          <div className="h-[1.375rem] rounded-[0.375rem] min-w-[2rem] border-[1px] border-[#1F1F1F] flex justify-center items-center">
            <span className="text-[#808080] text-xs font-medium">V{index + 1}</span>
          </div>
          {isHovering && (
            <PrimaryButton onClick={closeAgentDrawer}
              classNames="h-[1.375rem] rounded-[0.375rem] min-w-[3rem] !border-[#479d5f] !bg-[#479d5f1a] hover:!bg-[#479d5f] hover:!border-[#965CDE] group"
              textClass="!text-[0.625rem] !font-[400] text-[#479d5f] group-hover:text-[#EEEEEE]"
            >
              Save
            </PrimaryButton>
          )}
        </div>

        {/* Center Section - Load Model */}
        <LoadModel
          sessionId={session?.id || ''}
          open={openLoadModel}
          setOpen={setOpenLoadModel}
        />

        {/* Right Section - Action Buttons */}
        <div className="flex items-center gap-1">
          {/* Model Settings Button - Works as toggle */}
          <button
            className={`w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center cursor-pointer transition-none ${isModelSettingsOpen ? 'bg-[#965CDE] bg-opacity-20' : ''
              }`}
            onClick={toggleModelSettings}
            style={{ transform: 'none' }}
          >
            <div
              className={`w-[1.125rem] h-[1.125rem] flex justify-center items-center cursor-pointer group transition-none ${isModelSettingsOpen ? 'text-[#965CDE]' : 'text-[#B3B3B3] hover:text-[#FFFFFF]'
                }`}
              style={{ transform: 'none' }}
            >
              <Tooltip title={isModelSettingsOpen ? "Close Settings" : "Model Settings"}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="none"
                  style={{ transform: 'none', display: 'block' }}
                >
                  <path
                    fill="currentColor"
                    d="M16.313 3.563H14.55a2.39 2.39 0 0 0-2.317-1.828 2.39 2.39 0 0 0-2.316 1.828h-8.23a.562.562 0 1 0 0 1.125h8.23a2.39 2.39 0 0 0 2.316 1.828 2.39 2.39 0 0 0 2.317-1.828h1.761a.562.562 0 1 0 0-1.125ZM12.235 5.39a1.267 1.267 0 0 1 0-2.531 1.267 1.267 0 0 1 0 2.53ZM16.313 8.437h-8.23A2.39 2.39 0 0 0 5.765 6.61a2.39 2.39 0 0 0-2.317 1.828H1.688a.562.562 0 1 0 0 1.125h1.76a2.39 2.39 0 0 0 2.318 1.829 2.39 2.39 0 0 0 2.316-1.829h8.23a.562.562 0 1 0 0-1.125ZM5.765 10.266a1.267 1.267 0 0 1 0-2.532 1.267 1.267 0 0 1 0 2.531ZM16.313 13.312H14.55a2.39 2.39 0 0 0-2.317-1.828 2.39 2.39 0 0 0-2.316 1.828h-8.23a.562.562 0 1 0 0 1.125h8.23a2.39 2.39 0 0 0 2.316 1.828 2.39 2.39 0 0 0 2.317-1.828h1.761a.562.562 0 1 0 0-1.125Zm-4.078 1.828a1.267 1.267 0 0 1 0-2.53 1.267 1.267 0 0 1 0 2.53Z"
                  />
                </svg>
              </Tooltip>
            </div>
          </button>

          {/* Tools Button - Works as toggle */}
          <button
            className={`w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center cursor-pointer transition-none ${isToolsOpen ? 'bg-[#965CDE] bg-opacity-20 text-[#B3B3B3] hover:text-[#FFFFFF]' : ''}`}
            onClick={toggleTools}
            style={{ transform: 'none' }}
          >
            <div
              className={`w-[1.125rem] h-[1.125rem] flex justify-center items-center cursor-pointer group transition-none ${isToolsOpen ? 'text-[#965CDE]' : 'text-[#B3B3B3] hover:text-[#FFFFFF]'}`}
              style={{ transform: 'none' }}
            >
              <Tooltip title={isToolsOpen ? "Close Tools" : "Tools"}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-[1rem] h-[1rem]"
                  viewBox="0 0 18 18"
                  fill="none"
                  style={{ transform: 'none', display: 'block' }}
                >
                  <g clip-path="url(#clip0_959_20489)">
                    <path d="M7.3045 8.31543L4.23567 11.3836C3.12453 11.0635 1.85415 11.3794 0.984831 12.2488C0.0076377 13.226 -0.27205 14.7053 0.279734 15.9723C0.379981 16.1998 0.684095 16.2444 0.844998 16.0549L2.55258 14.0373L3.78419 14.2159L3.96278 15.4475L1.94519 17.1551C1.75648 17.316 1.80113 17.6201 2.02774 17.7203C3.29558 18.2721 4.77394 17.9924 5.75131 17.0152C6.61983 16.1467 6.93575 14.8763 6.61646 13.7644L8.8977 11.4832L8.47566 10.9558L6.00313 13.4283C5.91299 13.5185 5.88182 13.6516 5.92226 13.7729C6.23732 14.7122 6.02503 15.7888 5.27528 16.5385C4.57607 17.2377 3.62161 17.4357 2.84912 17.2739L4.53984 15.841C4.62914 15.766 4.67295 15.6498 4.6561 15.5352L4.41684 13.868C4.40589 13.7948 4.37135 13.7282 4.32165 13.6785C4.27195 13.6288 4.2054 13.5934 4.13211 13.5833L2.46496 13.3441C2.34954 13.3272 2.23414 13.3719 2.15915 13.4603L0.726206 15.151C0.564462 14.3785 0.762431 13.4241 1.46165 12.7249C2.21141 11.9751 3.28802 11.7628 4.22725 12.0779C4.34856 12.1183 4.48083 12.0872 4.57181 11.997L7.77887 8.78996L7.3045 8.31543Z" fill="currentColor" />
                    <path d="M14.6192 0.000147943C13.7473 0.00267525 12.8897 0.343002 12.2487 0.984932C11.3801 1.85346 11.0642 3.12384 11.3843 4.23577L8.31616 7.30395L8.7896 7.77823L11.9975 4.57117C12.0877 4.48103 12.1188 4.34792 12.0784 4.22661C11.7633 3.28731 11.9756 2.21069 12.7254 1.461C13.4246 0.76179 14.379 0.563815 15.1515 0.725559L13.4608 2.1585C13.3715 2.23348 13.3277 2.34973 13.3446 2.46431L13.5838 4.13146C13.5948 4.20475 13.6293 4.2713 13.679 4.321C13.7287 4.37071 13.7953 4.40609 13.8685 4.4162L15.5357 4.65545C15.6511 4.6723 15.7665 4.62765 15.8415 4.5392L17.2744 2.84847C17.4362 3.62096 17.2382 4.57543 16.539 5.27464C15.7892 6.02439 14.7126 6.23667 13.7734 5.92161C13.6521 5.88118 13.5198 5.91235 13.4288 6.00248L11.0954 8.33591L11.4509 8.92982L13.7643 6.61644C14.8754 6.93657 16.1458 6.62066 17.0151 5.75129C17.9923 4.77409 18.272 3.29472 17.7202 2.02772C17.6208 1.80027 17.3167 1.75562 17.155 1.94432L15.4474 3.96192L14.2158 3.78417L14.038 2.55256L16.0556 0.844974C16.2443 0.68323 16.1997 0.379108 15.973 0.27887C15.5367 0.0893251 15.0757 -0.0015342 14.6192 0.000147943Z" fill="currentColor" />
                    <path d="M8.72412 11.0844L9.67942 12.9891C9.69543 13.0219 9.71733 13.0514 9.74261 13.0767L13.7929 17.127C13.7929 17.127 14.0785 17.4193 14.5207 17.5667C14.963 17.7141 15.5814 17.7192 16.1744 17.127L17.128 16.1733C17.7186 15.5828 17.7152 14.9628 17.5678 14.5197C17.4204 14.0774 17.128 13.7918 17.128 13.7918L13.0777 9.74239C13.0516 9.71628 13.0221 9.69521 12.9901 9.67921L11.0838 8.72559L10.783 9.32876L12.6406 10.2571L16.6522 14.2688C16.6522 14.2688 16.8376 14.4592 16.9285 14.7313C17.0195 15.0034 17.0195 15.3336 16.6539 15.6984L15.7003 16.652C15.3381 17.0142 15.0053 17.0168 14.7332 16.9266C14.4611 16.8356 14.2707 16.6503 14.2707 16.6503L10.2584 12.6395L9.33004 10.782L8.72412 11.0844Z" fill="currentColor" />
                    <path d="M7.83416 9.26462C7.3582 9.74058 7.37 10.2393 7.48792 10.5931C7.60586 10.9461 7.83584 11.1702 7.83584 11.1702C7.83584 11.1702 8.06161 11.4027 8.41458 11.5198C8.76755 11.6377 9.26542 11.647 9.74054 11.1719L11.1701 9.74228C11.6469 9.26548 11.6377 8.76761 11.5197 8.41464C11.4018 8.06167 11.1701 7.8359 11.1701 7.8359C11.1701 7.8359 10.9469 7.60508 10.5931 7.48798C10.2401 7.3692 9.74138 7.3574 9.26372 7.83506L7.83416 9.26462ZM8.31096 9.74142L9.74054 8.31184C9.97979 8.07258 10.198 8.06417 10.3808 8.12482C10.5636 8.18546 10.6942 8.31099 10.6942 8.31099C10.6942 8.31099 10.8214 8.44325 10.882 8.62605C10.9427 8.80885 10.9326 9.0262 10.6942 9.26459L9.26374 10.695C9.02701 10.9326 8.81051 10.9418 8.62772 10.8812C8.44491 10.8205 8.31266 10.6933 8.31266 10.6933C8.31266 10.6933 8.18714 10.5628 8.12649 10.38C8.06499 10.1972 8.0734 9.97897 8.31096 9.74142Z" fill="currentColor" />
                    <path d="M0.448939 1.40219C0.335214 1.51592 0.317521 1.69367 0.406819 1.82762L1.36212 3.2572C1.39413 3.30606 1.43878 3.34481 1.49017 3.37177L2.39408 3.82668L8.07367 9.50541L8.55047 9.02861L2.83206 3.31106C2.80595 3.28495 2.77646 3.26389 2.74445 3.24788L1.87002 2.80983L1.1211 1.68351L1.68384 1.12077L2.80762 1.87221L3.24566 2.74665C3.26167 2.7795 3.28357 2.80898 3.30885 2.83426L9.02726 8.5518L9.50321 8.07584L3.82449 2.39625L3.3721 1.49066C3.34598 1.43843 3.30639 1.39462 3.25753 1.36177L1.82795 0.407306C1.69401 0.318011 1.51626 0.335701 1.40252 0.449427L0.448939 1.40219Z" fill="currentColor" />
                    <path d="M11.8866 12.8401C11.7543 12.9715 11.7535 13.1847 11.8849 13.3169L14.0305 15.4626C14.1628 15.594 14.3759 15.5931 14.5073 15.4609C14.6379 15.3295 14.6379 15.1172 14.5073 14.9858L12.3617 12.8401C12.2303 12.7095 12.018 12.7095 11.8866 12.8401Z" fill="currentColor" />
                    <path d="M12.8397 11.886C12.7075 12.0174 12.7066 12.2306 12.838 12.3628L14.9837 14.5085C15.1159 14.6399 15.3291 14.639 15.4605 14.5068C15.591 14.3753 15.591 14.163 15.4605 14.0316L13.3148 11.886C13.1834 11.7554 12.9711 11.7554 12.8397 11.886Z" fill="currentColor" />
                  </g>
                  <defs>
                    <clipPath id="clip0_959_20489" fill="currentColor">
                      <rect width="18" height="18" fill="white" />
                    </clipPath>
                  </defs>
                </svg>
              </Tooltip>
            </div>
          </button>

          {/* New Chat Window Button */}
          <Tooltip title="New chat window" placement="bottom">
            <button
              onClick={createSession}
              className="w-7 h-7 rounded-md flex justify-center items-center cursor-pointer hover:bg-[#1A1A1A] transition-colors"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                fill="none"
                className="text-[#B3B3B3] hover:text-white"
              >
                <path
                  fill="currentColor"
                  d="M9 2a.757.757 0 0 0-.757.757v5.486H2.757a.757.757 0 0 0 0 1.514h5.486v5.486a.757.757 0 0 0 1.514 0V9.757h5.486a.757.757 0 0 0 0-1.514H9.757V2.757A.757.757 0 0 0 9 2Z"
                />
              </svg>
            </button>
          </Tooltip>

          {/* More Options Dropdown */}
          <Dropdown menu={{ items: menuItems }} trigger={["click"]} placement="bottomRight">
            <Tooltip title="Options" placement="bottom">
              <button className="w-7 h-7 rounded-md flex justify-center items-center cursor-pointer hover:bg-[#1A1A1A] transition-colors">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M10.453 3.226a1.226 1.226 0 1 1-2.453 0 1.226 1.226 0 0 1 2.453 0Zm0 5.45a1.226 1.226 0 1 1-2.453 0 1.226 1.226 0 0 1 2.453 0Zm-1.226 6.676a1.226 1.226 0 1 0 0-2.452 1.226 1.226 0 0 0 0 2.452Z"
                    clipRule="evenodd"
                    className="text-[#B3B3B3] hover:text-white"
                  />
                </svg>
              </button>
            </Tooltip>
          </Dropdown>

          {/* Close Button */}
          {totalSessions > 1 && (
            <Tooltip title="Close" placement="bottom">
              <button
                onClick={() => session && handleCloseSession()}
                className="w-7 h-7 rounded-md flex justify-center items-center cursor-pointer hover:bg-[#1A1A1A] transition-colors"
              >
                <CloseOutlined className="text-[#B3B3B3] hover:text-[#FF4444] text-base" />
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden relative">
        <div
          className={`flex w-full h-full transition-all duration-300 ease-in-out ${isRightSidebarOpen || isModelSettingsOpen ? 'pr-[15rem]' : 'pr-0'}`}
          onClick={() => {
            // Close sidebars when clicking outside but inside the agent box
            if (isRightSidebarOpen) {
              closeSettings();
              closeTools();
            }
            if (isModelSettingsOpen) {
              closeModelSettings();
            }
          }}
        >
          {/* Main content area */}
          <div className="flex-1 p-4 flow-editor-container">
            <SessionProvider
              session={session}
              onSavePromptSchema={handleSavePromptSchema}
              onSaveOutputSchema={handleSaveOutputSchema}
              onSaveSystemPrompt={handleSaveSystemPrompt}
              onSavePromptMessages={handleSavePromptMessages}
              isSaving={isSaving}
              isSavingOutput={isSavingOutput}
              isSavingSystemPrompt={isSavingSystemPrompt}
              isSavingPromptMessages={isSavingPromptMessages}
              workflowStatus={workflowStatus}
              outputWorkflowStatus={outputWorkflowStatus}
              systemPromptWorkflowStatus={systemPromptWorkflowStatus}
              promptMessagesWorkflowStatus={promptMessagesWorkflowStatus}
            >
              <Editor onNodeClick={handleNodeClick} />
            </SessionProvider>
          </div>

          {/* Settings Sidebar */}
          <SettingsSidebar
            session={session}
            isOpen={isSettingsOpen}
            activeSettings={activeSettings}
            onClose={closeSettings}
            onAddInputVariable={handleAddVariable}
            onAddOutputVariable={handleAddOutputVariable}
            onVariableChange={handleVariableChange}
            onDeleteVariable={handleDeleteVariable}
            onStructuredInputEnabledChange={setStructuredInputEnabled}
            onStructuredOutputEnabledChange={setStructuredOutputEnabled}
            onSystemPromptChange={handleSystemPromptChange}
            onPromptMessagesChange={handlePromptMessagesChange}
            localSystemPrompt={localSystemPrompt}
            localPromptMessages={localPromptMessages}
            onSavePromptSchema={handleSavePromptSchema}
            isSaving={isSaving}
            onSaveSystemPrompt={handleSaveSystemPrompt}
            isSavingSystemPrompt={isSavingSystemPrompt}
            onSavePromptMessages={handleSavePromptMessages}
            isSavingPromptMessages={isSavingPromptMessages}
            onSaveOutputSchema={handleSaveOutputSchema}
            isSavingOutput={isSavingOutput}
          />

          {/* Tools Sidebar */}
          <ToolsSidebar
            isOpen={isToolsOpen}
            onClose={closeTools}
            promptId={session?.promptId}
          />

          {/* Model Settings Sidebar */}
          <ModelSettingsSidebar
            isOpen={isModelSettingsOpen}
            onClose={closeModelSettings}
            session={session}
          />
        </div>
      </div>
    </div>
  );
}

// Wrapper component that provides the context
function AgentBox(props: AgentBoxProps) {
  return (
    <SettingsProvider>
      <ToolsProvider>
        <ModelSettingsProvider>
          <AgentBoxInner {...props} />
        </ModelSettingsProvider>
      </ToolsProvider>
    </SettingsProvider>
  );
}

export default AgentBox;
