import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useState } from "react";
import { Text_10_400_757575, Text_12_400_757575, Text_12_400_B3B3B3, Text_12_600_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { Select, Form, Input, ConfigProvider } from "antd";
import { useDrawer } from "@/hooks/useDrawer";
import ThemedLabel from "@/components/ui/bud/dataEntry/ThemedLabel";
import FileInput from "../components/FileInput";

interface BatchJobFile {
  name: string;
  size: number;
  type: string;
  file: File;
}

export default function CreateBatchJob() {
  const { form } = useContext(BudFormContext); // Required for form context
  const [batchJobData, setBatchJobData] = useState({
    name: "",
    model: "",
    file: null as BatchJobFile | null,
  });
  const { openDrawerWithStep } = useDrawer();

  const isFormValid = batchJobData.name && batchJobData.model && batchJobData.file;

  return (
    <BudForm
      data={{
        ...batchJobData,
      }}
      disableNext={!isFormValid}
      onNext={async () => {
        // Here you would submit the batch job to your backend
        // For now, we'll just navigate to the success screen
        openDrawerWithStep("create-batch-job-success");
      }}
      onBack={() => {
        openDrawerWithStep(""); // Close drawer
      }}
    >
      <style dangerouslySetInnerHTML={{ __html: `
        /* Drawer title and description text colors for light theme */
        [data-theme="light"] .text-sm {
          color: #000000 !important;
        }
        [data-theme="light"] .text-xs {
          color: #757575 !important;
        }

        /* Input border colors - #B1B1B1 for all themes */
        input.drawerInp {
          border: 0.5px solid #B1B1B1 !important;
        }
        input.drawerInp:hover {
          border: 0.5px solid #757575 !important;
        }
        input.drawerInp:focus {
          border: 0.5px solid #757575 !important;
        }
        /* Light theme text colors for inputs */
        [data-theme="light"] input.drawerInp {
          color: #000000 !important;
        }
        [data-theme="light"] input.drawerInp::placeholder {
          color: #808080 !important;
        }

        /* Select component borders */
        .model-select-wrapper .ant-select {
          border: none !important;
        }
        .model-select-wrapper .ant-select .ant-select-selector {
          border: 0.5px solid #B1B1B1 !important;
          border-radius: 6px !important;
          background-color: transparent !important;
        }
        .model-select-wrapper .ant-select:hover .ant-select-selector {
          border: 0.5px solid #757575 !important;
        }
        .model-select-wrapper .ant-select-focused .ant-select-selector {
          border: 0.5px solid #757575 !important;
          box-shadow: none !important;
        }
        /* Fix Select placeholder font size to match input */
        .model-select-wrapper .ant-select-selection-placeholder {
          font-size: 0.75rem !important;
        }
        /* Light theme text colors for select */
        [data-theme="light"] .model-select-wrapper .ant-select-selection-item {
          color: #000000 !important;
        }
        [data-theme="light"] .model-select-wrapper .ant-select-selection-placeholder {
          color: #808080 !important;
        }
        [data-theme="light"] .model-select-wrapper .ant-select-dropdown {
          background-color: #FFFFFF !important;
        }
        [data-theme="light"] .model-select-wrapper .ant-select-item {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item-option-selected {
          background-color: #F0F0F0 !important;
        }
        [data-theme="light"] .ant-select-dropdown .ant-select-item:hover {
          background-color: #F5F5F5 !important;
        }

        /* File upload border - #B1B1B1 */
        .ant-upload-dragger {
          border: 0.5px solid #B1B1B1 !important;
          border-style: solid !important;
        }
        .ant-upload-dragger:hover {
          border: 0.5px solid #757575 !important;
          border-style: solid !important;
        }
        /* Light theme text colors for file upload */
        [data-theme="light"] .ant-upload-dragger .ant-upload-text {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-upload-dragger .ant-upload-hint {
          color: #808080 !important;
        }
        [data-theme="light"] .ant-upload-dragger p {
          color: #000000 !important;
        }
        [data-theme="light"] .ant-upload-dragger span {
          color: #000000 !important;
        }
      ` }} />
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Batch Job"
            description="Upload a JSONL file containing your batch requests"
          />
          <div className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
            {/* Job Name Input */}
            <Form.Item
              hasFeedback
              name={"name"}
              rules={[{ required: true, message: "Please input job name!" }]}
              className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
            >
              <div className="w-full">
                <ThemedLabel text="Job Name" info="Enter a descriptive name for your batch job" />
              </div>
              <Input
                placeholder="e.g., Product Descriptions Generation"
                style={{
                  backgroundColor: "transparent",
                  color: "#EEEEEE",
                  border: "0.5px solid #B1B1B1",
                }}
                size="large"
                onChange={(e) => {
                  form.setFieldsValue({ name: e.target.value });
                  form.validateFields(["name"]);
                  setBatchJobData({ ...batchJobData, name: e.target.value });
                }}
                className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#B1B1B1] rounded-[6px] hover:border-[#757575] focus:border-[#757575] active:border-[#757575] text-[.75rem] shadow-none w-full indent-[.4rem]"
              />
            </Form.Item>

            {/* Model Selection */}
            <Form.Item
              hasFeedback
              rules={[{ required: true, message: "Please select model!" }]}
              name={"model"}
              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
            >
              <div className="w-full">
                <ThemedLabel text="Select Model" info="Choose the model to process your batch requests" />
              </div>
              <div className="model-select-wrapper w-full">
                <ConfigProvider
                  theme={{
                    token: {
                      colorTextPlaceholder: "#808080",
                      boxShadowSecondary: "none",
                    },
                  }}
                >
                  <Select
                    variant="borderless"
                    placeholder="Select a model"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                      width: "100%",
                      fontSize: ".75rem",
                    }}
                    size="large"
                    className="!bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full outline-0 h-[2.5rem] outline-none [&_.ant-select-selection-placeholder]:text-[.75rem]"
                    options={[
                      { value: "gpt-4", label: "GPT-4" },
                      { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
                      { value: "claude-3-opus", label: "Claude 3 Opus" },
                      { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
                      { value: "claude-3.5-sonnet", label: "Claude 3.5 Sonnet" },
                    ]}
                    onChange={(value) => {
                      form.setFieldsValue({ model: value });
                      form.validateFields(["model"]);
                      setBatchJobData({ ...batchJobData, model: value });
                    }}
                  />
                </ConfigProvider>
              </div>
            </Form.Item>

            {/* File Upload with FileInput component */}
            <FileInput
              name="jsonl_file"
              acceptedFileTypes={['.jsonl', '.json']}
              label="Upload JSONL File"
              placeholder=""
              infoText="Upload the JSONL file containing your batch requests"
              required
              text={
                <div className="flex justify-center items-center w-[100%]">
                  <Text_12_400_B3B3B3>Drag & Drop or </Text_12_400_B3B3B3>&nbsp;
                  <Text_12_600_EEEEEE>Choose file</Text_12_600_EEEEEE>&nbsp;
                  <Text_12_400_B3B3B3> to upload</Text_12_400_B3B3B3>
                </div>
              }
              hint={
                <>
                  <Text_10_400_757575>Supported format: JSONL (Maximum file size: 100MB)</Text_10_400_757575>
                </>
              }
              rules={[{ required: true, message: "Please upload a JSONL file" }]}
              onChange={(value) => {
                if (value) {
                  setBatchJobData({
                    ...batchJobData,
                    file: {
                      name: value.name,
                      size: value.size,
                      type: value.type,
                      file: value,
                    },
                  });
                }
              }}
            />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
