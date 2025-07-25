import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  PrimaryButton,
} from "@/components/ui/bud/form/Buttons";
import { Text_12_300_EEEEEE, Text_12_400_B3B3B3, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE, Text_14_600_EEEEEE } from "@/components/ui/text";
import React, { useContext } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import CustomPopover from "src/flows/components/customPopover";
import { useDeployModel } from "src/stores/useDeployModel";
import { assetBaseUrl } from "@/components/environment";
import dayjs from "dayjs";
import Leaderboards from "src/flows/components/LeaderboardsTable";
import { Model, useModels } from "src/hooks/useModels";
import ModelTags from "src/flows/components/ModelTags";




export default function ModelEvaluations({
  model
}: {
  model: Model
}) {
  const { currentWorkflow } = useDeployModel();
  const { getModel } = useModels();
  const { closeDrawer, openDrawerWithStep, openDrawer } = useDrawer()

  const imageUrl = currentWorkflow?.workflow_steps?.model?.icon ? assetBaseUrl + currentWorkflow?.workflow_steps?.model?.icon : '/images/drawer/zephyr.png';

  return (
    <BudForm
      data={{
      }}
      onBack={() => {
        openDrawerWithStep('cloud-model-success')
      }}
      onNext={() => {
        closeDrawer();
      }}
      nextText="Done"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex justify-start w-full p-[1.35rem] items-start">
            <div className="p-[.6rem] w-[2.75rem] h-[2.75rem] bg-[#1F1F1F] rounded-[6px] flex justify-center align-center mr-[1.05rem] shrink-0 grow-0">
              <Image
                preview={false}
                src={imageUrl}
                alt="info"
                style={{ width: '1.75rem' }}
              />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-start">
                <Text_14_400_EEEEEE className="mb-[0.65rem]">
                  {currentWorkflow?.workflow_steps?.model?.name}
                </Text_14_400_EEEEEE>
                <div className="w-[.75rem] h-[.75rem] cursor-pointer" onClick={async () => {
                  await getModel(currentWorkflow?.workflow_steps?.model?.id);
                  openDrawer("edit-model");
                }}>
                  <Image
                    preview={false}
                    src="/images/drawer/edit.png"
                    alt="info"
                    style={{ width: '.75rem', height: '.75rem' }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-start flex-wrap	gap-[.6rem]">
                <ModelTags model={currentWorkflow?.workflow_steps?.model} hideLink hideEndPoints />
              </div>
            </div>
          </div>
          <div className="px-[1.4rem] pt-[.25rem] border-b-[1px] border-b-[#1F1F1F] pb-[.9rem]">
            <div className="flex justify-start items-center">
              <div className="flex justify-start items-center mr-[3.3rem]">
                <div className="w-[.75rem] h-[.75rem] flex justify-center align-center mr-[.5rem] shrink-0 grow-0">
                  <Image
                    preview={false}
                    src="/images/drawer/calander.png"
                    alt="info"
                    style={{ width: '.75rem' }}
                  />
                </div>
                <Text_12_400_B3B3B3>Updated on</Text_12_400_B3B3B3>
              </div>
              <Text_12_400_EEEEEE>
                {dayjs().format("DD MMM, YYYY")}
              </Text_12_400_EEEEEE>
            </div>
            <Text_12_400_B3B3B3 className="mt-[1.2rem] leading-[1.1rem]">
              {currentWorkflow?.workflow_steps?.model?.description}
            </Text_12_400_B3B3B3>
          </div>
          <div className="px-[1.4rem] pt-[1.2rem]">
            <Leaderboards runEval={true}
              model={model}
            />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
