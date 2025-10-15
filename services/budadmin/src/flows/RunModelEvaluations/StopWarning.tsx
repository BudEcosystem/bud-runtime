import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd"; // Added Checkbox import

export default function StopWarning() {
  const { closeDrawer, openDrawer } = useDrawer();

  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "🌐",
      }}
      onBack={() => {
        closeDrawer();
      }}
      onNext={(values) => {
        closeDrawer();
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex justify-start items-start py-[1.4rem] pb-[1.4rem] px-[1.7rem]">
            <div className="align-center w-[23%]">
              <Image
                preview={false}
                src="/images/drawer/warning.png"
                alt="info"
                style={{ width: "3.4375rem", maxHeight: "4.0625rem" }}
              />
            </div>
            <div className="w-full flex justify-center items-start flex-col">
              <Text_14_400_EEEEEE className="text-center leading-[1.3rem] mb-[.6rem]">
                You&apos;re about to stop evaluations
              </Text_14_400_EEEEEE>
              <Text_12_400_757575 className="text-left leading-[1.11rem]">
                If you choose to cancel evaluations are you sure you want to
                continue?
              </Text_12_400_757575>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
