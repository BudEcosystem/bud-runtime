import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Form } from "antd";
import { errorToast, successToast } from "@/components/toast";
import TextInput from "../components/TextInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import TagsInput, { Tag } from "@/components/ui/bud/dataEntry/TagsInput";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import { usePromptsAgents } from "@/stores/usePromptsAgents";
import { usePrompts } from "src/hooks/usePrompts";
import { useAddAgent } from "@/stores/useAddAgent";

// Type for agent tags - can be either a string or an object
type AgentTag = string | { name: string; color?: string };

export default function AgentEditDrawer() {
  const { drawerProps, closeDrawer } = useDrawer();
  const [form] = Form.useForm();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { fetchPrompts } = usePromptsAgents();
  const { getPromptVersions, versions } = usePrompts();
  const { getPromptTags, promptTags } = useAddAgent();

  // State for tags - both the current value and dropdown options
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagOptions, setTagOptions] = useState<Tag[]>([]);
  // Track if tags have been initialized from agent data
  const [tagsInitialized, setTagsInitialized] = useState(false);

  // Fetch prompt tags on component mount
  useEffect(() => {
    getPromptTags();
  }, [getPromptTags]);

  // Transform promptTags to tagOptions format
  useEffect(() => {
    if (promptTags && promptTags.length > 0) {
      const formattedTags = promptTags.map((tag) => ({
        name: tag.name,
        color: tag.color,
      }));
      setTagOptions(formattedTags);
    }
  }, [promptTags]);

  // Initialize form with agent data
  useEffect(() => {
    // Reset initialization state when agent changes
    setTagsInitialized(false);
    form.resetFields();

    if (drawerProps?.agent) {
      const agent = drawerProps.agent;

      // Format tags if they exist
      const formattedTags = (agent.tags && Array.isArray(agent.tags))
        ? agent.tags.map((tag: AgentTag) => {
            if (typeof tag === 'string') {
              return { name: tag, color: "#CaCF40" };
            }
            return { name: tag.name, color: tag.color || "#CaCF40" };
          })
        : [];

      // Set local tags state for TagsInput
      setTags(formattedTags);
      // Mark tags as initialized so TagsInput renders with correct initial value
      setTagsInitialized(true);

      form.setFieldsValue({
        name: agent.name || "",
        description: agent.description || "",
        tags: formattedTags,
        default_version: agent.default_version,
      });

      // Fetch versions
      if (agent.id) {
        getPromptVersions(agent.id);
      }
    }
  }, [drawerProps, form, getPromptVersions]);

  const handleNext = async () => {
    try {
      const values = await form.validateFields();

      setIsSubmitting(true);

      try {
        // Find the version ID corresponding to the entered version number
        let targetVersionId = drawerProps?.agent?.default_version_id;

        if (values.default_version) {
          const targetVersion = versions.find(v => v.version === Number(values.default_version));
          if (targetVersion) {
            targetVersionId = targetVersion.id;
          } else {
            errorToast(`Version ${values.default_version} not found`);
            setIsSubmitting(false);
            return;
          }
        }

        const payload = {
          name: values.name,
          description: values.description || "",
          tags: tags.map((tag: Tag) => ({
            name: tag.name,
            color: tag.color || "#CaCF40"
          })),
          default_version_id: targetVersionId
        };

        const response = await AppRequest.Patch(
          `${tempApiBaseUrl}/prompts/${drawerProps?.agent?.id}`,
          payload
        );

        if (response?.data) {
          successToast("Agent updated successfully");
          fetchPrompts(); // Refresh the list
          closeDrawer();
        } else {
          errorToast("Failed to update agent");
        }
      } catch (error) {
        console.error("Failed to update agent:", error);
        errorToast("Failed to update agent");
      } finally {
        setIsSubmitting(false);
      }
    } catch (error) {
      console.error("Validation failed:", error);
    }
  };

  const handleBack = () => {
    closeDrawer();
  };

  return (
    <BudForm
      form={form}
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText="Cancel"
      nextText="Save"
      disableNext={isSubmitting}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Edit Agent"
            description="Update your agent's details"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Name */}
            <div className="mb-[1.5rem]">
              <TextInput
                label="Name"
                name="name"
                placeholder="Enter agent name"
                rules={[{ required: true, message: "Please enter agent name" }]}
                ClassNames="mt-[.3rem]"
                formItemClassnames="mb-[1rem]"
                infoText="Enter a unique name for your agent"
                InputClasses="py-[.5rem]"
                disabled={true}
              />
            </div>

            {/* Default Version */}
            <div className="mb-[1.5rem]">
              <TextInput
                label="Default Version"
                name="default_version"
                placeholder="Enter default version number"
                allowOnlyNumbers={true}
                infoText="Enter the version number to be used by default"
                formItemClassnames="mb-[1rem]"
                InputClasses="py-[.5rem]"
                rules={[]}
              />
            </div>

            {/* Tags */}
            <div className="mb-[1.5rem]">
              {tagsInitialized && (
                <TagsInput
                  key={`tags-${drawerProps?.agent?.id}`}
                  label="Tags"
                  options={tagOptions}
                  defaultValue={tags}
                  onChange={setTags}
                  info="Add keywords to help organize and find your agent later"
                  name="tags"
                  required={false}
                  placeholder=""
                  rules={[]}
                />
              )}
            </div>

            {/* Description */}
            <div className="mb-[1.5rem]">
              <TextAreaInput
                name="description"
                label="Description"
                required={false}
                info="Provide a detailed description of your agent"
                placeholder="Enter description"
                rules={[]}
                formItemClassnames="mb-[1rem]"
              />
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
