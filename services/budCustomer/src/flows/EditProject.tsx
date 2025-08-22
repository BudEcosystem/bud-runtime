import React, { useContext, useEffect, useState } from "react";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { useProjects } from "@/hooks/useProjects";
import { useDrawer } from "@/hooks/useDrawer";
import { AppRequest } from "@/services/api/requests";

function EditProjectForm() {
  const { globalSelectedProject, projectValues, setProjectValues } = useProjects();
  const { form, values = {} } = useContext(BudFormContext);
  const [options, setOptions] = useState([]);

  // Fetch available tags from the projects/tags endpoint
  async function fetchTags() {
    try {
      const response: any = await AppRequest.Get("/projects/tags?page=1&limit=1000");
      const data = response.data?.tags?.map((tag: any) => ({
        name: tag.name,
        color: tag.color,
      }));
      setOptions(data || []);
    } catch (error) {
      console.error("Error fetching tags:", error);
    }
  }

  useEffect(() => {
    fetchTags();
  }, []);

  // Initialize project values when component mounts
  useEffect(() => {
    if (globalSelectedProject?.project && form) {
      const projectData = globalSelectedProject.project;
      setProjectValues({
        name: projectData.name,
        description: projectData.description,
        tags: projectData.tags || [],
        icon: projectData.icon || "📁",
      });
      // Set form values for the form components to use
      form.setFieldsValue({
        name: projectData.name,
        description: projectData.description,
        tags: projectData.tags || [],
        icon: projectData.icon || "📁",
      });
    }
  }, [globalSelectedProject, setProjectValues, form]);

  return (
    <BudWraperBox>
      <BudDrawerLayout>
        <DrawerTitleCard
          title="Edit Project"
          description="Make changes to project name, tags and description"
        />
        <DrawerCard classNames="pb-0">
          <ProjectNameInput
            placeholder="Enter Project Name"
            isEdit={true}
            onChangeIcon={(icon) =>
              setProjectValues({
                ...projectValues,
                icon: icon,
              })
            }
            onChangeName={(name) =>
              setProjectValues({
                ...projectValues,
                name: name,
              })
            }
          />
          <div className="mt-[.5rem]">
            <div>
              <TagsInput
                info="Enter Tags"
                name="tags"
                placeholder="Enter tags"
                rules={[
                  {
                    validator: (rule, value) => {
                      if (!value || value.length === 0) {
                        return Promise.reject("Please select at least one tag");
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
                label="Tags"
                options={options}
                onChange={(tags) =>
                  setProjectValues({
                    ...projectValues,
                    tags: tags,
                  })
                }
              />
            </div>

            <div className="mt-[.7rem]">
              <TextAreaInput
                name="description"
                label="Description"
                info="Write Description Here"
                placeholder="Write Description Here"
                rules={[{ required: true, message: "Please enter description" }]}
                onChange={(description) =>
                  setProjectValues({
                    ...projectValues,
                    description: description,
                  })
                }
              />
            </div>
          </div>
        </DrawerCard>
      </BudDrawerLayout>
    </BudWraperBox>
  );
}

export default function EditProject() {
  const { values, submittable } = useContext(BudFormContext);
  const { closeDrawer } = useDrawer();
  const { globalSelectedProject, updateProject, getGlobalProject, projectValues, setProjectValues } = useProjects();

  // Reset project values when component unmounts
  useEffect(() => {
    return () => {
      setProjectValues(null);
    };
  }, [setProjectValues]);

  return (
    <BudForm
      nextText="Save"
      disableNext={!submittable}
      onNext={async (values) => {
        try {
          const projectId = globalSelectedProject?.project?.id;
          if (!projectId) {
            throw new Error("No project selected");
          }

          // Prepare the update payload according to API spec
          const updatePayload: any = {};

          // Only include fields that have changed
          if (projectValues?.name && projectValues.name !== globalSelectedProject?.project?.name) {
            updatePayload.name = projectValues.name;
          }

          if (values?.description !== undefined) {
            updatePayload.description = values.description;
          }

          if (projectValues?.icon !== undefined) {
            updatePayload.icon = projectValues.icon;
          }

          if (values?.tags !== undefined) {
            updatePayload.tags = values.tags;
          }

          // Call the API to update the project
          const result = await updateProject(projectId, updatePayload);

          if (result) {
            // Refresh the project data
            await getGlobalProject(projectId);
            closeDrawer();
          }
        } catch (error) {
          console.error("Error updating project:", error);
        }
      }}
      data={{
        name: globalSelectedProject?.project?.name || "",
        description: globalSelectedProject?.project?.description || "",
        tags: globalSelectedProject?.project?.tags || [],
        icon: globalSelectedProject?.project?.icon || "📁",
      }}
    >
      <EditProjectForm />
    </BudForm>
  );
}
