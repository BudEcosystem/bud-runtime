import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "@/hooks/useDrawer";
import { AppRequest } from "@/services/api/requests";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { successToast, errorToast } from "@/components/toast";
import { useTheme } from "@/context/themeContext";
import TextInput from "@/components/ui/bud/dataEntry/TextInput";
import CustomSelect from "@/components/ui/bud/dataEntry/CustomSelect";
import { useProjects } from "@/hooks/useProjects";

interface ApiKey {
  id: string;
  name: string;
  project: {
    id: string;
    name: string;
  };
  expiry: string;
  created_at: string;
  last_used_at: string;
  is_active: boolean;
  status: "active" | "revoked" | "expired";
}

interface Project {
  id: string;
  name: string;
}

function EditApiKeyForm({
  setDisableNext,
  form,
}: {
  setDisableNext: (value: boolean) => void;
  form: any;
}) {
  const [projectData, setProjectData] = useState<any>([]);
  const [KeyData, setKeyData] = useState<any>();
  const { projects, getProjects } = useProjects();
  const [formData, setFormData] = useState({
    name: "",
    project_id: "",
    expiry: "",
  });
  const [isInitialized, setIsInitialized] = useState(false);

  // Fetch projects using the hook
  useEffect(() => {
    getProjects(1, 100);
  }, [getProjects]);

  // Transform projects data to match the format needed for CustomSelect
  useEffect(() => {
    if (projects && projects.length > 0) {
      console.log("Raw projects from useProjects:", projects);
      // Match the exact pattern from AddNewKey.tsx
      const data = projects.map((item) => ({
        ...item,
        label: item?.["project"].name,
        value: item?.["project"].id,
      }));
      console.log("Transformed project data for select options:", data);
      setProjectData(data);
    }
  }, [projects]);

  // Load selected API key data - wait for projects to be loaded
  useEffect(() => {
    const storedKey = localStorage.getItem("selected_api_key");
    if (storedKey && !isInitialized && projectData.length > 0) {
      const keyData = JSON.parse(storedKey);
      setKeyData(keyData);
      console.log("=== EditApiKey Form Initialization ===");
      console.log("Loaded API key data:", keyData);
      const projectId = keyData.project?.id || "";
      const matchingProject = projectData.find((p: any) => p.value === projectId);

      const initialData = {
        name: keyData.name || "",
        project_id: projectId,
        expiry: keyData.expiry || "",
      };

      console.log("Setting formData to:", initialData);
      setFormData(initialData);

      // Set form values - this is crucial for Form.Item to display the values
      form.setFieldsValue({
        name: keyData.name,
        project_id: projectId,
        expiry: keyData.expiry,
      });

      setIsInitialized(true);
    }
  }, [form, isInitialized, projectData]);

  // Validate form and enable/disable next button
  useEffect(() => {
    const isValid = formData.name.trim() !== "" && formData.project_id !== "";
    setDisableNext(!isValid);
  }, [formData, setDisableNext]);

  return (
    <div className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
      <TextInput
        name="name"
        label="API Key Name"
        placeholder="Enter API key name"
        infoText="Name for your API key"
        rules={[{ required: true, message: "Please enter API key name!" }]}
        ClassNames="mt-[.1rem] mb-[0rem]"
        InputClasses="py-[.5rem]"
        formItemClassnames="mb-[0]"
        value={formData?.name}
        onChange={(value) => {
          form.setFieldsValue({ name: value });
          form.validateFields(["name"]);
          setFormData((prev) => ({ ...prev, name: value }));
        }}
      />

      <CustomSelect
        name="project_id"
        label="Project"
        info="Select the project for this API key"
        placeholder="Select Project"
        value={KeyData?.project?.name || undefined}
        selectOptions={projectData}
        rules={[{ required: true, message: "Please select a project!" }]}
        onChange={(value) => {
          form.setFieldsValue({ project_id: value });
          form.validateFields(["project_id"]);
          setFormData((prev) => ({ ...prev, project_id: value }));
        }}
      />

      <CustomSelect
        name="expiry"
        label="Set Expiry"
        info="Set when this API key should expire"
        placeholder="Select Expiry"
        value={formData.expiry || undefined}
        selectOptions={[
          { label: "Never", value: "0" },
          { label: "30 days", value: "30" },
          { label: "60 days", value: "60" },
          { label: "90 days", value: "90" },
        ]}
        onChange={(value) => {
          form.setFieldsValue({ expiry: value });
          form.validateFields(["expiry"]);
          setFormData((prev) => ({ ...prev, expiry: value || "" }));
        }}
      />
    </div>
  );
}

export default function EditApiKey() {
  const { closeDrawer } = useDrawer();
  const context = useContext(BudFormContext);
  const { effectiveTheme } = useTheme();
  const [selectedApiKey, setSelectedApiKey] = useState<ApiKey | null>(null);
  const [disableNext, setDisableNext] = useState(true);
  const [loading, setLoading] = useState(false);

  const isLight = effectiveTheme === "light";

  useEffect(() => {
    const storedKey = localStorage.getItem("selected_api_key");
    if (storedKey) {
      const keyData = JSON.parse(storedKey);
      setSelectedApiKey(keyData);
    }
  }, []);

  return (
    <BudForm
      data={{}}
      onNext={async () => {
        try {
          const values = await context.form?.validateFields();
          setLoading(true);

          const payload = {
            name: values.name,
            project_id: values.project_id,
            expiry: values.expiry || null,
          };

          const response = await AppRequest.Put(
            `/credentials/${selectedApiKey?.id}`,
            payload,
          );

          if (response?.status === 200 || response?.data) {
            successToast("API key updated successfully");
            closeDrawer();
          } else {
            errorToast("Failed to update API key");
          }
        } catch (error: any) {
          console.error("Error updating API key:", error);
          errorToast(
            error?.response?.data?.message || "Failed to update API key",
          );
        } finally {
          setLoading(false);
        }
      }}
      nextText={loading ? "Updating..." : "Update"}
      backText="Cancel"
      onBack={() => {
        closeDrawer();
      }}
      disableNext={disableNext}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="px-[1.4rem] pb-[.9rem] rounded-ss-lg rounded-se-lg pt-[1.1rem] border-b-[.5px] border-b-[#1F1F1F]">
            <div className="flex justify-between align-center">
              <div
                className={`p-0 pt-[.4rem] m-0 text-[1rem] font-medium ${isLight ? "text-[#1a1a1a]" : "text-[#EEEEEE]"}`}
              >
                Edit API Key
              </div>
            </div>
            <div
              className={`pt-[.55rem] leading-[1.05rem] ${isLight ? "text-[#666666]" : "text-[#757575]"}`}
            >
              Update API key details
            </div>
          </div>
          <div>
            <EditApiKeyForm
              setDisableNext={setDisableNext}
              form={context.form}
            />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
