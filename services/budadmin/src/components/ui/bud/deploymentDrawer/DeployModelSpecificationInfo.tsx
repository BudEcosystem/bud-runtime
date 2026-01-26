import React, { useEffect } from "react";

import { Image } from "antd";
import {
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_12_400_EEEEEE,
} from "../../text";
import { getChromeColor } from "../dataEntry/TagsInputData";
import { useDeployModel } from "src/stores/useDeployModel";
import {
  SpecificationTableItem,
  SpecificationTableItemProps,
} from "src/flows/components/SpecificationTableItem";
import { getSpecValueWidthOddEven } from "@/lib/utils";
import { useProprietaryCredentials } from "src/stores/useProprietaryCredentials";
import { assetBaseUrl } from "@/components/environment";
import ModelTags from "src/flows/components/ModelTags";
import { Model } from "src/hooks/useModels";
import { IconOnlyRender } from "src/flows/components/BudIconRender";

interface Props {
  data: {
    name: string;
    info?: {
      template: string;
      chat: string;
      concurrentRequest: string;
      deploymentName: string;
      perSessionToken: string;
      contextLength: string;
      timeToFirstToken: string;
    };
    tags: {
      name: string;
      color: string;
    }[];
  };
}

export function ModelFlowInfoCard({
  selectedModel,
  deploymentSpecs,
  credentialsSelected,
  informationSpecs,
  showTemplate,
  deploymentTitle,
}: {
  selectedModel?: Model;
  deploymentSpecs?: SpecificationTableItemProps[];
  credentialsSelected?: SpecificationTableItemProps[];
  informationSpecs?: SpecificationTableItemProps[];
  showTemplate?: boolean;
  deploymentTitle?: string;
}) {
  const modelIcon = assetBaseUrl + (selectedModel?.icon || selectedModel?.icon);

  return (
    <div className="flex flex-col	justify-start items-center w-full">
      {selectedModel && (
        <div className="flex items-center justify-start w-full p-[1.35rem] pb-[1.5rem]">
          <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
            {/* {selectedModel?.icon && selectedModel?.icon?.length <= 2 ? (
          <div className="w-[1.75rem] h-[1.75rem] text-[1.5rem] flex items-center justify-center">
            {selectedModel?.icon}
          </div>
        ) : (
          <Image
            preview={false}
            src={(selectedModel?.icon || selectedModel?.icon) ? modelIcon : (selectedModel?.provider_type === 'url' ? '/images/drawer/url-2.png' : '/images/drawer/disk-2.png')}
            alt="info"
            style={{ width: '1.75rem' }}
          />
        )} */}
            <IconOnlyRender
              icon={selectedModel?.icon || selectedModel?.provider?.icon}
              imageSize={26}
              type={selectedModel?.provider_type}
            />
          </div>
          <div>
            <Text_14_400_EEEEEE className="mb-[0.65rem]">
              {selectedModel?.name}
            </Text_14_400_EEEEEE>
            <div className="flex items-center justify-start flex-wrap	gap-[.6rem]">
              <ModelTags model={selectedModel} hideEndPoints />
            </div>
          </div>
        </div>
      )}
      {credentialsSelected?.length > 0 ||
        (deploymentSpecs?.length > 0 && (
          <div className="w-full px-[1.4rem] py-[.6rem] pb-[1.2rem]  border-t border-[#1F1F1F]">
            {credentialsSelected?.length > 0 && (
              <>
                <div className="pt-[.8rem] flex justify-between items-center flex-wrap gap-y-[1.5rem]">
                  <div className="w-full">
                    <Text_14_600_EEEEEE>Credential Selected</Text_14_600_EEEEEE>
                  </div>
                  {credentialsSelected.map((item, index) => (
                    <SpecificationTableItem key={index} item={item} />
                  ))}
                </div>
                {showTemplate ? (
                  <div className="height-40"></div>
                ) : (
                  <div className="pb-[1.5rem] border-b border-[#1F1F1F]"></div>
                )}
              </>
            )}
            {showTemplate && deploymentSpecs.length > 0 && (
              <div className="pt-[.8rem] flex justify-between items-center flex-wrap gap-y-[1.5rem]">
                <div className="w-full">
                  <Text_14_600_EEEEEE>
                    {deploymentTitle || "Deployment Specification"}
                  </Text_14_600_EEEEEE>
                </div>
                {deploymentSpecs.map((item, index) => (
                  <SpecificationTableItem
                    key={index}
                    item={item}
                    valueWidth={220}
                    // valueWidth={getSpecValueWidthOddEven(
                    //   deploymentSpecs,
                    //   index
                    // )}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      {informationSpecs?.length > 0 && (
        <div className="w-full px-[1.4rem] py-[.6rem] pb-[1.2rem]  ">
          {informationSpecs?.map((item, index) => (
            <SpecificationTableItem
              key={index}
              item={item}
              valueWidth={getSpecValueWidthOddEven(informationSpecs, index)}
              benchmark={true}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function DeployModelSpecificationInfo({
  showTemplate = true,
  showDeployInfo = true,
  showCredentials = true,
}: {
  showTemplate?: boolean;
  showDeployInfo?: boolean;
  showCredentials?: boolean;
}) {
  const { providerInfo } = useProprietaryCredentials();
  const {
    selectedModel,
    selectedTemplate,
    deploymentSpecifcation,
    selectedCredentials,
    currentWorkflow,
  } = useDeployModel();
  const isCloudModelFlow =
    currentWorkflow?.workflow_steps?.model?.provider_type === "cloud_model";

  // Check if model is embedding/classify-only (no TTFT/throughput metrics apply)
  const hasChatEndpoint = selectedModel?.supported_endpoints?.chat?.enabled;
  const hasCompletionEndpoint = selectedModel?.supported_endpoints?.completion?.enabled;
  const hasEmbeddingEndpoint = selectedModel?.supported_endpoints?.embedding?.enabled;
  const hasClassifyEndpoint = selectedModel?.supported_endpoints?.classify?.enabled;
  const isEmbeddingOrClassifyOnly = (hasEmbeddingEndpoint || hasClassifyEndpoint) && !hasChatEndpoint && !hasCompletionEndpoint;

  const deploymentSpecs: SpecificationTableItemProps[] = [
    {
      name: "Template",
      value: selectedTemplate?.name,
      icon: "/images/drawer/template-1.png",
      // fullText: true,
      // full: true,
    },
    {
      name: "Deployment Name",
      value: showDeployInfo && deploymentSpecifcation.deployment_name,
      icon: "/images/drawer/tag.png",
      // full: true,
    },
    !isCloudModelFlow && !isEmbeddingOrClassifyOnly && {
      name: "Time To First Token",
      value:
        deploymentSpecifcation.ttft?.length > 0 &&
        deploymentSpecifcation.ttft?.join("-") + " ms",
      icon: "/images/drawer/tag.png",
    },
    {
      name: "Concurrent Request",
      value: showDeployInfo && deploymentSpecifcation.concurrent_requests,
      icon: "/images/drawer/current.png",
    },
    !isCloudModelFlow && !isEmbeddingOrClassifyOnly && {
      name: "Per-session Token/sec",
      value:
        deploymentSpecifcation.per_session_tokens_per_sec?.length > 0 &&
        deploymentSpecifcation.per_session_tokens_per_sec?.join("-"),
      icon: "/images/drawer/per.png",
    },
    {
      name: "Context Length",
      value: deploymentSpecifcation.avg_context_length,
      icon: "/images/drawer/context.png",
    },
    {
      name: "Sequence Length",
      value: deploymentSpecifcation.avg_sequence_length,
      icon: "/images/drawer/context.png",
    },
    !isCloudModelFlow && {
      name: "End to End Latency",
      value:
        deploymentSpecifcation.e2e_latency?.length > 0 &&
        deploymentSpecifcation.e2e_latency?.join("-") + " s",
      icon: "/images/drawer/tag.png",
    },
    !isEmbeddingOrClassifyOnly && {
      name: "Throughput per User",
      value:
        currentWorkflow?.workflow_steps?.endpoint_details?.result
          ?.target_throughput_per_user,
      icon: "/images/drawer/tag.png",
    },
    !isEmbeddingOrClassifyOnly && {
      name: "Target TTFT",
      value:
        currentWorkflow?.workflow_steps?.endpoint_details?.result?.target_ttft,
      icon: "/images/drawer/tag.png",
    },
    {
      name: "Target E2E Latency",
      value:
        currentWorkflow?.workflow_steps?.endpoint_details?.result
          ?.target_e2e_latency,
      icon: "/images/drawer/tag.png",
    },
  ]?.filter((item) => item?.value && showTemplate);

  const credentialsSelected = [
    {
      name: "API Key Name",
      value: selectedCredentials?.name,
      icon: "/images/drawer/template-1.png",
      full: true,
    },
    ...Object.keys(selectedCredentials?.other_provider_creds || {}).map(
      (key) => ({
        name: providerInfo?.find((item) => item.field === key)?.label || key,
        value: selectedCredentials?.other_provider_creds[key],
        icon: "/images/drawer/tag.png",
        secret: true,
        full: true,
      }),
    ),
  ]?.filter((item) => item.value && showCredentials);

  return (
    <ModelFlowInfoCard
      selectedModel={selectedModel}
      deploymentSpecs={deploymentSpecs}
      credentialsSelected={credentialsSelected}
      showTemplate={showTemplate}
    />
  );
}

export default DeployModelSpecificationInfo;
