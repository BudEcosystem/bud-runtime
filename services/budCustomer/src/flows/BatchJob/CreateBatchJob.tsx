import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useState } from "react";
import { Text_10_400_757575, Text_12_400_757575, Text_12_400_B3B3B3, Text_12_600_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { Select } from "antd";
import { Icon } from "@iconify/react/dist/iconify.js";
import { useDrawer } from "@/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import Tags from "../components/DrawerTags";

interface BatchJobFile {
  name: string;
  size: number;
  type: string;
  file: File;
}

export default function CreateBatchJob() {
  useContext(BudFormContext); // Required for form context
  const [batchJobData, setBatchJobData] = useState({
    name: "",
    model: "",
    file: null as BatchJobFile | null,
  });
  const { openDrawerWithStep } = useDrawer();
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.type !== "application/json" && !file.name.endsWith(".jsonl")) {
        errorToast("Please upload a JSONL file");
        return;
      }

      if (file.size > 100 * 1024 * 1024) { // 100MB limit
        errorToast("File size must be less than 100MB");
        return;
      }

      setBatchJobData({
        ...batchJobData,
        file: {
          name: file.name,
          size: file.size,
          type: file.type,
          file: file,
        },
      });
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (file.type !== "application/json" && !file.name.endsWith(".jsonl")) {
        errorToast("Please upload a JSONL file");
        return;
      }

      if (file.size > 100 * 1024 * 1024) { // 100MB limit
        errorToast("File size must be less than 100MB");
        return;
      }

      setBatchJobData({
        ...batchJobData,
        file: {
          name: file.name,
          size: file.size,
          type: file.type,
          file: file,
        },
      });
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

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
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Batch Job"
            description="Upload a JSONL file containing your batch requests"
          />
          <DrawerCard classNames="pb-0">
            <div className="pt-[.87rem]">
              {/* Job Name Input */}
              <div className="mb-[1.7rem]">
                <Text_14_400_EEEEEE className="p-0 pt-[.3rem] m-0">
                  Job Name
                </Text_14_400_EEEEEE>
                <Text_12_400_757575 className="pt-[.35rem] leading-[1.05rem] mb-[0.5rem]">
                  Enter a descriptive name for your batch job
                </Text_12_400_757575>
                <input
                  type="text"
                  placeholder="e.g., Product Descriptions Generation"
                  value={batchJobData.name}
                  onChange={(e) => setBatchJobData({ ...batchJobData, name: e.target.value })}
                  className="w-full bg-[#161616] border border-[#1F1F1F] text-[#EEEEEE] px-[0.75rem] py-[0.5rem] rounded-[6px] focus:outline-none focus:border-[#965CDE] transition-colors"
                />
              </div>

              {/* Model Selection */}
              <div className="mb-[1.7rem]">
                <Text_14_400_EEEEEE className="p-0 pt-[.3rem] m-0">
                  Select Model
                </Text_14_400_EEEEEE>
                <Text_12_400_757575 className="pt-[.35rem] leading-[1.05rem] mb-[0.5rem]">
                  Choose the model to process your batch requests
                </Text_12_400_757575>
                <Select
                  placeholder="Select a model"
                  value={batchJobData.model || undefined}
                  onChange={(value) => setBatchJobData({ ...batchJobData, model: value })}
                  className="w-full custom-select"
                  style={{ height: "40px" }}
                  options={[
                    { value: "gpt-4", label: "GPT-4" },
                    { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
                    { value: "claude-3-opus", label: "Claude 3 Opus" },
                    { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
                    { value: "claude-3.5-sonnet", label: "Claude 3.5 Sonnet" },
                  ]}
                />
              </div>

              {/* File Upload */}
              <div className="mb-[1.7rem]">
                <Text_14_400_EEEEEE className="p-0 pt-[.3rem] m-0">
                  Upload JSONL File
                </Text_14_400_EEEEEE>
                <Text_12_400_757575 className="pt-[.35rem] leading-[1.05rem] mb-[0.5rem]">
                  Upload the JSONL file containing your batch requests
                </Text_12_400_757575>

                {batchJobData.file ? (
                  <div className="flex justify-start items-center gap-2">
                    <Tags
                      tags={[batchJobData.file.name]}
                      color="#D1B854"
                      className="flex"
                    />
                    <button
                      onClick={() => {
                        setBatchJobData({
                          ...batchJobData,
                          file: null,
                        });
                        if (fileInputRef.current) {
                          fileInputRef.current.value = "";
                        }
                      }}
                      className="text-[#757575] hover:text-[#EEEEEE] text-[1.5rem] leading-none transition-colors"
                    >
                      ×
                    </button>
                  </div>
                ) : (
                  <div
                    className="border-2 border-dashed border-[#1F1F1F] hover:border-[#965CDE] rounded-[8px] p-[2rem] text-center cursor-pointer transition-colors bg-[#161616]"
                    onClick={() => fileInputRef.current?.click()}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".jsonl,application/json"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                    <Icon
                      icon="ph:upload-simple"
                      className="text-[2rem] text-[#757575] mb-[0.5rem] mx-auto"
                    />
                    <div className="flex justify-center items-center w-[100%]">
                      <Text_12_400_B3B3B3>Drag & Drop or </Text_12_400_B3B3B3>&nbsp;
                      <Text_12_600_EEEEEE>Choose file</Text_12_600_EEEEEE>&nbsp;
                      <Text_12_400_B3B3B3> to upload</Text_12_400_B3B3B3>
                    </div>
                    <Text_10_400_757575 className="mt-[0.5rem]">
                      Supported format: JSONL (Maximum file size: 100MB)
                    </Text_10_400_757575>
                  </div>
                )}
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
