import React from "react";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { colourOptions } from "@/components/ui/bud/dataEntry/TagsInputData";
import { successToast } from "@/components/toast";
import { useDrawer } from "src/hooks/useDrawer";
import { useEvaluations } from "src/hooks/useEvaluations";
import TextInput from "src/flows/components/TextInput";

const NewExperimentForm = React.memo(function NewExperimentForm() {
  const { experimentTags, getExperimentTags } = useEvaluations();

  // Add colors to tags that don't have one, cycling through the color palette
  const tagsWithColor = React.useMemo(() => {
    return (experimentTags || []).map((tag, index) => ({
      ...tag,
      color: tag.color || colourOptions[index % colourOptions.length].value,
    }));
  }, [experimentTags]);

  React.useEffect(() => {
    getExperimentTags();
  }, []);

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
          {
            max: 100,
            message: "Experiment name must not exceed 100 characters",
          },
          {
            pattern: /^[a-zA-Z0-9\s\-_]+$/,
            message:
              "Experiment name can only contain letters, numbers, spaces, hyphens, and underscores",
          },
          {
            validator: (_, value) => {
              if (value && value.trim().length === 0) {
                return Promise.reject(
                  "Experiment name cannot be only whitespace",
                );
              }
              return Promise.resolve();
            },
          },
        ]}
        ClassNames="mt-[.4rem]"
        InputClasses="py-[.5rem]"
      />
      <TagsInput
        label="Tags"
        required
        options={tagsWithColor}
        info="Add keywords to help organize and find your experiment later. Max 10 tags, 20 characters each."
        name="tags"
        placeholder="Select or Create tags that are relevant"
        rules={[
          {
            required: true,
            message: "Please add tags to create an experiment.",
          },
          {
            validator: (_, value) => {
              if (value && value.length > 10) {
                return Promise.reject("Maximum 10 tags allowed");
              }
              if (
                value &&
                value.some((tag: any) => {
                  const tagName = typeof tag === "string" ? tag : tag.name;
                  return tagName && tagName.length > 20;
                })
              ) {
                return Promise.reject("Each tag must be 20 characters or less");
              }
              if (
                value &&
                value.some((tag: any) => {
                  const tagName = typeof tag === "string" ? tag : tag.name;
                  return tagName && !/^[a-zA-Z0-9\-_]+$/.test(tagName);
                })
              ) {
                return Promise.reject(
                  "Tags can only contain letters, numbers, hyphens, and underscores",
                );
              }
              return Promise.resolve();
            },
          },
        ]}
        ClassNames="mb-[1rem]"
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
          { max: 500, message: "Description must not exceed 500 characters" },
          {
            validator: (_, value) => {
              if (value && value.trim().length === 0) {
                return Promise.reject("Description cannot be only whitespace");
              }
              if (value && value.trim().length < 10) {
                return Promise.reject(
                  "Description must be at least 10 characters (excluding leading/trailing spaces)",
                );
              }
              return Promise.resolve();
            },
          },
        ]}
      />
    </DrawerCard>
  );
});

export default function NewExperimentDrawer() {
  const { openDrawerWithStep } = useDrawer();
  const { createExperiment, getExperiments } = useEvaluations();

  const handleSubmit = async (values: any) => {
    try {
      // Trim and clean values before sending
      const cleanedName = values.experimentName?.trim();
      const cleanedDescription = values.description?.trim();
      // Tags are objects with {name, color}, extract just the names
      const cleanedTags = (values.tags || [])
        .map((tag: any) =>
          typeof tag === "string" ? tag.trim() : tag.name?.trim(),
        )
        .filter(Boolean);

      // Additional validation before API call
      if (!cleanedName || cleanedName.length < 3) {
        return;
      }
      if (!cleanedDescription || cleanedDescription.length < 10) {
        return;
      }

      // Map form values to API payload format matching the expected input
      const payload = {
        name: cleanedName?.toLowerCase(),
        description: cleanedDescription,
        // project_id: selectedProject?.id || "92ba4cb7-6ab8-49be-b211-a69a1b78feb4",
        tags: cleanedTags,
      };

      // Call the API to create experiment
      const response = await createExperiment(payload);
      console.log('createExperiment response', response)
      // Check if the response indicates success
      if (response && (response.id || response.experiment?.id || response.data?.id)) {
        // Show success message only when API returns success
        successToast("Experiment created successfully");

        // Refresh the experiments list
        await getExperiments({
          page: 1,
          limit: 10,
        });

        // Pass the experiment ID to the success screen
        openDrawerWithStep("new-experiment-success", {
          experimentId:
            response.id || response.experiment?.id || response.data?.id,
        });
      }
    } catch (error: any) {
      console.log('error', error)
      console.error("Failed to create experiment:", error);
    }
  };

  return (
    <BudForm
      data={{
        experimentName: "",
        tags: [],
        description: "",
      }}
      onNext={handleSubmit}
      nextText="Create"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="New Experiment"
            description="Create a new experiment to evaluate and compare model performance across different configurations, prompts, and datasets."
          />
          <NewExperimentForm />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
