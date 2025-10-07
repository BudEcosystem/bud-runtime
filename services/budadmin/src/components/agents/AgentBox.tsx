'use client';

import React, { useState } from "react";
import { Dropdown, Tooltip } from "antd";
import {
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useAgentStore, AgentSession, AgentVariable } from "@/stores/useAgentStore";
import LoadModel from "./LoadModel";
import { Editor } from "../flowgramEditorDemo/editor";
import { SessionProvider } from "../flowgramEditorDemo/contexts/SessionContext";
import { SettingsSidebar, SettingsType } from "./settings/SettingsSidebar";
import { SettingsProvider, useSettings } from "./contexts/SettingsContext";
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
}

function AgentBoxInner({
  session,
  index,
  totalSessions
}: AgentBoxProps) {
  // All hooks must be called before any conditional returns
  const {
    updateSession,
    deleteSession,
    duplicateSession,
    addInputVariable,
    addOutputVariable,
    updateVariable,
    deleteVariable,
    createSession,
    closeAgentDrawer,
  } = useAgentStore();

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

  // Use the prompt schema workflow hook for socket handling (Input)
  const { status: workflowStatus, startWorkflow, resetStatus } = usePromptSchemaWorkflow({
    workflowId: session?.workflowId,
    onCompleted: () => {
      console.log('Input workflow completed successfully');
      // Auto-reset status after a delay
      setTimeout(() => {
        resetStatus();
      }, 3000);
    },
    onFailed: () => {
      console.error('Input workflow failed');
      errorToast('Input workflow execution failed');
      setTimeout(() => {
        resetStatus();
      }, 3000);
    },
  });

  // Use the prompt schema workflow hook for socket handling (Output)
  const { status: outputWorkflowStatus, startWorkflow: startOutputWorkflow, resetStatus: resetOutputStatus } = usePromptSchemaWorkflow({
    workflowId: session?.workflowId,
    onCompleted: () => {
      console.log('Output workflow completed successfully');
      // Auto-reset status after a delay
      setTimeout(() => {
        resetOutputStatus();
      }, 3000);
    },
    onFailed: () => {
      console.error('Output workflow failed');
      errorToast('Output workflow execution failed');
      setTimeout(() => {
        resetOutputStatus();
      }, 3000);
    },
  });

  // Use the prompt schema workflow hook for socket handling (System Prompt)
  const { status: systemPromptWorkflowStatus, startWorkflow: startSystemPromptWorkflow, resetStatus: resetSystemPromptStatus } = usePromptSchemaWorkflow({
    workflowId: session?.workflowId,
    onCompleted: () => {
      console.log('System prompt workflow completed successfully');
      // Auto-reset status after a delay
      setTimeout(() => {
        resetSystemPromptStatus();
      }, 3000);
    },
    onFailed: () => {
      console.error('System prompt workflow failed');
      errorToast('System prompt workflow execution failed');
      setTimeout(() => {
        resetSystemPromptStatus();
      }, 3000);
    },
  });

  // Use the prompt schema workflow hook for socket handling (Prompt Messages)
  const { status: promptMessagesWorkflowStatus, startWorkflow: startPromptMessagesWorkflow, resetStatus: resetPromptMessagesStatus } = usePromptSchemaWorkflow({
    workflowId: session?.workflowId,
    onCompleted: () => {
      console.log('Prompt messages workflow completed successfully');
      // Auto-reset status after a delay
      setTimeout(() => {
        resetPromptMessagesStatus();
      }, 3000);
    },
    onFailed: () => {
      console.error('Prompt messages workflow failed');
      errorToast('Prompt messages workflow execution failed');
      setTimeout(() => {
        resetPromptMessagesStatus();
      }, 3000);
    },
  });

  // Use the settings context
  const { isOpen: isRightSidebarOpen, activeSettings, openSettings, closeSettings, toggleSettings } = useSettings();

  // Update local state when session changes
  React.useEffect(() => {
    setLocalSystemPrompt(session?.systemPrompt || "");
    setLocalPromptMessages(
      typeof session?.promptMessages === 'string'
        ? session.promptMessages
        : ""
    );
  }, [session?.systemPrompt, session?.promptMessages]);

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

  // Handler for when a flowgram card is clicked
  const handleNodeClick = (nodeType: string, nodeId: string, nodeData: any) => {
    // The openSettings function in context already handles the mapping
    openSettings(nodeType, nodeId, nodeData);
  };

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

    // Check if workflow_id exists, if not we need to get it from add agent workflow
    if (!session.workflowId) {
      errorToast("Workflow ID is not available. Please create the agent workflow first.");
      return;
    }

    setIsSaving(true);

    try {
      // Determine the type based on whether we have output variables
      const type = session.outputVariables && session.outputVariables.length > 0 ? "output" : "input";

      // Build the payload using the utility function with required parameters
      const payload = buildPromptSchemaFromSession(
        session,
        type,
        1,     // step_number
        0,     // workflow_total_steps (0 for single step save)
        true   // trigger_workflow
      );

      // Start workflow status tracking
      startWorkflow();

      // Make the API call
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-schema`,
        payload
      );

      if (response && response.data) {
        successToast("Prompt schema saved successfully");

        // Optionally update the session with the response data if needed
        // For example, if the API returns an ID or updated workflow info
        if (response.data.id || response.data.schema_id || response.data.prompt_id) {
          updateSession(session.id, {
            workflowId: session.workflowId, // Keep existing workflow_id
            promptId: response.data.prompt_id || response.data.id // Store prompt_id if returned
          });
        }

        // Close the agent drawer after successful save
        // setTimeout(() => {
        //   closeAgentDrawer();
        // }, 500);
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

    // Check if workflow_id exists
    if (!session.workflowId) {
      errorToast("Workflow ID is not available. Please create the agent workflow first.");
      return;
    }

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
        successToast("Output schema saved successfully");

        // Update the session with the response data if needed
        if (response.data.id || response.data.schema_id || response.data.prompt_id) {
          updateSession(session.id, {
            workflowId: session.workflowId, // Keep existing workflow_id
            promptId: response.data.prompt_id || response.data.id // Store prompt_id if returned
          });
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

    // Check if deployment is selected
    if (!session.selectedDeployment?.name) {
      errorToast("Please select a deployment model first");
      return;
    }

    // Check if prompt_id exists
    if (!session.promptId) {
      errorToast("Prompt ID is not available. Please save input/output schema first.");
      return;
    }

    // Check if system prompt is not empty
    if (!session.systemPrompt || session.systemPrompt.trim() === "") {
      errorToast("System prompt cannot be empty");
      return;
    }

    setIsSavingSystemPrompt(true);

    try {
      // Build the payload for prompt-config endpoint
      const payload = {
        prompt_id: session.promptId,
        version: 1,
        set_default: false,
        deployment_name: session.selectedDeployment.name,
        model_settings: {
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
        },
        stream: true,
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

      // Start workflow status tracking
      startSystemPromptWorkflow();

      // Make the API call
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-config`,
        payload
      );

      if (response && response.data) {
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

    // Check if prompt_id exists
    if (!session.promptId) {
      errorToast("Prompt ID is not available. Please save input/output schema first.");
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
        deployment_name: session.selectedDeployment.name,
        model_settings: {
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
        },
        stream: true,
        messages: messages.map((msg: any) => ({
          role: msg.role,
          content: msg.content
        })),
        llm_retry_limit: 0,
        enable_tools: true,
        allow_multiple_calls: true,
        system_prompt_role: "system"
      };

      // Start workflow status tracking
      startPromptMessagesWorkflow();

      // Make the API call
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-config`,
        payload
      );

      if (response && response.data) {
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
      key: 'duplicate',
      icon: <CopyOutlined />,
      label: 'Duplicate',
      onClick: () => session && duplicateSession(session.id)
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: 'Delete',
      danger: true,
      onClick: () => session && deleteSession(session.id)
    }
  ];

  // All boxes are expanded by default
  const boxWidth = "600px";

  return (
    <div
      className="agent-box flex flex-col bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg min-w-[400px] h-full overflow-hidden"
      style={{ width: boxWidth, transition: "width 0.3s ease" }}
    >
      {/* Navigation Bar */}
      <div className="topBg text-white p-4 flex justify-between items-center h-[3.625rem] relative sticky top-0 z-10 bg-[#101010] border-b border-[#1F1F1F]">
        {/* Left Section - Session Info */}
        <div className="flex items-center gap-3">
          <span className="text-[#808080] text-xs font-medium">V{index + 1}</span>
        </div>

        {/* Center Section - Load Model */}
        <LoadModel
          sessionId={session?.id || ''}
          open={openLoadModel}
          setOpen={setOpenLoadModel}
        />

        {/* Right Section - Action Buttons */}
        <div className="flex items-center gap-1">
          {/* Settings Button - Works as toggle */}
          <button
            className={`w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center cursor-pointer ${
              isRightSidebarOpen ? 'bg-[#965CDE] bg-opacity-20' : ''
            }`}
            onClick={toggleSettings}
          >
            <div className={`w-[1.125rem] h-[1.125rem] flex justify-center items-center cursor-pointer group ${
              isRightSidebarOpen ? 'text-[#965CDE]' : 'text-[#B3B3B3] hover:text-[#FFFFFF]'
            }`}>
              <Tooltip title={isRightSidebarOpen ? "Close Settings" : "Settings"}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    d="M16.313 3.563H14.55a2.39 2.39 0 0 0-2.317-1.828 2.39 2.39 0 0 0-2.316 1.828h-8.23a.562.562 0 1 0 0 1.125h8.23a2.39 2.39 0 0 0 2.316 1.828 2.39 2.39 0 0 0 2.317-1.828h1.761a.562.562 0 1 0 0-1.125ZM12.235 5.39a1.267 1.267 0 0 1 0-2.531 1.267 1.267 0 0 1 0 2.53ZM16.313 8.437h-8.23A2.39 2.39 0 0 0 5.765 6.61a2.39 2.39 0 0 0-2.317 1.828H1.688a.562.562 0 1 0 0 1.125h1.76a2.39 2.39 0 0 0 2.318 1.829 2.39 2.39 0 0 0 2.316-1.829h8.23a.562.562 0 1 0 0-1.125ZM5.765 10.266a1.267 1.267 0 0 1 0-2.532 1.267 1.267 0 0 1 0 2.531ZM16.313 13.312H14.55a2.39 2.39 0 0 0-2.317-1.828 2.39 2.39 0 0 0-2.316 1.828h-8.23a.562.562 0 1 0 0 1.125h8.23a2.39 2.39 0 0 0 2.316 1.828 2.39 2.39 0 0 0 2.317-1.828h1.761a.562.562 0 1 0 0-1.125Zm-4.078 1.828a1.267 1.267 0 0 1 0-2.53 1.267 1.267 0 0 1 0 2.53Z"
                  />
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
                onClick={() => session && deleteSession(session.id)}
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
          className={`flex w-full h-full transition-all duration-300 ease-in-out ${isRightSidebarOpen ? 'pr-[15rem]' : 'pr-0'}`}
          onClick={() => {
            // Close settings when clicking outside the settings box but inside the agent box
            if (isRightSidebarOpen) {
              closeSettings();
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
            isOpen={isRightSidebarOpen}
            activeSettings={activeSettings}
            onClose={closeSettings}
            onAddInputVariable={handleAddVariable}
            onAddOutputVariable={handleAddOutputVariable}
            onVariableChange={handleVariableChange}
            onDeleteVariable={handleDeleteVariable}
            onSystemPromptChange={handleSystemPromptChange}
            onPromptMessagesChange={handlePromptMessagesChange}
            localSystemPrompt={localSystemPrompt}
            localPromptMessages={localPromptMessages}
            onSavePromptSchema={handleSavePromptSchema}
            isSaving={isSaving}
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
      <AgentBoxInner {...props} />
    </SettingsProvider>
  );
}

export default AgentBox;
