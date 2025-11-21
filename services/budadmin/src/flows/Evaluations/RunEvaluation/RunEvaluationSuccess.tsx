import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useEvaluations } from "src/hooks/useEvaluations";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Text_12_300_EEEEEE, Text_12_400_B3B3B3, Text_24_600_EEEEEE } from "@/components/ui/text";
import { CheckCircle2, ArrowRight } from "lucide-react";
import { useRouter } from "next/router";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { Image } from "antd";

export default function RunEvaluationSuccess() {
  const { closeDrawer, drawerProps } = useDrawer();
  const { currentWorkflow } = useEvaluations();
  const router = useRouter();
  const experimentId = currentWorkflow?.experiment_id || drawerProps?.experimentId;

  const handleViewExperiment = () => {
    closeDrawer();
    // router.push(`/home/evaluations/experiments`);
    if(experimentId)
      router.replace(`/home/evaluations/experiments/${experimentId}`);
  };

  const handleClose = () => {
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      onNext={handleViewExperiment}
      nextText="View Evaluation"
      backText="Close"
      onBack={handleClose}
    >
      <BudWraperBox>
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
            <div className="max-w-[90%] mt-[1rem] mb-[3rem] flex flex-col items-center justify-center">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[90%]">
                Evaluation Ran Successfully!
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center">
                You can now view the results and metrics for {currentWorkflow?.workflow_steps?.name} in the experiment details page.
              </Text_12_400_B3B3B3>
            </div>
            {/* <PrimaryButton
              onClick={handleViewExperiment}
            >
              <Text_12_300_EEEEEE className="ml-[.3rem]">
                View Experiment
              </Text_12_300_EEEEEE>
            </PrimaryButton> */}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
