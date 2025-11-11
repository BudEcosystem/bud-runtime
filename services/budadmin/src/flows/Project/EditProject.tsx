
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { PaperPublished, useModels } from "src/hooks/useModels";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { successToast } from "@/components/toast";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { useProjects } from "src/hooks/useProjects";
import { isValidProjectName } from "@/lib/utils";


function EditProjectForm() {
  const { selectedProject } = useProjects();
  const { values = {} } = useContext(BudFormContext);

  const [options, setOptions] = useState([]);

  async function fetchList(tagname) {
    await axiosInstance(`${tempApiBaseUrl}/models/tags?page=1&limit=1000`).then((result) => {
      const data = result.data?.tags?.map((result) => ({
        name: result.name,
        color: result.color,
      }));
      setOptions(data);
    });
  }

  useEffect(() => {
    fetchList("");
  }, []);

  return <BudWraperBox>
    <BudDrawerLayout>
      <DrawerTitleCard
        title="Edit Project"
        description="Make changes to project name, tags and description "
      />
      <DrawerCard classNames="pb-0">
        <ProjectNameInput
          placeholder="Enter Project Name"
        />
        <div className="mt-[.5rem]">
          <div>
            <TagsInput
              defaultValue={selectedProject?.tags}
              info="Enter Tags"
              name="tags"
              placeholder="Enter tags" rules={[
                { validator: (rule, value) => {
                  if (value.length === 0) {
                    return Promise.reject("Please select at least one tag");
                  }
                  return Promise.resolve();
                }}
              ]}
              label="Tags"
              options={options}
            />
          </div>

          <div className="mt-[.7rem]">
            <TextAreaInput
              name="description"
              label="Description"
              info="Write Description Here"
              placeholder="Write Description Here"
              rules={[{ required: true, message: "Please enter description" }]}
              value={values.description}
            />
          </div>
        </div>
      </DrawerCard>
    </BudDrawerLayout>
  </BudWraperBox>
}


export default function EditProject() {
  const { values, submittable } = useContext(BudFormContext);
  const { openDrawer, closeDrawer } = useDrawer();
  const { selectedProject, updateProject, getGlobalProject } = useProjects();


  return (
    <BudForm
      nextText="Save"
      disableNext={!submittable}
      onNext={async (values) => {
        const result = await updateProject(selectedProject?.id, {
          name: values?.name === selectedProject?.name ? undefined : values?.name,
          description: values?.description,
          icon: values?.icon,
          tags: values?.tags,
        });
        if (result) {
          await getGlobalProject(selectedProject?.id);
          // successToast("Project Updated Successfully")
          closeDrawer();
        }
      }}
      data={selectedProject}
    >
      <EditProjectForm />
    </BudForm>
  );
}
