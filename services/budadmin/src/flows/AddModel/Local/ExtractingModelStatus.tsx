import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_14_400_EEEEEE } from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Flex, Image, Tag } from "antd"; // Added Checkbox import
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { LinkOutlined } from "@ant-design/icons";
import { useDeployModel } from "src/stores/useDeployModel";
import { assetBaseUrl } from "@/components/environment";
import { useSocket } from "@novu/notification-center";
import { calculateEta } from "src/flows/utils/calculateETA";
import BudStepAlert from "src/flows/components/BudStepAlert";
import TagsList, { TagListeItem } from "src/flows/components/TagsList";
import CommonStatus from "src/flows/components/CommonStatus";
import Tags from "src/flows/components/DrawerTags";
import { IconOnlyRender } from "src/flows/components/BudIconRender";

function ModelTag({
  tag,
}: {
  tag: {
    name: string;
    color: string;
    image?: boolean;
  };
}) {
  return (
    <Tag
      className={`border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem]`}
      style={{
        backgroundColor: getChromeColor(tag.color),
      }}
    >
      {tag.image && (
        <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
          <LinkOutlined
            style={{
              color: tag.color || "#B3B3B3",
            }}
          />
        </div>
      )}
      <div
        className={`text-[0.625rem] font-[400] leading-[100%]`}
        style={{
          color: tag.color || "#B3B3B3",
        }}
      >
        {tag.name}
      </div>
    </Tag>
  );
}

export default function ExtractingModel() {
  const [showAlert, setShowAlert] = React.useState(false);
  const { closeDrawer, openDrawerWithStep, openDrawer } = useDrawer();
  const { currentWorkflow, getWorkflow, providerType } = useDeployModel();
  const [isFailed, setIsFailed] = React.useState(false);

  const providerName =
    currentWorkflow?.workflow_steps?.name || providerType?.name;
  const providerIcon =
    currentWorkflow?.workflow_steps?.icon || providerType?.icon;

  const tags: TagListeItem[] = [
    {
      icon: providerIcon,
      name: providerName,
      color: "#965CDE",
      background: "#8F55D62B",
      drop: true,
      title: `Provider: ${providerName}`,
      url: `https://huggingface.co/${currentWorkflow?.workflow_steps?.uri}`,
    },
  ]?.filter((tag) => tag.name?.toLowerCase() === "hugging face");

  return (
    <BudForm
      data={{}}
      onBack={() => {
        if (isFailed) {
          closeDrawer();
        } else {
          setShowAlert(true);
        }
      }}
      backText={isFailed ? "Close" : "Cancel"}
    >
      <BudWraperBox center={false}>
        {showAlert && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title="You're about to stop the extraction process"
              description="If the extraction process is stopped, the model will not be added to the model repository. "
              cancelText="Continue Extraction"
              confirmText="Cancel Anyways"
              confirmAction={() => {
                // TODO: Add cancel action
                closeDrawer();
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        {isFailed && (
          <BudDrawerLayout>
            <BudStepAlert
              type="failed"
              title="Extraction Failed!"
              description="We are not able to extract the model details. Hence we won't be able to run the inference of this model."
              confirmText="Add Another Model"
              confirmAction={() => {
                // TODO: Add cancel action
                openDrawer("add-model");
              }}
            />
          </BudDrawerLayout>
        )}
        <BudDrawerLayout>
          <div
            className="flex items-start justify-start w-full p-[1.35rem]"
            onClick={() => {
              getWorkflow();
            }}
          >
            <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0">
              {
                // currentWorkflow?.workflow_steps.icon?.length > 2 ? (
                //   <Flex
                //     align={"center"}
                //     justify={"center"}
                //     className="bg-[#1F1F1F] w-[2.40125rem] h-[2.40125rem] rounded"
                //   >
                //     <div className="text-[1.5625rem]">
                //       {currentWorkflow?.workflow_steps.icon}
                //     </div>
                //   </Flex>
                // ) : (
                //   <IconOnlyRender
                //     icon={currentWorkflow?.workflow_steps.icon}
                //     imageSize={26}
                //     type={currentWorkflow.workflow_steps.provider_type}
                //   />
                // )
                <IconOnlyRender
                  icon={
                    currentWorkflow?.workflow_steps?.icon ||
                    currentWorkflow?.workflow_steps?.provider?.icon
                  }
                  imageSize={26}
                  type={currentWorkflow?.workflow_steps?.provider_type}
                />
                // <Image
                //   preview={false}
                //   src={currentWorkflow?.workflow_steps?.icon ? assetBaseUrl + currentWorkflow?.workflow_steps?.icon
                //     : providerType?.icon
                //   }
                //   alt="info"
                //   style={{ width: '1.75rem' }}
                // />
              }
            </div>
            <div className="w-[calc(100%-4rem)]">
              <Text_14_400_EEEEEE className="mb-[0.3rem] truncate leading">
                {currentWorkflow?.workflow_steps.name}
              </Text_14_400_EEEEEE>
              <div className="flex items-center justify-start flex-wrap gap-[.4rem]">
                <TagsList data={tags} />
                <TagsList data={currentWorkflow?.workflow_steps?.tags || []} />
                {currentWorkflow?.workflow_steps?.provider?.name ? (
                  <Tags
                    name={currentWorkflow?.workflow_steps?.provider?.name}
                    color="#D1B854"
                  />
                ) : (
                  <Tags name={providerType?.name} color="#D1B854" />
                )}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="model_extraction_events"
          onCompleted={() => {
            return openDrawerWithStep("local-model-success");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          success_payload_type="perform_model_extraction"
          title={"Adding model to the repository"}
          description={
            <>
              In process of verification, downloading and extracting the model
            </>
          }
        />
      </BudWraperBox>
    </BudForm>
  );
}
