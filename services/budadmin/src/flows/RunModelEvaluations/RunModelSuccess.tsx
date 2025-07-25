
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3, Text_24_600_EEEEEE } from "@/components/ui/text";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd"; // Added Checkbox import

export default function RunModelSuccess() {
  const { closeDrawer, openDrawer } = useDrawer()

  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "😍"
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
            <div className="mt-[1rem] mb-[3rem] w-full flex justify-center items-center flex-col	">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[70%]">
                Model Successfully Added To Repository
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center leading-[1.125rem] max-w-[85%]">
              Your model Evaluation are still running, we will send you a notification when it’s done and you can see the results later. 
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
