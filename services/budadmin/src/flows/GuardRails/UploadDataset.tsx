import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Upload, message } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";

const { Dragger } = Upload;

export default function UploadDataset() {
  const { openDrawerWithStep } = useDrawer();
  const [fileList, setFileList] = useState<any[]>([]);

  const handleBack = () => {
    openDrawerWithStep("select-probe-type");
  };

  const handleTrain = () => {
    if (fileList.length === 0) {
      message.error("Please upload a dataset file");
      return;
    }
    // Start training and move to training progress
    openDrawerWithStep("training-probe");
  };

  const uploadProps = {
    name: "file",
    multiple: false,
    fileList,
    beforeUpload: (file: any) => {
      const isValidType = file.type === "text/csv" || file.type === "application/json";
      if (!isValidType) {
        message.error("You can only upload CSV or JSON files!");
        return false;
      }
      setFileList([file]);
      return false; // Prevent auto upload
    },
    onRemove: () => {
      setFileList([]);
    },
  };

  const instructions = [
    "Ensure your dataset contains labeled examples for classification",
    "CSV files should have 'text' and 'label' columns",
    "JSON files should be an array of objects with 'text' and 'label' fields",
    "Include at least 100 examples per class for better accuracy",
    "Balanced datasets (equal examples per class) perform better",
  ];

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleTrain}
      backText="Back"
      nextText="Train"
      disableNext={fileList.length === 0}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Upload Dataset"
            description="Bud will train a custom classifier model based on your dataset with the best possible architecture to ensure best possible accuracy"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* File Upload Area */}
            <div className="mb-[2rem]">
              <Dragger
                {...uploadProps}
                className="bg-transparent border-[#757575] hover:border-[#965CDE]"
                style={{
                  background: "transparent",
                  minHeight: "190px",
                }}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined className="text-[3rem] text-[#757575]" />
                </p>
                <p className="ant-upload-text text-[#EEEEEE]">
                  Drop your files here
                </p>
                <p className="ant-upload-hint text-[#757575]">
                  (supports CSV, JSON files)
                </p>
              </Dragger>

              {fileList.length > 0 && (
                <div className="mt-[1rem] p-[0.75rem] bg-[#FFFFFF08] rounded-[6px] border border-[#1F1F1F]">
                  <Text_12_400_B3B3B3>
                    Selected file: {fileList[0].name}
                  </Text_12_400_B3B3B3>
                </div>
              )}
            </div>

            {/* Instructions Section */}
            <div>
              <Text_14_400_EEEEEE className="mb-[0.75rem]">
                Instructions
              </Text_14_400_EEEEEE>
              <div className="space-y-[0.5rem]">
                {instructions.map((instruction, index) => (
                  <div key={index} className="flex items-start gap-[0.5rem]">
                    <Text_12_400_757575>{index + 1}.</Text_12_400_757575>
                    <Text_12_400_757575 className="flex-1">
                      {instruction}
                    </Text_12_400_757575>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
