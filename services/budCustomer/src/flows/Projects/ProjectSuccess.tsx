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

const ProjectSuccess = () => {
  const { closeDrawer } = useDrawer();
  const [projectName, setProjectName] = useState("");

  useEffect(() => {
    // Get the project name from localStorage (temporarily stored)
    const name = localStorage.getItem("temp_project_name");
    if (name) {
      setProjectName(name);
      // Clean up after retrieving
      localStorage.removeItem("temp_project_name");
    }
  }, []);

  return (
    <BudForm
      data={{}}
      nextText="Get Started"
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
                Project Created Successfully!
              </Text_24_600_EEEEEE>

              {projectName && (
                <Text_13_400_EEEEEE className="text-center text-[#B3B3B3]">
                  Your project &quot;{projectName}&quot; has been created and is ready to use.
                </Text_13_400_EEEEEE>
              )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default ProjectSuccess;
