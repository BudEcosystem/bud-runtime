import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "@/hooks/useDrawer";
import { AppRequest } from "@/services/api/requests";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useProjects } from "@/hooks/useProjects";
import { errorToast } from "@/components/toast";
import TextInput from "@/components/ui/bud/dataEntry/TextInput";
import CustomSelect from "@/components/ui/bud/dataEntry/CustomSelect";

function AddKeyForm({ setApiKeyData, apiKeyData }: { setApiKeyData: (data: any) => void; apiKeyData: any }) {
  const { form } = useContext(BudFormContext);
  const [projectData, setProjectData] = useState<any>([]);
  const { projects, getProjects } = useProjects();

  useEffect(() => {
    getProjects(1, 100);
  }, [getProjects]);

  useEffect(() => {
    const data = projects.map((item) => ({
      ...item,
      label: item?.["project"].name,
      value: item?.["project"].id,
    }));
    setProjectData(data);
  }, [projects]);

  return (
    <div className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
      <TextInput
        name="name"
        label="Credential Name"
        placeholder="Enter name"
        infoText="This is the name"
        rules={[{ required: true, message: "Please input name!" }]}
        ClassNames="mt-[.1rem] mb-[0rem]"
        InputClasses="py-[.5rem]"
        formItemClassnames="mb-[0]"
        onChange={(value) => {
          form.setFieldsValue({ name: value });
          form.validateFields(["name"]);
          setApiKeyData((prev: any) => ({
            ...prev,
            name: value,
          }));
        }}
      />
      <CustomSelect
        name="project"
        label="Project"
        info="This is the project"
        placeholder="Select project"
        value={apiKeyData.project_id}
        selectOptions={projectData}
        onChange={(value) => {
          form.setFieldsValue({ project: value });
          form.validateFields(["project"]);
          setApiKeyData((prev: any) => ({
            ...prev,
            project_id: value,
          }));
        }}
      />
      <CustomSelect
        name="SetExpiry"
        label="Set Expiry"
        info="This is the Set Expiry"
        placeholder="Select Expiry"
        value={apiKeyData.expiry}
        selectOptions={[
          { label: "30 days", value: "30" },
          { label: "60 days", value: "60" },
          { label: "90 days", value: "90" },
          { label: "Never", value: "0" },
        ]}
        onChange={(value) => {
          form.setFieldsValue({ SetExpiry: value });
          form.validateFields(["SetExpiry"]);
          setApiKeyData((prev: any) => ({
            ...prev,
            expiry: value,
          }));
        }}
      />
    </div>
  );
}

export default function AddNewKey() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const [apiKeyData, setApiKeyData] = useState<any>({
    name: "",
    project_id: "",
    expiry: "",
  });

  const handleSubmit = async (values: any) => {
    try {
      const payload = {
        name: apiKeyData.name || values.name,
        project_id: apiKeyData.project_id || values.project,
        expiry: apiKeyData.expiry || values.SetExpiry,
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
        error?.response?.data?.detail || error?.response?.data?.message || "Failed to create API key",
      );
    } finally {
      // Handle loading state if needed
    }
  };

  return (
    <BudForm
      data={{}}
      disableNext={!apiKeyData.name || !apiKeyData.project_id || !apiKeyData.expiry}
      onNext={handleSubmit}
      nextText="Create"
      backText="Cancel"
      onBack={() => {
        closeDrawer();
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="New Key"
            description="Generate secure API credentials for accessing your project resources"
          />
          <div>
            <AddKeyForm setApiKeyData={setApiKeyData} apiKeyData={apiKeyData} />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
