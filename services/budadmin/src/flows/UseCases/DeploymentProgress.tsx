/**
 * DeploymentProgress - Real-time deployment progress view for BudUseCases
 *
 * Uses CommonStatus component with Novu WebSocket for real-time updates,
 * backed by budapp workflow persistence for page-refresh resilience.
 */

import React, { useState } from "react";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_13_400_B3B3B3 } from "@/components/ui/text";
import { useUseCases } from "src/stores/useUseCases";
import { useDrawer } from "src/hooks/useDrawer";
import CommonStatus from "@/flows/components/CommonStatus";

export default function DeploymentProgress() {
  const { selectedDeployment: deployment } = useUseCases();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const [failed, setFailed] = useState(false);

  if (!deployment) {
    return (
      <BudForm data={{}} onBack={() => closeDrawer()} backText="Close">
        <BudWraperBox>
          <BudDrawerLayout>
            <div className="p-6 text-center">
              <Text_13_400_B3B3B3>No deployment selected.</Text_13_400_B3B3B3>
            </div>
          </BudDrawerLayout>
        </BudWraperBox>
      </BudForm>
    );
  }

  // If no workflow_id is available (e.g. legacy deployment), show a basic message
  if (!deployment.workflow_id) {
    return (
      <BudForm data={{}} onBack={() => closeDrawer()} backText="Close">
        <BudWraperBox>
          <BudDrawerLayout>
            <div className="p-6 text-center">
              <Text_13_400_B3B3B3>
                Deployment started. Progress tracking is not available for this deployment.
              </Text_13_400_B3B3B3>
            </div>
          </BudDrawerLayout>
        </BudWraperBox>
      </BudForm>
    );
  }

  return (
    <BudForm
      data={{}}
      onBack={() => closeDrawer()}
      backText={failed ? "Close" : "Close"}
    >
      <BudWraperBox>
        <CommonStatus
          workflowId={deployment.workflow_id}
          events_field_id="usecase_deployment_events"
          success_payload_type="usecase_deployment"
          onCompleted={() => openDrawerWithStep("deploy-usecase-success")}
          onFailed={() => setFailed(true)}
          title="Use Case Deployment In Progress"
          description={
            failed ? (
              <>
                Deployment failed. Check the step details below for more information.
              </>
            ) : (
              <>
                Deploying <strong className="text-[#EEEEEE]">{deployment.name}</strong> to your cluster.
                You can close this drawer and check back later.
              </>
            )
          }
        />
      </BudWraperBox>
    </BudForm>
  );
}
