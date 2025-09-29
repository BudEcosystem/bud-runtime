import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Form, InputNumber, Switch, Input } from "antd";
import { errorToast } from "@/components/toast";
import TextInput from "../components/TextInput";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import TagsInput, { Tag } from "@/components/ui/bud/dataEntry/TagsInput";

const { TextArea } = Input;

export default function AgentConfiguration() {
  const { openDrawerWithStep } = useDrawer();
  const [form] = Form.useForm();

  // State for form values
  const [deploymentName, setDeploymentName] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [description, setDescription] = useState("");
  const [minConcurrency, setMinConcurrency] = useState(1);
  const [maxConcurrency, setMaxConcurrency] = useState(10);
  const [autoScale, setAutoScale] = useState(true);
  const [autoCaching, setCaching] = useState(true);
  const [autoLogging, setAutoLogging] = useState(true);

  // Tag options for the tags input
  const tagOptions: Tag[] = [
    { name: "test", color: "#FF6B6B" },
    { name: "production", color: "#4ECDC4" },
    { name: "development", color: "#45B7D1" },
    { name: "staging", color: "#96CEB4" },
  ];

  const handleNext = async () => {
    try {
      await form.validateFields();

      if (!deploymentName) {
        errorToast("Please enter a deployment name");
        return;
      }

      if (tags.length === 0) {
        errorToast("Please add at least one tag");
        return;
      }

      // Get previously stored data
      const projectData = localStorage.getItem("addAgent_selectedProject");
      const modelData = localStorage.getItem("addAgent_selectedModel");

      // Store configuration data
      const configData = {
        deploymentName,
        tags,
        description,
        minConcurrency,
        maxConcurrency,
        autoScale,
        autoCaching,
        autoLogging,
        project: projectData ? JSON.parse(projectData) : null,
        model: modelData ? JSON.parse(modelData) : null,
      };

      localStorage.setItem("addAgent_configuration", JSON.stringify(configData));

      // Navigate to the deployment warning screen
      openDrawerWithStep("add-agent-deployment-warning");

    } catch (error) {
      console.error("Validation failed:", error);
    }
  };

  const handleBack = () => {
    openDrawerWithStep("add-agent-select-model");
  };

  return (
    <BudForm
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Title"
            description="Agent's description"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Deployment Name */}
            <div className="mb-[1.5rem]">
              <TextInput
                label="Deployment Name"
                name="deploymentName"
                placeholder="Enter deployment name"
                rules={[{ required: true, message: "Please enter deployment name" }]}
                value={deploymentName}
                onChange={(value: string) => setDeploymentName(value)}
                ClassNames="mt-[.3rem]"
                formItemClassnames="mb-[1rem]"
                infoText="Enter a unique name for your agent deployment"
                InputClasses="py-[.5rem]"
              />
            </div>

            {/* Tags */}
            <div className="mb-[1.5rem]">
              <Form.Item
                name="tags"
                rules={[{ required: true, message: "Please add at least one tag" }]}
                className="mb-[1rem]"
              >
                <TagsInput
                  label="Tags"
                  options={tagOptions}
                  defaultValue={tags}
                  onChange={setTags}
                  info="Add keywords to help organize and find your agent later"
                  name="tags"
                  required={true} placeholder={""} rules={[]}                />
              </Form.Item>
            </div>

            {/* Description */}
            <div className="mb-[1.5rem]">
              <Form.Item name="description" className="mb-[1rem]">
                <div className="float-label">
                  <InfoLabel
                    text="Description"
                    content="Provide a detailed description of your agent's purpose and capabilities"
                  />
                  <TextArea
                    placeholder="Enter description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={4}
                    className="mt-[.5rem] bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                    }}
                  />
                </div>
              </Form.Item>
            </div>

            {/* Concurrency Settings */}
            <div className="mb-[1.5rem]">
              <InfoLabel
                text="Concurrency"
                content="Set the minimum and maximum concurrent requests"
              />
              <div className="flex gap-[1rem] mt-[.5rem]">
                <div className="flex-1">
                  <Text_12_400_757575 className="mb-[.25rem]">Min</Text_12_400_757575>
                  <InputNumber
                    min={1}
                    max={100}
                    value={minConcurrency}
                    onChange={(value) => setMinConcurrency(value || 1)}
                    className="w-full bg-transparent text-[#EEEEEE] border-[#757575]"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                    }}
                  />
                </div>
                <div className="flex-1">
                  <Text_12_400_757575 className="mb-[.25rem]">Max</Text_12_400_757575>
                  <InputNumber
                    min={1}
                    max={100}
                    value={maxConcurrency}
                    onChange={(value) => setMaxConcurrency(value || 10)}
                    className="w-full bg-transparent text-[#EEEEEE] border-[#757575]"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Toggle Switches */}
            <div className="space-y-[1rem]">
              {/* Auto Scale */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Auto Scale</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={autoScale}
                  onChange={setAutoScale}
                  style={{
                    backgroundColor: autoScale ? "#965CDE" : "#757575",
                  }}
                />
              </div>

              {/* Caching */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Caching</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={autoCaching}
                  onChange={setCaching}
                  style={{
                    backgroundColor: autoCaching ? "#965CDE" : "#757575",
                  }}
                />
              </div>

              {/* Auto Logging */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Auto Logging</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={autoLogging}
                  onChange={setAutoLogging}
                  style={{
                    backgroundColor: autoLogging ? "#965CDE" : "#757575",
                  }}
                />
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
