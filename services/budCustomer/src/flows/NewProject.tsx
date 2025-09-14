import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextInput from "@/components/ui/bud/dataEntry/TextInput";
import { projectNameRegex } from "@/lib/utils";
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
  project_type: "client_app";
  benchmark: boolean;
}

export default function NewProject() {
  const {
    createProject: apiCreateProject,
    getGlobalProjects,
    getProjectTags,
    projectTags,
  } = useProjects();
  const { openDrawerWithStep } = useDrawer();
  const { form, submittable } = useContext(BudFormContext);
  const [options, setOptions] = useState<{ name: string; color: string }[]>([]);
  const [isCreating, setIsCreating] = useState(false);

  const fetchList = useCallback(() => {
    const data =
      projectTags?.map((result) => ({
        ...result,
        name: result.name,
        color: result.color,
      })) || [];
    setOptions(data);
  }, [projectTags]);

  useEffect(() => {
    getProjectTags();
  }, [getProjectTags]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  return (
    <>
      <style
        dangerouslySetInnerHTML={{
          __html: `
        /* Fix tags dropdown visibility in light theme */
        [data-theme="light"] .ant-select-dropdown {
          background-color: #FFFFFF !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item-option-content {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item-option-content span {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .rc-virtual-list-holder-inner .ant-select-item {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .rc-virtual-list-holder-inner .ant-select-item span {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item-option-selected {
          background-color: #F0F0F0 !important;
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item-option:hover {
          background-color: #F5F5F5 !important;
          color: #000000 !important;
        }
        /* Fix all text elements in dropdown */
        [data-theme="light"] .ant-select-dropdown * {
          color: #000000 !important;
        }
        /* Fix tag text visibility in light theme */
        [data-theme="light"] .ant-tag {
          color: #000000 !important;
        }
        /* Fix select input text in light theme */
        [data-theme="light"] .ant-select-selection-item {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-selection-item span {
          color: #000000 !important;
        }
      `,
        }}
      />
      <BudForm
        data={{
          name: "",
          description: "",
          tags: [],
          icon: "😍",
        }}
        onNext={(values) => {
          // Prevent multiple submissions
          if (isCreating) {
            return;
          }

          if (!submittable) {
            form.submit();
            return;
          }

          // Set loading state to prevent multiple clicks
          setIsCreating(true);

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
            name: values.name ? values.name.trim() : "",
            description: values.description ? values.description.trim() : "",
            tags: formattedTags,
            icon: values.icon || "😍",
            project_type: "client_app",
            benchmark: false,
          };

          // Additional validation to ensure name is not empty after trimming
          if (!projectData.name) {
            setIsCreating(false);
            return;
          }

          apiCreateProject(projectData)
            .then((result) => {
              if (result) {
                // Store project name temporarily for success screen
                localStorage.setItem("temp_project_name", values.name);
                // Refresh projects list
                getGlobalProjects(1, 10);
                // Navigate to success screen
                openDrawerWithStep("project-success");
              }
            })
            .catch((error) => {
              console.error("Error creating project:", error);
            })
            .finally(() => {
              // Reset loading state in case of error or if user navigates back
              setIsCreating(false);
            });
        }}
        nextText="Create Project"
        disableNext={isCreating}
        drawerLoading={isCreating}
      >
        <BudWraperBox center>
          <BudDrawerLayout>
            <DrawerTitleCard
              title="Create a new project"
              description="Let's get started by filling in the details below"
            />
            <DrawerCard classNames="pb-0">
              <TextInput
                name="name"
                label="Project Name"
                placeholder="Enter Project Name"
                preventFirstSpace={true}
                rules={[
                  {
                    required: true,
                    message: "Please Enter Project Name",
                  },
                  {
                    max: 30,
                    message: "Project name should be less than 30 characters",
                  },
                  {
                    pattern: projectNameRegex,
                    message: "Project name should contain only alphanumeric characters, spaces, hyphens, and underscores",
                  },
                  {
                    validator: (_, value) => {
                      if (value && value.trim().length === 0) {
                        return Promise.reject(new Error("Project name cannot be only spaces"));
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
              />
              <div className="flex justify-start items-center px-[.65rem] mb-[1.65rem] mt-4">
                <Icon
                  icon="ph:calendar"
                  className="text-bud-text-disabled mr-2 text-[0.875rem]"
                />
                <Text_12_400_B3B3B3>Created on&nbsp;&nbsp;</Text_12_400_B3B3B3>
                <Text_12_400_EEEEEE>
                  {dayjs().format("DD MMM, YYYY")}
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
    </>
  );
}
