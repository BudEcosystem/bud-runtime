import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";

import { useEvaluations } from "src/hooks/useEvaluations";
import { successToast } from "@/components/toast";
import BudStepAlert from "src/flows/components/BudStepAlert";
import CommonStatus from "src/flows/components/CommonStatus";
import { useRouter } from "next/router";


export default function RunEvaluationStatus() {

    const { openDrawerWithStep, closeDrawer, drawerProps } = useDrawer();
    const { currentWorkflow, getExperimentDetails } = useEvaluations();
    const [isFailed, setIsFailed] = React.useState(false);
    const [showAlert, setShowAlert] = React.useState(false);
    const router = useRouter();
    // const experimentId = currentWorkflow?.experiment_id || drawerProps?.experimentId;
    const { experimentId } = router.query;
    const handleBack = () => {
        if (isFailed) {
            openDrawerWithStep("evaluation-summary");
        } else {
            setShowAlert(true);
        }
    }

    return <BudForm
        data={{}}
        backText={isFailed ? "Back" : "Cancel"}
        onBack={handleBack}
    >
        <BudWraperBox>
            {showAlert && <BudDrawerLayout>
                <BudStepAlert
                    type="warning"
                    title="You're about to cancel the run evaluation process"
                    description="Please note that if you cancel now, you will have to start the process again."
                    cancelText="Continue Finding"
                    confirmText="Cancel Anyways"
                    confirmAction={async () => {
                        // TODO: Add API call to cancel evaluation workflow if needed
                        successToast("Evaluation cancelled");
                        closeDrawer();
                    }}
                    cancelAction={() => {
                        setShowAlert(false)
                    }}
                />
            </BudDrawerLayout>}
            <CommonStatus
                workflowId={currentWorkflow?.workflow_id}
                events_field_id="evaluation_events"
                success_payload_type="evaluate_model"
                onCompleted={() => {
                    console.log("Evaluation completed");
                    getExperimentDetails(experimentId.toString());
                    openDrawerWithStep("run-evaluation-success");
                }}
                onFailed={() => {
                    setIsFailed(true);
                }}
                title="Running Evaluation"
                description={`We've started running the evaluation workflow for ${currentWorkflow?.workflow_steps?.name}. This process may take a while depending on the selected evaluations and model. Feel free to minimize the screen, we'll notify you once it's done.`}
            />
        </BudWraperBox>
    </BudForm>
}
