import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_FFFFFF,
  Text_12_400_EEEEEE,
  Text_12_400_FFFFFF,
  Text_14_400_EEEEEE,
  Text_8_300_FFFFFF,
} from "@/components/ui/text";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { ConfigProvider, Image } from "antd"; // Added Checkbox import
import Tags from "src/flows/components/DrawerTags";
import { Tabs } from "antd";
import type { TabsProps } from "antd";
import General from "./General/General";
import CustomDropDown from "../components/CustomDropDown";
import Evaluations from "./Evaluations/Evaluations";
import Advanced from "./Advanced/Advanced";
import { useModels } from "src/hooks/useModels";
import { assetBaseUrl } from "@/components/environment";
import BudStepAlert from "../components/BudStepAlert";
import { successToast } from "@/components/toast";
import ModelVerificationStatus from "../components/ModelVerificationStatus";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import ModelTags from "../components/ModelTags";
import { useDeployModel } from "src/stores/useDeployModel";
import { PermissionEnum, useUser } from "src/stores/useUser";
import IconRender from "../components/BudIconRender";
import { useMemo } from "react";

const TAB_KEYS = {
  GENERAL: "1",
  // EVALUATIONS: "2",
  ADVANCED: "2",
  ADAPTERS: "3",
};

export default function ViewModel() {
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const { currentWorkflow, setCurrentWorkflow } = useDeployModel();
  const {
    openDrawerWithStep,
    closeDrawer,
    previousStep,
    setPreviousStep,
    closeExpandedStep,
  } = useDrawer();
  const [filteredItems, setFilteredItems] = useState<TabsProps["items"]>([]);
  const [showConfirm, setShowConfirm] = useState(false);
  const [toAdapter, setToAdapter] = useState(false);
  const { selectedModel, deleteModel, refresh } = useModels();
  const { hasPermission } = useUser();
  // const imageUrl = (assetBaseUrl + selectedModel?.provider?.icon) || selectedModel?.icon
  const imageUrl =
    selectedModel?.source == "local"
      ? assetBaseUrl + selectedModel?.icon
      : assetBaseUrl + selectedModel?.provider?.icon;

  const onChange = (key: string) => {
    // if (key != '1') {
    //   closeExpandedStep();
    // }

    closeExpandedStep();
    if (key === TAB_KEYS.ADAPTERS) {
      setToAdapter(true);
    } else {
      setToAdapter(false);
    }
  };
  useEffect(() => {
    console.log("toAdapter", toAdapter);
  }, [toAdapter]);

  const items: TabsProps["items"] = useMemo(
    () => [
      {
        key: TAB_KEYS.GENERAL,
        label: "General",
        children: <General data={selectedModel} />,
      },
      // {
      //   key: TAB_KEYS.EVALUATIONS,
      //   label: "Evaluations",
      //   children: <Evaluations model={selectedModel} />,
      // },
      {
        key: TAB_KEYS.ADVANCED,
        label: "Advanced",
        children: <Advanced data={selectedModel} />,
      },
      {
        key: TAB_KEYS.ADAPTERS,
        label: "Adapters",
        children: (
          <General
            key={`general-tab-${toAdapter}`}
            data={selectedModel}
            goToAdapter={toAdapter}
          />
        ),
      },
    ],
    [toAdapter, selectedModel],
  );

  useEffect(() => {
    let filtered = items;

    // Hide certain tabs for cloud models
    if (selectedModel?.provider_type === "cloud_model") {
      filtered = filtered.filter(
        (item) => item.key !== "4" && item.key !== "5",
      );
    }

    setFilteredItems(filtered);
  }, [selectedModel, toAdapter]);

  const firstLineText = !selectedModel?.endpoints_count
    ? "You're about to delete the model"
    : "You're not allowed to delete this model";
  const secondLineText = !selectedModel?.endpoints_count
    ? "The model is not deployed on any projects. Are you sure you want to delete this model?"
    : "You will have to stop the deployment of this model from every project, before you can delete this model.";
  return (
    <BudForm
      data={{}}
      backText={previousStep ? "Back" : undefined}
      onBack={
        previousStep
          ? () => {
              if (previousStep) {
                setCurrentWorkflow(null);
                openDrawerWithStep(previousStep);
                setPreviousStep(null);
              }
            }
          : undefined
      }
    >
      <BudWraperBox>
        {showConfirm && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title={firstLineText}
              description={secondLineText}
              confirmText={
                !selectedModel?.endpoints_count
                  ? "Delete Model"
                  : "Okay, I understand"
              }
              cancelText={!selectedModel?.endpoints_count ? "Cancel" : null}
              confirmAction={async () => {
                if (!selectedModel?.endpoints_count) {
                  const result = await deleteModel(selectedModel?.id);
                  if (result) {
                    successToast("Model deleted successfully");
                    await refresh();
                    closeDrawer();
                  }
                  setShowConfirm(false);
                } else setShowConfirm(false);
              }}
              cancelAction={() => {
                setShowConfirm(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <BudDrawerLayout>
          <div className="flex items-start justify-between w-full p-[1.35rem]">
            <div className="flex items-start justify-start max-w-[72%]">
              {/* <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
                {selectedModel?.icon && selectedModel?.icon.length > 0 && selectedModel?.icon && selectedModel?.icon.length <= 2 ? (
                  <div className="w-[1.75rem] h-[1.75rem] text-[1.5rem] flex items-center justify-center">
                    {selectedModel?.icon}
                  </div>
                ) : (<>
                  <Image
                    preview={false}
                    src={imageUrl || (selectedModel?.provider_type === 'url' ? '/images/drawer/url-2.png' : '/images/drawer/disk-2.png')}
                    alt="info"
                    style={{ width: '1.75rem' }}
                  />
                </>
                )}
              </div> */}
              <div className="mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
                <IconRender
                  icon={selectedModel?.icon || selectedModel?.icon}
                  size={44}
                  imageSize={28}
                  type={selectedModel?.provider_type}
                  model={selectedModel}
                />
              </div>
              <div>
                <Text_14_400_EEEEEE className="mb-[0.65rem] leading-[140%]">
                  {selectedModel?.name}
                </Text_14_400_EEEEEE>
                <ModelTags model={selectedModel} maxTags={3} />
              </div>
            </div>
            <div className="flex justify-end items-start">
              {/* bud rank temp hidden */}
              {/* <div className="flex items-center justify-start rounded-[8px] border border-[transparent] bg-[#FFFFFF08] mr-[.65rem] mt-[.1rem] py-[.25rem] px-[.35rem]">
                <div className="e-[1.125] mt-[.2rem]">
                  <Image
                    preview={false}
                    src="/images/drawer/star.png"
                    alt="info"
                    style={{ width: '1.125rem', height: '1.25rem' }}
                  />
                </div>
                <div className="ml-[.4rem]">
                  <div className="flex items-baseline justify-start mt-[-.1rem]">
                    <Text_12_400_FFFFFF>68</Text_12_400_FFFFFF><Text_8_300_FFFFFF>/100</Text_8_300_FFFFFF>
                  </div>
                  <Text_10_400_FFFFFF>Bud Rank</Text_10_400_FFFFFF>
                </div>
              </div> */}
              <div>
                {hasPermission(PermissionEnum.ModelManage) && (
                  <CustomDropDown
                    isDisabled={isExpandedViewOpen}
                    buttonContent={
                      <div className="px-[.3rem] my-[0] py-[0.02rem]">
                        <Image
                          preview={false}
                          src="/images/drawer/threeDots.png"
                          alt="info"
                          style={{ width: "0.1125rem", height: ".6rem" }}
                        />
                      </div>
                    }
                    items={[
                      {
                        key: "1",
                        label: <Text_12_400_EEEEEE>Edit</Text_12_400_EEEEEE>,
                        onClick: () => openDrawerWithStep("edit-model"),
                      },
                      {
                        key: "2",
                        label: <Text_12_400_EEEEEE>Delete</Text_12_400_EEEEEE>,
                        onClick: () => setShowConfirm(true),
                      },
                    ]}
                  />
                )}
              </div>
            </div>
          </div>
          <div className="relative group px-[1.4rem]">
            <ModelVerificationStatus />
          </div>
          <div className="antTabWrap px-[1.4rem]">
            <ConfigProvider
              theme={{
                token: {
                  /* here is your global tokens */
                },
              }}
            >
              <Tabs
                defaultActiveKey={TAB_KEYS.GENERAL}
                items={filteredItems}
                onChange={onChange}
                className="generalTabs"
              />
            </ConfigProvider>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
