import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useEffect, useState, useCallback } from "react";
import { useDrawer } from "@/hooks/useDrawer";
import { useProjects } from "@/hooks/useProjects";
import { Icon } from "@iconify/react/dist/iconify.js";
import { Text_12_400_B3B3B3, Text_12_400_EEEEEE } from "@/components/ui/text";
import dayjs from "dayjs";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";

interface ProjectData {
  name: string;
  description: string;
  tags: Array<{
    name: string;
    color: string;
  }>;
  icon: string;
}

export default function EditProject() {
  const {
    updateProject: apiUpdateProject,
    getGlobalProjects,
    getProjectTags,
    projectTags,
    globalSelectedProject,
  } = useProjects();
  const { closeDrawer } = useDrawer();
  const { form, submittable } = useContext(BudFormContext);
  const [options, setOptions] = useState<{ name: string; color: string }[]>([]);

  const fetchList = useCallback(() => {
    const data =
      projectTags?.map((result) => ({
        ...result,
        name: result.name,
        color: result.color,
      })) || [];
    setOptions(data);
  }, [projectTags]);

  // Get the current project data
  const currentProject: any = globalSelectedProject?.project || globalSelectedProject;

  useEffect(() => {
    getProjectTags();
  }, [getProjectTags]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // Set form values when component mounts or project changes
  useEffect(() => {
    if (currentProject && form) {
      const existingTags = currentProject.tags
        ? currentProject.tags.map((tag: any) => {
            // Handle both string and object tag formats
            if (typeof tag === 'string') {
              return { name: tag, color: "#89C0F2" };
            }
            return {
              name: tag.name || tag,
              color: tag.color || "#89C0F2",
            };
          })
        : [];

      // Use requestAnimationFrame to ensure form is ready and avoid conflicts
      requestAnimationFrame(() => {
        form.setFieldsValue({
          name: currentProject.name || "",
          description: currentProject.description || "",
          tags: existingTags,
          icon: currentProject.icon || "😍",
        });
        // Trigger form validation to update UI
        form.validateFields({ validateOnly: true });
      });
    }
  }, [currentProject, form]);

  // If no project is selected, show error
  if (!currentProject) {
    return (
      <BudForm
        data={{
          name: "",
          description: "",
          tags: [],
          icon: "😍",
        }}
        onNext={() => closeDrawer()}
        nextText="Close"
      >
        <BudWraperBox center>
          <BudDrawerLayout>
            <DrawerTitleCard
              title="Error"
              description="No project selected for editing"
            />
          </BudDrawerLayout>
        </BudWraperBox>
      </BudForm>
    );
  }

  // Format existing tags to ensure they have the correct structure
  const existingTags = currentProject?.tags
    ? currentProject.tags.map((tag: any) => {
        // Handle both string and object tag formats
        if (typeof tag === 'string') {
          return { name: tag, color: "#89C0F2" };
        }
        return {
          name: tag.name || tag,
          color: tag.color || "#89C0F2",
        };
      })
    : [];

  return (
    <BudForm
      data={{
        name: currentProject?.name || "",
        description: currentProject?.description || "",
        tags: existingTags,
        icon: currentProject?.icon || "😍",
      }}
      onNext={(values) => {
        if (!submittable) {
          form.submit();
          return;
        }

        // Ensure tags are in the correct format (array of objects with name and color)
        const formattedTags = values.tags
          ? (Array.isArray(values.tags) ? values.tags : [])
              .map((tag: any) => {
                // If tag is already in correct format, use it
                if (
                  tag &&
                  typeof tag === "object" &&
                  "name" in tag &&
                  "color" in tag
                ) {
                  return {
                    name: tag.name,
                    color: tag.color,
                  };
                }
                // If tag is a string, convert it
                if (typeof tag === "string") {
                  return {
                    name: tag,
                    color: "#89C0F2", // Default color
                  };
                }
                return null;
              })
              .filter(Boolean)
          : [];

        const projectData: ProjectData = {
          name: values.name,
          description: values.description,
          tags: formattedTags,
          icon: values.icon || "😍",
        };

        apiUpdateProject(currentProject.id, projectData)
          .then((result) => {
            if (result) {
              // Refresh projects list
              getGlobalProjects(1, 10);
              // Navigate to success or close drawer
              closeDrawer();
            }
          })
          .catch((error) => {
            console.error("Error updating project:", error);
          });
      }}
      nextText="Update Project"
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Edit project"
            description={`Update the details for ${currentProject.name}`}
          />
          <DrawerCard classNames="pb-0">
            <ProjectNameInput
              placeholder="Enter Project Name"
              onChangeName={(name) => form.setFieldsValue({ name })}
              onChangeIcon={(icon) => form.setFieldsValue({ icon })}
              isEdit={true}
              showIcon={false}
            />
            <div className="flex justify-start items-center px-[.65rem] mb-[1.65rem]">
              <Icon
                icon="ph:calendar"
                className="text-bud-text-disabled mr-2 text-[0.875rem]"
              />
              <Text_12_400_B3B3B3>Created on&nbsp;&nbsp;</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {currentProject.created_at
                  ? dayjs(currentProject.created_at).format("DD MMM, YYYY")
                  : dayjs().format("DD MMM, YYYY")}
              </Text_12_400_EEEEEE>
            </div>
            <TagsInput
              label="Tags"
              required
              options={options}
              info="Add keywords to help organize and find your project later."
              name="tags"
              placeholder="Add Tags (e.g. Data Science, Banking) "
              rules={[
                {
                  required: true,
                  message: "Please add tags to categorize the project.",
                },
              ]}
            />
            <div className="h-[1rem] w-full" />
            <TextAreaInput
              name="description"
              label="Description"
              required
              defaultValue={currentProject?.description || ""}
              info="This is the project's elevator pitch, use clear and concise words to summarize the project in few sentences"
              placeholder="Provide a brief description about the project."
              rules={[
                {
                  required: true,
                  message: "Provide a brief description about the project.",
                },
              ]}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
