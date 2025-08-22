import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "@/hooks/useDrawer";
import { TextInput, SelectInput } from "@/components/ui/input";
import { AppRequest } from "@/services/api/requests";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useProjects } from "@/hooks/useProjects";
import { errorToast } from "@/components/toast";

interface AddKeyFormProps {
  formData: {
    name: string;
    project_id: string;
    expiry: string;
  };
  setFormData: (data: any) => void;
}

function AddKeyForm({ formData, setFormData }: AddKeyFormProps) {
  const [projectOptions, setProjectOptions] = useState<any>([]);
  const { projects, getProjects } = useProjects();

  useEffect(() => {
    getProjects(1, 100);
  }, [getProjects]);

  useEffect(() => {
    // Map projects for SelectCustomInput - it needs the full object as value
    const data = projects.map((item) => ({
      label: item?.["project"].name,
      value: item?.["project"].id,
    }));
    setProjectOptions(data);
  }, [projects]);

  // Find the selected project object for display
  const selectedProject = projectOptions.find(
    (p: any) => p.value === formData.project_id,
  );

  // Expiry options
  const expiryOptions = [
    { label: "30 days", value: "30" },
    { label: "60 days", value: "60" },
    { label: "90 days", value: "90" },
    { label: "Never", value: "0" },
  ];

  return (
    <DrawerCard classNames="pb-0">
      <div className="pt-[.87rem]">
        {/* API Key Name Input */}
        <div className="mb-[1.7rem]">
          <Text_14_400_EEEEEE className="p-0 pt-[.3rem] m-0">
            API Key Name
          </Text_14_400_EEEEEE>
          <Text_12_400_757575 className="pt-[.35rem] leading-[1.05rem] mb-[0.5rem]">
            Enter a descriptive name for your API key
          </Text_12_400_757575>
          <TextInput
            placeholder="e.g., Production API Key"
            value={formData.name}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setFormData({ ...formData, name: e.target.value })
            }
            className="!max-w-full"
          />
        </div>

        {/* Project Selection */}
        <div className="mb-[1.7rem]">
          <Text_14_400_EEEEEE className="p-0 pt-[.3rem] m-0">
            Select Project
          </Text_14_400_EEEEEE>
          <Text_12_400_757575 className="pt-[.35rem] leading-[1.05rem] mb-[0.5rem]">
            Choose the project to associate with this API key
          </Text_12_400_757575>
          <SelectInput
            placeholder="Select a project"
            value={selectedProject}
            onValueChange={(item: any) =>
              setFormData({ ...formData, project_id: item.value })
            }
            selectItems={projectOptions}
            renderItem={(item: any) => item.label}
            className="!max-w-full"
            showSearch={true}
          />
        </div>

        {/* Expiry Selection */}
        <div className="mb-[1.7rem]">
          <Text_14_400_EEEEEE className="p-0 pt-[.3rem] m-0">
            Set Expiry
          </Text_14_400_EEEEEE>
          <Text_12_400_757575 className="pt-[.35rem] leading-[1.05rem] mb-[0.5rem]">
            Choose when this API key should expire
          </Text_12_400_757575>
          <SelectInput
            placeholder="Select expiry period"
            value={expiryOptions.find((e: any) => e.value === formData.expiry)}
            onValueChange={(item: any) =>
              setFormData({ ...formData, expiry: item.value })
            }
            selectItems={expiryOptions}
            renderItem={(item: any) => item.label}
            className="!max-w-full"
            showSearch={false}
          />
        </div>
      </div>
    </DrawerCard>
  );
}

export default function AddNewKey() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const [formData, setFormData] = useState<any>({
    name: "",
    project_id: "",
    expiry: "",
  });

  const isFormValid = formData.name && formData.project_id && formData.expiry;

  return (
    <BudForm
      data={formData}
      disableNext={!isFormValid}
      onNext={async () => {
        try {
          const payload = {
            name: formData.name,
            project_id: formData.project_id,
            expiry: formData.expiry,
            credential_type: "client_app",
          };

          const response = await AppRequest.Post("/credentials/", payload);

          if (response?.data) {
            // Store the API key for display in success screen
            localStorage.setItem(
              "temp_api_key",
              response.data.key || response.data.api_key || "",
            );
            openDrawerWithStep("api-key-success");
          } else {
            errorToast("Failed to create API key");
          }
        } catch (error: any) {
          console.error("Error during form submission:", error);
          errorToast(
            error?.response?.data?.message || "Failed to create API key",
          );
        } finally {
          // Handle loading state if needed
        }
      }}
      nextText="Create"
      backText="Cancel"
      onBack={() => {
        closeDrawer();
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="New API Key"
            description="Create a new API key for programmatic access"
          />
          <AddKeyForm formData={formData} setFormData={setFormData} />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
