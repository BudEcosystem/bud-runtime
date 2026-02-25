import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { CheckCircleOutlined } from "@ant-design/icons";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Text_12_400_B3B3B3, Text_16_600_FFFFFF, Text_24_600_EEEEEE } from "@/components/ui/text";
import { Image } from "antd";

export default function ProbeDeploymentSuccess() {
  const { closeDrawer } = useDrawer();

  const handleDone = () => {
    closeDrawer();
  };

  return (
    <BudForm data={{}} onNext={handleDone} nextText="Done" showBack={false}>
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <div className="flex flex-col items-center justify-center min-h-[400px] px-[2rem] py-[3rem]">
            {/* Success Icon Container */}
            <div className="align-center">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="info"
                width={140}
                height={129}
              />
            </div>

            {/* Success Message */}
            <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[90%]">
              Probe Successfully Deployed
            </Text_24_600_EEEEEE>
            {/* Additional Success Details (optional) */}
            <div className="mt-[2rem] text-center space-y-[0.5rem]">
              <Text_12_400_B3B3B3 className="text-center">
                Your guardrail probe has been successfully deployed and is now
                active.
              </Text_12_400_B3B3B3>
              <div className="text-[#757575] text-[10px] text-center">
                You can monitor its performance in the Guardrails dashboard.
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
