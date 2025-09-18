import ProjectSuccessCard from "@/components/ui/bud/card/ProjectSuccessCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import {
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_24_600_EEEEEE,
} from "@/components/ui/text";
import { Image } from "antd";
import React, { useEffect } from "react";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { useRouter } from "next/navigation";
import { useDeployModel } from "src/stores/useDeployModel";

interface Props {
  text: string;
}

export default function CreateClusterSuccess(props: Props) {
  const { currentWorkflow, cancelClusterOnboarding } = useDeployModel();
  const { clusters } = useCluster();

  const { closeDrawer, openDrawer } = useDrawer();
  const router = useRouter();
  useEffect(() => {
    console.log("currentWorkflow", currentWorkflow);
  }, [currentWorkflow]);
  return (
    <BudForm data={{}}>
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <div className="flex flex-col	justify-start items-center p-[2.5rem]">
            <div className="align-center pt-[.3rem]">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="info"
                style={{
                  width: "8.75rem",
                  height: "8.0625",
                }}
              />
            </div>
            <div className="max-w-[75%] mt-[1.3rem] pb-[1.6rem]">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem]">
                Cluster Successfully
                <br /> added to the repository
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center">
                You can view the cluster now
              </Text_12_400_B3B3B3>
            </div>
            {clusters[0]?.id && (
              <PrimaryButton
                onClick={() => {
                  closeDrawer();
                  router.push(`/clusters/${clusters[0]?.id}`);
                }}
              >
                <div className="flex items-center justify-center gap">
                  <Text_12_300_EEEEEE>View Cluster</Text_12_300_EEEEEE>
                </div>
              </PrimaryButton>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
