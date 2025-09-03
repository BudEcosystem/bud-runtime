import ProjectSuccessCard from "@/components/ui/bud/card/ProjectSuccessCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { Text_12_300_EEEEEE, Text_12_400_B3B3B3, Text_24_600_EEEEEE } from "@/components/ui/text";
import { Image } from "antd";
import React from "react";
import { useDrawer } from "@/hooks/useDrawer";
import { useRouter } from "next/navigation";

interface Props {
  batchJobId?: string;
}

export default function CreateBatchJobSuccess(props: Props) {
  const { closeDrawer } = useDrawer();
  const router = useRouter();

  return (
    <BudForm
      data={{}}
    >
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center p-[2.5rem]">
            <div className="align-center pt-[.3rem]">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="success"
                style={{
                  width: '8.75rem',
                  height: '8.0625rem'
                }}
              />
            </div>
            <div className="max-w-[75%] mt-[1.3rem] pb-[1.6rem]">
              <Text_24_600_EEEEEE className="text-[black] dark:text-[#EEEEE] text-center leading-[2rem] mb-[1.2rem]">
                Batch Job Successfully<br /> Created
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center text-[black] dark:text-[#EEEEE]">
                Your batch job has been queued for processing. You can monitor its progress in the batch jobs dashboard.
              </Text_12_400_B3B3B3>
            </div>
            <PrimaryButton
              onClick={() => {
                closeDrawer();
                router.push(`/batches`);
              }}
            >
              <div className="flex items-center justify-center gap">
                <Text_12_300_EEEEEE>
                  View Batch Jobs
                </Text_12_300_EEEEEE>
              </div>
            </PrimaryButton>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
