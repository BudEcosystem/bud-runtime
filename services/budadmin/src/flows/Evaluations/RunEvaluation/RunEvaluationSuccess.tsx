import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useEvaluations } from "src/hooks/useEvaluations";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Text_14_600_EEEEEE, Text_12_400_757575 } from "@/components/ui/text";
import { CheckCircle2, ArrowRight } from "lucide-react";
import { useRouter } from "next/router";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

export default function RunEvaluationSuccess() {
  const { closeDrawer, drawerProps } = useDrawer();
  const { currentWorkflow } = useEvaluations();
  const router = useRouter();
  const experimentId = currentWorkflow?.experiment_id || drawerProps?.experimentId;

  const handleViewExperiment = () => {
    closeDrawer();
    router.push(`/home/evaluations/experiments/${experimentId}`);
  };

  const handleClose = () => {
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      onNext={handleViewExperiment}
      nextText="View Experiment"
      backText="Close"
      onBack={handleClose}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Evaluation Complete"
            description="Your evaluation has been successfully completed"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <div className="flex flex-col items-center justify-center py-12 px-6">
            {/* Success Icon */}
            <div className="mb-6">
              <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center">
                <CheckCircle2 className="w-12 h-12 text-green-500" />
              </div>
            </div>

            {/* Success Message */}
            <div className="text-center space-y-3 mb-8">
              <Text_14_600_EEEEEE className="text-xl">
                Evaluation Completed Successfully!
              </Text_14_600_EEEEEE>
              <Text_12_400_757575 className="max-w-md mx-auto">
                The evaluation workflow for experiment {experimentId} has been completed.
                You can now view the results and metrics in the experiment details page.
              </Text_12_400_757575>
            </div>

            {/* Summary Info */}
            <div className="w-full max-w-md space-y-3 mb-8">
              <div className="flex justify-between items-center py-2 border-b border-[#1F1F1F]">
                <Text_12_400_757575>Experiment ID</Text_12_400_757575>
                <Text_12_400_757575 className="text-[#EEEEEE]">{experimentId}</Text_12_400_757575>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-[#1F1F1F]">
                <Text_12_400_757575>Workflow ID</Text_12_400_757575>
                <Text_12_400_757575 className="text-[#EEEEEE]">{currentWorkflow?.workflow_id}</Text_12_400_757575>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-[#1F1F1F]">
                <Text_12_400_757575>Status</Text_12_400_757575>
                <Text_12_400_757575 className="text-green-500">Completed</Text_12_400_757575>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col w-full max-w-md space-y-3">
              <PrimaryButton
                onClick={handleViewExperiment}
                classNames="w-full justify-center shadow-purple-glow"
                textClass="text-[0.8125rem]"
              >
                View Experiment Results
                <ArrowRight className="ml-2 h-4 w-4" />
              </PrimaryButton>

              <button
                onClick={handleClose}
                className="w-full py-2 text-[#757575] hover:text-[#EEEEEE] transition-colors text-[0.8125rem]"
              >
                Close and Return
              </button>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
