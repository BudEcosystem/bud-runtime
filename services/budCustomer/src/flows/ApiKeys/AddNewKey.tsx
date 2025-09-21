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

function AddKeyForm({
  setApiKeyData,
  apiKeyData,
}: {
  setApiKeyData: (data: any) => void;
  apiKeyData: any;
}) {
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
        rules={[
          { required: true, message: "Please input name!" },
          {
            validator: (_, value) => {
              if (value && value.trim().length === 0) {
                return Promise.reject(new Error("Name cannot be only spaces"));
              }
              return Promise.resolve();
            },
          },
        ]}
        ClassNames="mt-[.1rem] mb-[0rem]"
        InputClasses="py-[.5rem]"
        formItemClassnames="mb-[0]"
        onChange={(value) => {
          form.setFieldsValue({ name: value });
          form.validateFields(["name"]);
          setApiKeyData((prev: any) => ({
            ...prev,
            name: value ? value.trim() : "",
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
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (values: any) => {
    // Prevent double submission
    if (isSubmitting) {
      console.log("Submission already in progress, ignoring click");
      return;
    }

    // Validate required fields before proceeding
    const payload = {
      name: (apiKeyData.name || values.name || "").trim(),
      project_id: apiKeyData.project_id || values.project,
      expiry: apiKeyData.expiry || values.SetExpiry,
      credential_type: "client_app",
    };

    if (!payload.name || !payload.project_id || !payload.expiry) {
      errorToast("Please fill in all required fields");
      return;
    }

    setIsSubmitting(true);
    try {

      const response = await AppRequest.Post("/credentials/", payload);

      console.log("API Response:", response);
      console.log("Response status:", response?.status);
      console.log("Response data:", response?.data);

      // Check for successful response (2xx status codes)
      if (response && response.status >= 200 && response.status < 300) {
        // Store the API key for display in success screen
        // Handle different possible response structures
        const apiKey =
          response.data?.key ||
          response.data?.api_key ||
          response.data?.credential?.key ||
          response.data?.credential?.api_key ||
          "";

        if (apiKey) {
          localStorage.setItem("temp_api_key", apiKey);
          openDrawerWithStep("api-key-success");
        } else {
          // Success response but no API key in response
          console.warn(
            "API key created but key not found in response:",
            response.data,
          );
          // Still navigate to success screen as the creation was successful
          localStorage.setItem("temp_api_key", "");
          openDrawerWithStep("api-key-success");
        }
      } else {
        // If response exists but not a success status
        errorToast("Failed to create API key. Please try again.");
      }
    } catch (error: any) {
      console.error("Error during form submission:", error);

      // Check specifically for 500 errors
      if (error?.response?.status === 500) {
        errorToast("Server error occurred. Please try again later.");
      } else {
        errorToast(
          error?.response?.data?.detail ||
            error?.response?.data?.message ||
            "Failed to create API key. Please try again.",
        );
      }
      // Ensure we don't navigate to success screen on error
      return;
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <BudForm
      data={{}}
      disableNext={
        !apiKeyData.name ||
        !apiKeyData.project_id ||
        !apiKeyData.expiry ||
        isSubmitting
      }
      onNext={handleSubmit}
      nextText={isSubmitting ? "Creating..." : "Create"}
      backText="Cancel"
      onBack={() => {
        closeDrawer();
      }}
      drawerLoading={isSubmitting}
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
