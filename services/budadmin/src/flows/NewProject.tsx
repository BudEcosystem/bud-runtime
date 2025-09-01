
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useProjects } from "src/hooks/useProjects";
import { Image } from "antd";
import { Text_12_400_B3B3B3, Text_12_400_EEEEEE } from "@/components/ui/text";
import dayjs from "dayjs";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { axiosInstance } from "src/pages/api/requests";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";

export default function NewProject() {
  const { createProject, getProjects, getProject, projectValues, getProjectTags, projectTags } = useProjects();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { form, submittable } = useContext(BudFormContext);
  const [options, setOptions] = useState([]);

  async function fetchList() {
    const data = projectTags?.map((result) => ({
      ...result,
      name: result.name,
      color: result.color,
    }));
    setOptions(data);
  }

  useEffect(() => {
    getProjectTags()
  }, []);

  useEffect(() => {
    fetchList();
  }, [projectTags]);

  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "😍"
      }}
      // disableNext={!submittable}
      onNext={(values) => {
        if (!submittable) {
          form.submit();
          return;
        };

        createProject(values)
          .then((result) => {
            if (result) {
              getProjects(1, 10);
              getProject(result.id);
              openDrawerWithStep("invite-members");
            }
          })
      }}
      nextText="Next"
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create a new project"
            description="Let’s get started by filling in the details below"
          />
          <DrawerCard classNames="pb-0">
            <ProjectNameInput
              placeholder="Enter Project Name"
              isEdit={true}
            />
            <div className="flex justify-start items-center px-[.65rem] mb-[1.65rem]">
              <div className="h-[0.875rem] flex justify-start items-center grow-0 shrink-0">
                <Image
                  preview={false}
                  src="/images/drawer/calander.png"
                  alt="info"
                  style={{ height: '0.875rem', width: '0.875rem', marginRight: ".5rem" }}
                />
              </div>
              <Text_12_400_B3B3B3>Created on&nbsp;&nbsp;</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {dayjs().format("DD MMM, YYYY")}</Text_12_400_EEEEEE>
            </div>
            <TagsInput
              label="Tags"
              required
              options={options}
              info='Add keywords to help organize and find your project later.'
              name="tags" placeholder="Add Tags (e.g. Data Science, Banking) " rules={[
                { required: true, message: "Please add tags to categorize the project." }
              ]} />
            <div className="h-[1rem] w-full" />
            <TextAreaInput
              name="description"
              label="Description"
              required
              info="This is the project’s elevator pitch, use clear and concise words to summarize the project in few sentences"
              placeholder="Provide a brief description about the project."
              rules={[{ required: true, message: "Provide a brief description about the project." }]}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
