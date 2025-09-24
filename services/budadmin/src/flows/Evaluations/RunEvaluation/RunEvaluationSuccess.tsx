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
import BudStepAlert from "src/flows/components/BudStepAlert";

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
          <BudStepAlert
            type="success"
            title="Evaluation Complete"
            description={`The evaluation workflow for experiment ${currentWorkflow?.workflow_steps?.name} has been completed.
                You can now view the results and metrics in the experiment details page.`}
          />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
