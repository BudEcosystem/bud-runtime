import React, { useEffect } from "react";
import { Image } from "antd";
import { useDrawer } from "@/hooks/useDrawer";
import { useBlockingRules } from "@/stores/useBlockingRules";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_24_600_EEEEEE,
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

interface BlockingRuleSuccessProps {
  ruleName?: string;
  ruleType?: string;
}

const BlockingRuleSuccess: React.FC<BlockingRuleSuccessProps> = ({
  ruleName,
  ruleType,
}) => {
  const { closeDrawer, drawerProps } = useDrawer();
  const { fetchRules } = useBlockingRules();

  useEffect(() => {
    // Refresh the rules list
    fetchRules();
  }, []);

  return (
    <BudForm data={{}}>
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center p-[2.5rem]">
            <div className="align-center">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="success"
                width={140}
                height={129}
              />
            </div>
            <div className="max-w-[84%] mt-[1rem] mb-[3rem] flex flex-col items-center justify-center">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[70%]">
                Blocking Rule Created Successfully!
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center">
                Your rule "{drawerProps?.ruleName || ruleName}" is now active
                and protecting your gateway.
              </Text_12_400_B3B3B3>
            </div>
            <PrimaryButton
              onClick={() => {
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
                  View Rules
                </Text_12_300_EEEEEE>
              </div>
            </PrimaryButton>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default BlockingRuleSuccess;
