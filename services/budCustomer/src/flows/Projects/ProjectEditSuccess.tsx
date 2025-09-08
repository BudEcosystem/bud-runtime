import React, { useEffect, useState } from "react";
import { Image } from "antd";
import { useDrawer } from "@/hooks/useDrawer";
import {
  Text_13_400_EEEEEE,
  Text_24_600_EEEEEE,
} from "@/components/ui/text";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Icon } from "@iconify/react/dist/iconify.js";

const ProjectEditSuccess = () => {
  const { closeDrawer } = useDrawer();
  const [projectName, setProjectName] = useState("");

  useEffect(() => {
    // Get the project name from localStorage (temporarily stored)
    const name = localStorage.getItem("temp_edited_project_name");
    if (name) {
      setProjectName(name);
      // Clean up after retrieving
      localStorage.removeItem("temp_edited_project_name");
    }
  }, []);

  return (
    <BudForm
      data={{}}
      nextText="Done"
      onNext={() => {
        closeDrawer();
      }}>
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center p-[2.5rem]">
            <div className="align-center mb-4">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="success"
                width={140}
                height={129}
              />
            </div>

            <div className="max-w-[84%] mt-[1rem] mb-[2rem] flex flex-col items-center justify-center">
              <Text_24_600_EEEEEE className="text-[black] dark:text-[#EEEEEE] text-center leading-[2rem] mb-[1.2rem]">
                Project Updated Successfully!
              </Text_24_600_EEEEEE>

              {projectName && (
                <Text_13_400_EEEEEE className="text-center text-[#B3B3B3]">
                  Your project &quot;{projectName}&quot; has been updated with the new details.
                </Text_13_400_EEEEEE>
              )}
            </div>

            <div className="bg-[#1F1F1F] border border-[#2F2F2F] rounded-[8px] p-[1.5rem] w-full max-w-[500px] flex items-start gap-[0.75rem]">
              <Icon
                icon="ph:check-circle"
                className="text-[#4ADE80] text-[1.25rem] flex-shrink-0"
              />
              <Text_13_400_EEEEEE>
                All changes have been saved. Your project settings are now up to date.
              </Text_13_400_EEEEEE>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default ProjectEditSuccess;
