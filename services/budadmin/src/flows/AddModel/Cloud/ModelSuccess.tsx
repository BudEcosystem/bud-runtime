import React, { useEffect, useState } from "react";
import { Image } from "antd";

import { useDrawer } from "src/hooks/useDrawer";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";

import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import SelectedModeInfoCard from "src/flows/components/SelectedModeInfoCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { useDeployModel } from "src/stores/useDeployModel";
import { useModels } from "src/hooks/useModels";
import ComingSoon from "@/components/ui/comingSoon";
import { Text_12_400_B3B3B3, Text_24_600_EEEEEE } from "@/components/ui/text";
import { successToast } from "@/components/toast";

const ModelSuccessCard: React.FC = () => {
  const { openDrawer, openDrawerWithStep, closeDrawer } = useDrawer();
  const { getModel, selectedModel, deleteModel, refresh } = useModels();
  const { currentWorkflow, getWorkflow, startSecurityScan } = useDeployModel();
  const [showConfirm, setShowConfirm] = useState(false);
  React.useEffect(() => {
    getWorkflow();
  }, []);

  useEffect(() => {
    console.log("currentWorkflow add success", currentWorkflow);
    if (currentWorkflow?.workflow_steps?.model) {
      getModel(currentWorkflow.workflow_steps.model.id);
    }
    // if (
    //   currentWorkflow.workflow_steps.model?.modality &&
    //   !currentWorkflow.workflow_steps.add_model_modality?.some((modality) =>
    //     currentWorkflow.workflow_steps.model.modality.includes(modality)
    //   )
    // ) {
    //   setShowConfirm(true);
    // } else {
    //   setShowConfirm(false);
    // }
  }, [currentWorkflow]);

  return (
    <BudForm
      data={{}}
      // Hide evaluation button if model is not cloud model temporarily
      backText={
        selectedModel?.provider_type === "cloud_model" ? "Close" : "Skip"
      }
      onBack={() => {
        if (selectedModel?.provider_type === "cloud_model") {
          closeDrawer();
        } else {
          openDrawer("view-model");
        }
      }}
      // Hide evaluation button if model is not cloud model temporarily
      nextText={`${
        selectedModel?.provider_type === "cloud_model" ? "View Model" : "Scan"
      }`}
      // Hide evaluation button if model is not cloud model temporarily
      onNext={async () => {
        if (selectedModel?.provider_type === "cloud_model") {
          return openDrawer("view-model");
          // return openDrawer("run-model-evaluations");
          // return openDrawerWithStep("model-evaluations");
        } else {
          const result = await startSecurityScan();
          if (result) {
            openDrawerWithStep("security-scan-status");
          }
        }
      }}
      disableNext={showConfirm}
      disableBack={showConfirm}
    >
      <BudWraperBox center={!showConfirm ? true : false}>
        <BudDrawerLayout>
          <div className="flex flex-col	justify-start items-center p-[2.5rem]">
            <div className="align-center">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="info"
                width={140}
                height={129}
              />
            </div>
            <div className="max-w-[80%] mt-[1rem] mb-[3rem] flex flex-col items-center justify-center">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[90%]">
                Model Successfully added to the repository
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center">
                Your model has been successfully added to the system. You can
                now deploy the model to a cluster.
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>

        {showConfirm && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title="Mismatch between selected modality and uploaded model"
              description="You have selected the [LLM] modality, but you have uploaded an [embedding] model. Please confirm if you want to proceed with this upload despite the mismatch."
              confirmText={"Delete Model"}
              cancelText={"Proceed"}
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
      </BudWraperBox>
    </BudForm>
  );
};

export default ModelSuccessCard;
