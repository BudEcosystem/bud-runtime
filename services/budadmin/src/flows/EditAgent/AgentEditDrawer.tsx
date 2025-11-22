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

export default function AgentEditDrawer() {
  const { drawerProps, closeDrawer } = useDrawer();
  const [form] = Form.useForm();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { fetchPrompts } = usePromptsAgents();
  const { getPromptVersions, versions, versionsLoading } = usePrompts();

  // State for form values
  const [name, setName] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [description, setDescription] = useState("");
  const [tagOptions, setTagOptions] = useState<Tag[]>([]);
  const [defaultVersion, setDefaultVersion] = useState<number | undefined>(undefined);

  // Initialize form with agent data
  useEffect(() => {
    if (drawerProps?.agent) {
      const agent = drawerProps.agent;
      setName(agent.name || "");
      setDescription(agent.description || "");

      // Format tags if they exist
      if (agent.tags && Array.isArray(agent.tags)) {
        const formattedTags = agent.tags.map((tag: any) => {
          if (typeof tag === 'string') {
            return { name: tag, color: "#CaCF40" };
          }
          return { name: tag.name, color: tag.color || "#CaCF40" };
        });
        setTags(formattedTags);
        form.setFieldsValue({ tags: formattedTags });
      }

      form.setFieldsValue({
        name: agent.name || "",
        description: agent.description || ""
      });

      // Set default version directly from agent data
      if (agent.default_version) {
        setDefaultVersion(agent.default_version);
        form.setFieldsValue({ default_version: agent.default_version });
      }

      // Fetch versions
      if (agent.id) {
        getPromptVersions(agent.id);
      }
    }
  }, [drawerProps]);

  const handleNext = async () => {
    try {
      await form.validateFields();

      if (!name) {
        errorToast("Please enter an agent name");
        return;
      }

      setIsSubmitting(true);

      try {
        // Find the version ID corresponding to the entered version number
        let targetVersionId = drawerProps?.agent?.default_version_id;

        if (defaultVersion) {
          const targetVersion = versions.find(v => v.version === Number(defaultVersion));
          if (targetVersion) {
            targetVersionId = targetVersion.id;
          } else {
            errorToast(`Version ${defaultVersion} not found`);
            setIsSubmitting(false);
            return;
          }
        }

        const payload = {
          name: name,
          description: description || "",
          tags: tags.map(tag => ({
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
                value={name}
                onChange={(value: string) => setName(value)}
                ClassNames="mt-[.3rem]"
                formItemClassnames="mb-[1rem]"
                infoText="Enter a unique name for your agent"
                InputClasses="py-[.5rem]"
              />
            </div>

            {/* Default Version */}
            <div className="mb-[1.5rem]">
              <TextInput
                label="Default Version"
                name="default_version"
                placeholder="Enter default version number"
                value={defaultVersion}
                onChange={(value) => setDefaultVersion(Number(value))}
                allowOnlyNumbers={true}
                infoText="Enter the version number to be used by default"
                formItemClassnames="mb-[1rem]"
                InputClasses="py-[.5rem]"
                rules={[]}
              />
            </div>

            {/* Tags */}
            <div className="mb-[1.5rem]">
              <TagsInput
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
            </div>

            {/* Description */}
            <div className="mb-[1.5rem]">
              <TextAreaInput
                name="description"
                label="Description"
                required={false}
                info="Provide a detailed description of your agent"
                placeholder="Enter description"
                value={description}
                onChange={(value: string) => setDescription(value)}
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
