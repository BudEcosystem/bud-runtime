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
import { Form } from "antd";

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
  const { projects, getProjects } = useProjects();

  // Initialize formValues from localStorage on mount
  const getInitialFormValues = () => {
    const storedKey = localStorage.getItem("selected_api_key");
    if (storedKey) {
      const keyData = JSON.parse(storedKey);
      return {
        name: keyData.name || "",
        project_id: keyData.project?.id || "",
        expiry: keyData.expiry || "",
      };
    }
    return {
      name: "",
      project_id: "",
      expiry: "",
    };
  };

  const [formValues, setFormValues] = useState(getInitialFormValues());

  // Fetch projects using the hook
  useEffect(() => {
    getProjects(1, 100);
  }, [getProjects]);

  // Transform projects data to match the format needed for CustomSelect
  useEffect(() => {
    if (projects && projects.length > 0) {
      const data = projects.map((item) => ({
        ...item,
        label: item?.["project"].name,
        value: item?.["project"].id,
      }));
      setProjectData(data);
    }
  }, [projects]);
  useEffect(() => {
    console.log("formValues", formValues)
  }, [formValues]);

  // Re-initialize form values when component mounts and form is ready
  useEffect(() => {
    const storedKey = localStorage.getItem("selected_api_key");
    if (storedKey && form && form.setFieldsValue && projectData.length > 0) {
      const keyData = JSON.parse(storedKey);
      const initialFormValues = {
        name: keyData.name || "",
        project_id: keyData.project?.id || "",
        expiry: keyData.expiry || "",
      };
      // Note: Could check if the project exists in projectData if needed
      // const projectExists = projectData.some((p: any) => p.value === initialFormValues.project_id);
      // Set state immediately
      setFormValues(initialFormValues);

      // Try multiple times to ensure fields are registered
      let attempts = 0;
      const trySetValues = () => {
        attempts++;
        // Set individual field values
        if (initialFormValues.name) {
          form.setFieldValue("name", initialFormValues.name);
        }
        if (initialFormValues.project_id) {
          form.setFieldValue("project_id", initialFormValues.project_id);
        }
        if (initialFormValues.expiry) {
          form.setFieldValue("expiry", initialFormValues.expiry);
        }

        // Check what was actually set
        const currentValues = form.getFieldsValue();
        // If not all fields are set and we haven't tried too many times, try again
        if ((!currentValues.project_id || !currentValues.name) && attempts < 5) {
          setTimeout(trySetValues, 200);
        } else {
          // Validate after setting values
          const isValid = currentValues.name?.trim() && currentValues.project_id;
          setDisableNext(!isValid);
        }
      };

      // Start trying to set values
      trySetValues();
    }
  }, [form, setDisableNext, projectData]);

  // Watch form values to enable/disable next button
  const validateForm = () => {
    const values = form.getFieldsValue();
    const isValid = values.name?.trim() && values.project_id;
    setDisableNext(!isValid);
  };

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
        value={formValues?.name}
        onChange={(value) => {
          setFormValues(prev => ({ ...prev, name: value }));
          form.setFieldValue("name", value);
          validateForm();
        }}
      />

      <Form.Item
        name="project_id"
        rules={[{ required: true, message: "Please select a project!" }]}
        hasFeedback
      >
        <CustomSelect
          name="project_id"
          label="Project"
          info="Select the project for this API key"
          placeholder="Select Project"
          value={projects.find(item => item.project.id === formValues?.project_id)?.project?.name || undefined}
          selectOptions={projectData}
          onChange={(value) => {
            setFormValues(prev => ({ ...prev, project_id: value }));
            form.setFieldValue("project_id", value);
            validateForm();
          }}
        />
      </Form.Item>

      <CustomSelect
        name="expiry"
        label="Set Expiry"
        info="Set when this API key should expire"
        placeholder="Select Expiry"
        value={formValues?.expiry || undefined}
        selectOptions={[
          { label: "Never", value: "0" },
          { label: "30 days", value: "30" },
          { label: "60 days", value: "60" },
          { label: "90 days", value: "90" },
        ]}
        onChange={(value) => {
          setFormValues(prev => ({ ...prev, expiry: value }));
          form.setFieldValue("expiry", value);
          validateForm();
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
  const [initialData, setInitialData] = useState<any>(null);
  const [isDataLoaded, setIsDataLoaded] = useState(false);

  const isLight = effectiveTheme === "light";

  useEffect(() => {
    const storedKey = localStorage.getItem("selected_api_key");
    if (storedKey) {
      const keyData = JSON.parse(storedKey);
      setSelectedApiKey(keyData);
      // Set initial data for the form
      const initialFormData = {
        name: keyData.name || "",
        project_id: keyData.project?.id || "",
        expiry: keyData.expiry || "",
      };
      setInitialData(initialFormData);
      setIsDataLoaded(true);
    } else {
      // No data found, but still mark as loaded
      setIsDataLoaded(true);
      setInitialData({});
    }
  }, []);

  // Don't render the form until data is loaded
  if (!isDataLoaded) {
    return <div>Loading...</div>;
  }

  return (
    <BudForm
      data={initialData}
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
