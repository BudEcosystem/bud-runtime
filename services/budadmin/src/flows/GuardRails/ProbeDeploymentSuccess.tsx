import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { CheckCircleOutlined } from "@ant-design/icons";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Text_16_600_FFFFFF } from "@/components/ui/text";

export default function ProbeDeploymentSuccess() {
  const { closeDrawer } = useDrawer();

  const handleDone = () => {
    closeDrawer();
  };

  return (
    <BudForm data={{}} onNext={handleDone} nextText="Done" showBack={false}>
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex flex-col items-center justify-center min-h-[400px] px-[2rem] py-[3rem]">
            {/* Success Icon Container */}
            <div className="mb-[2rem]">
              <div className="w-[120px] h-[120px] bg-[#1F1F1F] border-2 border-[#52C41A] rounded-[12px] flex items-center justify-center">
                <CheckCircleOutlined className="text-[#52C41A] text-[48px]" />
              </div>
            </div>

            {/* Success Message */}
            <Text_16_600_FFFFFF className="text-center mb-[0.5rem] text-[20px]">
              Probe Successfully
            </Text_16_600_FFFFFF>
            <Text_16_600_FFFFFF className="text-center text-[20px]">
              Deployed
            </Text_16_600_FFFFFF>

            {/* Additional Success Details (optional) */}
            <div className="mt-[2rem] text-center space-y-[0.5rem]">
              <div className="text-[#B3B3B3] text-[14px]">
                Your guardrail probe has been successfully deployed and is now
                active.
              </div>
              <div className="text-[#757575] text-[12px]">
                You can monitor its performance in the Guardrails dashboard.
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
