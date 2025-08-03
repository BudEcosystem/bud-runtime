import React, { useEffect } from "react";
import { Image } from "antd";

import { useDrawer } from "src/hooks/useDrawer";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";

import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { useDeployModel } from "src/stores/useDeployModel";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useWorkers } from "src/hooks/useWorkers";
import { useRouter } from "next/router";
import { Text_12_300_EEEEEE, Text_24_600_EEEEEE } from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

const NewExperimentSuccess: React.FC = () => {
  const { closeDrawer } = useDrawer();
  const { currentWorkflow, getWorkflow } = useDeployModel();
  const { getEndpointClusterDetails } = useEndPoints();
  const { getWorkers } = useWorkers();
  const router = useRouter();
  const projectId = router.query.projectId as string
  React.useEffect(() => {
    getWorkflow();
  }, []);

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.endpoint?.id) {
      getEndpointClusterDetails(currentWorkflow?.workflow_steps?.endpoint?.id, projectId);
      getWorkers(currentWorkflow?.workflow_steps?.endpoint?.id, projectId);
    }
  }, [currentWorkflow]);

  return (
    <BudForm
      data={{
      }}
      onBack={async () => {
        closeDrawer();
      }}
    >
      <BudWraperBox center={true}>
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
            <div className="max-w-[84%] mt-[1rem] mb-[3rem] flex flex-col items-center justify-center">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[70%]">
                New Experiment Successfully Created!
              </Text_24_600_EEEEEE>
              {/* <Text_12_400_B3B3B3 className="text-center">
          Ready to deploy models to this project? Let’s get started!
        </Text_12_400_B3B3B3> */}
            </div>
            <PrimaryButton
              onClick={() => {
                //reset();
                closeDrawer();
              }}
            >
              <div className="flex items-center justify-center gap">
                <Image
                  preview={false}
                  src="/images/deployRocket.png"
                  alt="info"
                  width={12}
                  height={12}
                />
                <Text_12_300_EEEEEE className="ml-[.3rem]">
                  View Experiment
                </Text_12_300_EEEEEE>
              </div>
            </PrimaryButton>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default NewExperimentSuccess;
