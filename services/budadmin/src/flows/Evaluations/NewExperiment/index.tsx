import React, { useState } from "react";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { successToast } from "@/components/toast";
import { useDrawer } from "src/hooks/useDrawer";
import { useEvaluations } from "src/hooks/useEvaluations";
import { useProjects } from "src/hooks/useProjects";
import TextInput from "src/flows/components/TextInput";

const NewExperimentForm = React.memo(() => {
  const [options] = useState([]);


  return (
    <DrawerCard>
      <TextInput
        name="experimentName"
        label="Experiment Name"
        placeholder="Type experiment name"
        infoText="Experiment name must be 3-100 characters long"
        rules={[
          { required: true, message: "Experiment name is required" },
          { min: 3, message: "Experiment name must be at least 3 characters" },
          { max: 100, message: "Experiment name must not exceed 100 characters" },
          {
            pattern: /^[a-zA-Z0-9\s\-_]+$/,
            message: "Experiment name can only contain letters, numbers, spaces, hyphens, and underscores"
          },
          {
            validator: (_, value) => {
              if (value && value.trim().length === 0) {
                return Promise.reject("Experiment name cannot be only whitespace");
              }
              return Promise.resolve();
            }
          }
        ]}
        ClassNames="mt-[.4rem]"
        InputClasses="py-[.5rem]"
      />
      <TagsInput
        label="Tags"
        options={options}
        info="Add keywords to help organize and find your experiment later. Max 10 tags, 20 characters each."
        name="tags"
        placeholder="Select or Create tags that are relevant"
        rules={[
          {
            validator: (_, value) => {
              if (value && value.length > 10) {
                return Promise.reject("Maximum 10 tags allowed");
              }
              if (value && value.some((tag: string) => tag.length > 20)) {
                return Promise.reject("Each tag must be 20 characters or less");
              }
              if (value && value.some((tag: string) => !/^[a-zA-Z0-9\-_]+$/.test(tag))) {
                return Promise.reject("Tags can only contain letters, numbers, hyphens, and underscores");
              }
              return Promise.resolve();
            }
          }
        ]}
        ClassNames="mb-[0px]"
        SelectClassNames="mb-[.5rem]"
        menuplacement="top"
      />
      <TextAreaInput
        name="description"
        label="Description"
        required
        info="This is the experiment's elevator pitch. Use clear and concise words to summarize in a few sentences (10-500 characters)."
        placeholder="Provide a brief description about the experiment."
        rules={[
          { required: true, message: "Description is required" },
          { min: 10, message: "Description must be at least 10 characters" },
          { max: 500, message: "Description must not exceed 500 characters" },
          {
            validator: (_, value) => {
              if (value && value.trim().length === 0) {
                return Promise.reject("Description cannot be only whitespace");
              }
              if (value && value.trim().length < 10) {
                return Promise.reject("Description must be at least 10 characters (excluding leading/trailing spaces)");
              }
              return Promise.resolve();
            }
          }
        ]}
      />
    </DrawerCard>
  );
});

export default function NewExperimentDrawer() {
  const { openDrawerWithStep } = useDrawer();
  const { createExperiment } = useEvaluations();
  const { selectedProject } = useProjects();

  const handleSubmit = async (values: any) => {
    try {
      // Trim and clean values before sending
      const cleanedName = values.experimentName?.trim();
      const cleanedDescription = values.description?.trim();
      // Tags are objects with {name, color}, extract just the names
      const cleanedTags = (values.tags || []).map((tag: any) =>
        typeof tag === 'string' ? tag.trim() : tag.name?.trim()
      ).filter(Boolean);

      // Additional validation before API call
      if (!cleanedName || cleanedName.length < 3) {
        throw new Error("Invalid experiment name");
      }
      if (!cleanedDescription || cleanedDescription.length < 10) {
        throw new Error("Invalid description");
      }

      // Map form values to API payload format
      const payload = {
        name: cleanedName,
        description: cleanedDescription,
        project_id: selectedProject?.id || "36feef53-e271-4282-9de5-993b211a1c57", // Hardcoded as fallback
        tags: cleanedTags
      };

      // Call the API to create experiment
      await createExperiment(payload);

      successToast("Experiment created successfully");
      openDrawerWithStep("new-experiment-success");
    } catch (error) {
      console.error("Failed to create experiment:", error);
    }
  };

  return (
    <BudForm
      data={{
        experimentName: "",
        tags: [],
        description: "",
        model: undefined,
      }}
      onNext={handleSubmit}
      nextText="Create"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="New Experiment"
            description="A route allows you to create a custom OpenAI Compatible endpoint, with a swarm of models working together based on"
          />
          <NewExperimentForm />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
