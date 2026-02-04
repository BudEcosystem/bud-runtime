import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import { Spin } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_24_600_FFFFFF,
  Text_18_600_FFFFFF,
  Text_14_400_EEEEEE,
  Text_12_400_EEEEEE,
} from "@/components/ui/text";
import { formatDate } from "src/utils/formatDate";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { usePrompts, IPromptVersion } from "src/hooks/usePrompts";
import { useAgentStore } from "@/stores/useAgentStore";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import { errorToast } from "@/components/toast";
import { loadPromptForEditing } from "@/utils/promptHelpers";
import { parseSchemaToVariables } from "@/utils/schemaParser";

interface VersionsTabProps {
  agentData?: any;
}

const VersionsTab: React.FC<VersionsTabProps> = ({ agentData }) => {
  const router = useRouter();
  // Support both 'id' (from rewrite rule) and 'agentId' (from folder name)
  const { id, agentId, projectId, name } = router.query;
  const promptId = (id || agentId) as string;
  const promptName = useMemo(
    () => (typeof name === "string" ? name : undefined),
    [name]
  );

  // Use the prompts service for version management
  const {
    currentVersion,
    previousVersions,
    versionsLoading,
    getPromptVersions,
    getPromptById,
    getPromptConfig,
  } = usePrompts();

  // Use agent store for opening drawer in add version mode and edit version mode
  const {
    openAgentDrawer,
    loadPromptForAddVersion,
    loadPromptForEditVersion,
  } = useAgentStore();
  const [settingDefaultVersionId, setSettingDefaultVersionId] = useState<string | null>(null);

  // Fetch data when component mounts or promptId changes
  useEffect(() => {
    if (promptId) {
      getPromptVersions(promptId, projectId as string);
    }
  }, [promptId, projectId]);

  // Listen for version created event to refresh the list
  useEffect(() => {
    const handleVersionCreated = () => {
      if (promptId) {
        getPromptVersions(promptId, projectId as string);
      }
    };

    window.addEventListener('versionCreated', handleVersionCreated);

    return () => {
      window.removeEventListener('versionCreated', handleVersionCreated);
    };
  }, [promptId, projectId, getPromptVersions]);

  // Handle Add Version button click
  const handleAddVersion = async () => {
    if (!promptId) {
      errorToast("Invalid prompt ID");
      return;
    }

    try {
      // Fetch the prompt data
      const promptData = await getPromptById(promptId, projectId as string);

      if (!promptData) {
        errorToast("Failed to load prompt data");
        return;
      }

      // Prepare session data from prompt
      const sessionData = {
        name: promptData.name || promptData.prompt_name || "New Version",
        systemPrompt: "", // Will be configured in the drawer
        promptMessages: "",
        // Additional fields can be populated if available in promptData
      };

      // Load prompt data into agent store for add version mode
      loadPromptForAddVersion(promptId, sessionData);

      // Open the agent drawer
      openAgentDrawer();
    } catch (error) {
      console.error("Error loading prompt for add version:", error);
      errorToast("Failed to load prompt for adding version");
    }
  };

  // Handle Edit Version button click
  const handleEditVersion = async (versionData: IPromptVersion) => {
    if (!promptId) {
      errorToast("Invalid prompt ID");
      return;
    }

    try {
      // Fetch the prompt data
      const promptData = await getPromptById(promptId, projectId as string);

      if (!promptData) {
        errorToast("Failed to load prompt data");
        return;
      }

      const resolvedPromptName = promptName || promptData.name || promptData.prompt_name;

      // Load baseline session data from prompt
      const sessionData = await loadPromptForEditing(promptId, projectId as string);
      if (resolvedPromptName) {
        sessionData.name = resolvedPromptName;
      }

      const promptConfigKey = resolvedPromptName
        ? `${resolvedPromptName}:${versionData.version}`
        : undefined;

      // Fetch prompt config for the specific version
      const configResponse = resolvedPromptName
        ? await getPromptConfig(resolvedPromptName, versionData.version)
        : null;
      const configData = configResponse?.data;

      // Fetch endpoint/deployment details based on deployment name
      let selectedDeployment = null;
      const deploymentName =
        configData?.deployment_name ||
        versionData.endpoint_name;
      if (deploymentName) {
        try {
          const endpointResponse: any = await AppRequest.Get(
            `${tempApiBaseUrl}/playground/deployments`,
            {
              params: {
                name: deploymentName,
                project_id: projectId,
                page: 1,
                limit: 1,
                search: true
              }
            }
          );

          if (endpointResponse?.data?.endpoints && endpointResponse.data.endpoints.length > 0) {
            const endpoint = endpointResponse.data.endpoints[0];
            selectedDeployment = {
              id: endpoint.id,
              name: endpoint.model.name,
              model: {
                icon: endpoint.model.icon || endpoint.model.uri,
                provider: endpoint.model.provider
              }
            };
            console.log("Pre-selected deployment for edit version:", selectedDeployment);
          }
        } catch (endpointError) {
          console.warn("Failed to fetch endpoint details, user will need to select manually:", endpointError);
          // Don't show error - graceful degradation, user can select manually
        }
      }

      if (configData) {
        if (configData.system_prompt != null) {
          sessionData.systemPrompt = configData.system_prompt;
        }
        if (configData.messages && Array.isArray(configData.messages)) {
          sessionData.promptMessages = JSON.stringify(configData.messages);
        }
        if (configData.stream != null) {
          sessionData.settings = {
            ...sessionData.settings,
            stream: configData.stream,
          };
        }
        if (configData.llm_retry_limit != null) {
          sessionData.llm_retry_limit = configData.llm_retry_limit;
        }
        if (configData.allow_multiple_calls != null) {
          sessionData.allowMultipleCalls = configData.allow_multiple_calls;
        }
        if (configData.model_settings && typeof configData.model_settings === "object") {
          const settings = { ...sessionData.settings };
          if ("temperature" in configData.model_settings) {
            settings.temperature = Number(configData.model_settings.temperature);
          }
          if ("max_tokens" in configData.model_settings) {
            settings.maxTokens = Number(configData.model_settings.max_tokens);
          }
          if ("top_p" in configData.model_settings) {
            settings.topP = Number(configData.model_settings.top_p);
          }
          sessionData.settings = settings;
        }
        if (configData.input_schema) {
          const inputVars = parseSchemaToVariables(configData.input_schema, "Input", "input");
          if (inputVars.length > 0) {
            sessionData.inputVariables = inputVars;
          }
        }
        if (configData.output_schema) {
          const outputVars = parseSchemaToVariables(configData.output_schema, "Output", "output");
          if (outputVars.length > 0) {
            sessionData.outputVariables = outputVars;
          }
        }
        if (configData.deployment_name) {
          sessionData.selectedDeployment = {
            id: configData.deployment_id || "",
            name: configData.deployment_name,
            model: sessionData.selectedDeployment?.model || {},
          };
        }
      }

      if (promptConfigKey) {
        sessionData.promptConfigKey = promptConfigKey;
      }

      // Add selected deployment if found
      if (selectedDeployment) {
        sessionData.selectedDeployment = selectedDeployment;
      }

      // Prepare version metadata
      const versionMetadata = {
        versionId: versionData.id,
        versionNumber: versionData.version,
        isDefault: versionData.is_default_version
      };

      // Load prompt data into agent store for edit version mode
      loadPromptForEditVersion(promptId, versionMetadata, sessionData);

      // Open the agent drawer
      openAgentDrawer();
    } catch (error) {
      console.error("Error loading prompt for edit version:", error);
      errorToast("Failed to load prompt for editing version");
    }
  };

  const handleSetDefaultVersion = async (versionData: IPromptVersion) => {
    if (!promptId) {
      errorToast("Invalid prompt ID");
      return;
    }

    if (versionData.is_default_version) {
      return;
    }

    setSettingDefaultVersionId(versionData.id);

    try {
      let endpointId = versionData.endpoint_id;

      if (!endpointId && versionData.endpoint_name) {
        try {
          const endpointResponse: any = await AppRequest.Get(
            `${tempApiBaseUrl}/playground/deployments`,
            {
              params: {
                name: versionData.endpoint_name,
                project_id: projectId,
                page: 1,
                limit: 1,
                search: true
              }
            }
          );

          if (endpointResponse?.data?.endpoints && endpointResponse.data.endpoints.length > 0) {
            endpointId = endpointResponse.data.endpoints[0].id;
          }
        } catch (endpointError) {
          console.warn("Failed to fetch endpoint id for set default:", endpointError);
        }
      }

      if (!endpointId) {
        errorToast("Endpoint ID not found for this version");
        return;
      }

      const payload = {
        endpoint_id: endpointId,
        set_as_default: true,
      };

      await AppRequest.Patch(
        `${tempApiBaseUrl}/prompts/${promptId}/versions/${versionData.id}`,
        payload
      );
      await getPromptVersions(promptId, projectId as string);
    } catch (error) {
      console.error("Error setting default version:", error);
      errorToast("Failed to set default version");
    } finally {
      setSettingDefaultVersionId(null);
    }
  };

  const VersionCard = ({
    versionData
  }: {
    versionData: IPromptVersion;
  }) => (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-[.9rem] flex items-center justify-between mb-4">
      <div className="flex items-center gap-6">
        {/* Version Badge */}
        <div className="flex items-center justify-center w-[2.875rem] h-[2.875rem] bg-[#1A1A1A] border border-[#2F2F2F] rounded-lg">
          <Text_18_600_FFFFFF>V{versionData.version}</Text_18_600_FFFFFF>
        </div>

        {/* Version Info */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Text_14_400_EEEEEE>{versionData.endpoint_name}</Text_14_400_EEEEEE>
            {/* <Tags color="green" name="Public" /> */}
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11.0833 2.33333H10.5V1.16667C10.5 0.970833 10.3292 0.8 10.1333 0.8C9.9375 0.8 9.76667 0.970833 9.76667 1.16667V2.33333H4.23333V1.16667C4.23333 0.970833 4.0625 0.8 3.86667 0.8C3.67083 0.8 3.5 0.970833 3.5 1.16667V2.33333H2.91667C2.1625 2.33333 1.55 2.94583 1.55 3.7V11.6333C1.55 12.3875 2.1625 13 2.91667 13H11.0833C11.8375 13 12.45 12.3875 12.45 11.6333V3.7C12.45 2.94583 11.8375 2.33333 11.0833 2.33333ZM11.7167 11.6333C11.7167 11.9833 11.4333 12.2667 11.0833 12.2667H2.91667C2.56667 12.2667 2.28333 11.9833 2.28333 11.6333V5.83333H11.7167V11.6333Z" fill="#B3B3B3" />
              </svg>
              <Text_12_400_B3B3B3>Created Date</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-[#EEEEEE]">{formatDate(versionData.created_at)}</Text_12_400_EEEEEE>
            </div>
            <div className="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11.0833 2.33333H10.5V1.16667C10.5 0.970833 10.3292 0.8 10.1333 0.8C9.9375 0.8 9.76667 0.970833 9.76667 1.16667V2.33333H4.23333V1.16667C4.23333 0.970833 4.0625 0.8 3.86667 0.8C3.67083 0.8 3.5 0.970833 3.5 1.16667V2.33333H2.91667C2.1625 2.33333 1.55 2.94583 1.55 3.7V11.6333C1.55 12.3875 2.1625 13 2.91667 13H11.0833C11.8375 13 12.45 12.3875 12.45 11.6333V3.7C12.45 2.94583 11.8375 2.33333 11.0833 2.33333ZM11.7167 11.6333C11.7167 11.9833 11.4333 12.2667 11.0833 12.2667H2.91667C2.56667 12.2667 2.28333 11.9833 2.28333 11.6333V5.83333H11.7167V11.6333Z" fill="#B3B3B3" />
              </svg>
              <Text_12_400_B3B3B3>Last Updated</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-[#EEEEEE]">{formatDate(versionData.modified_at)}</Text_12_400_EEEEEE>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        {!versionData.is_default_version && (
          <PrimaryButton
            className="px-[.1rem]"
            onClick={() => handleSetDefaultVersion(versionData)}
            disabled={settingDefaultVersionId === versionData.id}
          >
            <div className="flex justify-center items-center gap-1">
              Set as Default
            </div>
          </PrimaryButton>
        )}
        <PrimaryButton
          className="px-[.1rem]"
          onClick={() => handleEditVersion(versionData)}
        >
          <div className="flex justify-center items-center gap-1">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M11.0871 1.04488C10.9933 0.951116 10.8661 0.898438 10.7335 0.898438C10.6009 0.898438 10.4737 0.951116 10.38 1.04488L3.44805 7.9768C3.35809 8.06675 3.28612 8.17305 3.23601 8.28998L1.87394 11.4681C1.7934 11.6561 1.83539 11.8741 1.97996 12.0187C2.12453 12.1632 2.34255 12.2052 2.53047 12.1247L5.70863 10.7626C5.82556 10.7125 5.93186 10.6405 6.02182 10.5506L12.9537 3.61866C13.149 3.4234 13.149 3.10681 12.9537 2.91155L11.0871 1.04488ZM4.15515 8.6839L10.7335 2.10554L11.8931 3.2651L5.31471 9.84346L3.91273 10.4443L3.5543 10.0859L4.15515 8.6839Z" fill="#EEEEEE" />
            </svg>
            Edit
          </div>
        </PrimaryButton>
        {/* {showDeploy && (
          <PrimaryButton
            className="px-[.1rem]"
            onClick={() => { }}
          >
            <div className="flex justify-center items-center gap-1">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12.25 6.41732C12.2503 6.34843 12.2232 6.28199 12.175 6.23232L7.51667 1.57398C7.46591 1.52323 7.39803 1.49414 7.32708 1.49414C7.25614 1.49414 7.18826 1.52323 7.1375 1.57398L6.4875 2.22398C6.38302 2.32846 6.38302 2.49904 6.4875 2.60357L9.93917 6.05482H2.04167C1.8938 6.05482 1.77083 6.17779 1.77083 6.32565V7.30398C1.77083 7.45185 1.8938 7.57482 2.04167 7.57482H9.93917L6.4875 11.0261C6.38302 11.1306 6.38302 11.3011 6.4875 11.4057L7.1375 12.0557C7.18826 12.1064 7.25614 12.1355 7.32708 12.1355C7.39803 12.1355 7.46591 12.1064 7.51667 12.0557L12.175 7.39732C12.2232 7.34765 12.2503 7.28121 12.25 7.21232V6.41732Z" fill="white" />
              </svg>
              Deploy
            </div>
          </PrimaryButton>
        )} */}
      </div>
    </div>
  );

  // Show loading state
  if (versionsLoading) {
    return (
      <div className="pb-8 pt-[2rem] flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="pb-8 pt-[2rem]">
      {/* Current Version Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <Text_24_600_FFFFFF>Current Version</Text_24_600_FFFFFF>
          <PrimaryButton
            className=" px-6"
            onClick={handleAddVersion}
          >
            + Version
          </PrimaryButton>
        </div>
        {currentVersion ? (
          <VersionCard versionData={currentVersion} />
        ) : (
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 text-center">
            <Text_14_600_EEEEEE>No current version available</Text_14_600_EEEEEE>
          </div>
        )}
      </div>

      {/* Previous Versions Section */}
      <div>
        <Text_24_600_FFFFFF className="block mb-6">Previous Version</Text_24_600_FFFFFF>
        {previousVersions.length > 0 ? (
          previousVersions.map((version) => (
            <VersionCard key={version.id} versionData={version} />
          ))
        ) : (
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 text-center">
            <Text_14_600_EEEEEE>No previous versions available</Text_14_600_EEEEEE>
          </div>
        )}
      </div>
    </div>
  );
};

export default VersionsTab;
