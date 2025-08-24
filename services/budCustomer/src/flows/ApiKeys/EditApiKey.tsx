import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "@/hooks/useDrawer";
import { Input, Form, Select, ConfigProvider } from "antd";
import { AppRequest } from "@/services/api/requests";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { successToast, errorToast } from "@/components/toast";
import ThemedLabel from "@/components/ui/bud/dataEntry/ThemedLabel";
import { useTheme } from "@/context/themeContext";

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

function EditApiKeyForm({ setDisableNext, form }: { setDisableNext: (value: boolean) => void; form: any }) {
  const [selectedApiKey, setSelectedApiKey] = useState<ApiKey | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [formData, setFormData] = useState({
    name: '',
    project_id: '',
    expiry: ''
  });

  // Fetch projects
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const response = await AppRequest.Get('/projects/');
        if (response?.data?.projects) {
          setProjects(response.data.projects);
        }
      } catch (error) {
        console.error('Failed to fetch projects:', error);
      }
    };
    fetchProjects();
  }, []);

  // Load selected API key data
  useEffect(() => {
    const storedKey = localStorage.getItem("selected_api_key");
    if (storedKey) {
      const keyData = JSON.parse(storedKey);
      setSelectedApiKey(keyData);
      setFormData({
        name: keyData.name || '',
        project_id: keyData.project?.id || '',
        expiry: keyData.expiry || ''
      });

      // Set form values
      form.setFieldsValue({
        name: keyData.name,
        project_id: keyData.project?.id,
        expiry: keyData.expiry
      });
    }
  }, [form]);

  // Validate form and enable/disable next button
  useEffect(() => {
    const isValid = formData.name.trim() !== '' && formData.project_id !== '';
    setDisableNext(!isValid);
  }, [formData, setDisableNext]);

  return (
    <div className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
      <Form.Item
        hasFeedback
        rules={[{ required: true, message: "Please enter API key name!" }]}
        name="name"
        className="flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
      >
        <div className="w-full">
          <ThemedLabel text="API Key Name" required />
        </div>
        <Input
          placeholder="Enter API key name"
          style={{
            backgroundColor: "transparent",
            color: "#EEEEEE",
            border: "0.5px solid #757575",
          }}
          size="large"
          defaultValue={selectedApiKey?.name}
          onChange={(e) => {
            const value = e.target.value;
            form.setFieldsValue({ name: value });
            form.validateFields(['name']);
            setFormData(prev => ({ ...prev, name: value }));
          }}
          className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem] px-[1rem] py-[1rem]"
        />
      </Form.Item>

      <Form.Item
        hasFeedback
        rules={[{ required: true, message: "Please select a project!" }]}
        name="project_id"
        className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]"
      >
        <div className="w-full">
          <ThemedLabel text="Project" required />
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
          <ConfigProvider
            theme={{
              token: {
                colorTextPlaceholder: '#808080',
                boxShadowSecondary: 'none',
              },
            }}
          >
            <Select
              variant="borderless"
              placeholder="Select Project"
              defaultValue={selectedApiKey?.project?.id}
              style={{
                backgroundColor: "transparent",
                color: "#EEEEEE",
                border: "0.5px solid #757575",
                width: "100%",
              }}
              size="large"
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
              options={projects.map(project => ({
                label: project.name,
                value: project.id
              }))}
              onChange={(value) => {
                form.setFieldsValue({ project_id: value });
                form.validateFields(['project_id']);
                setFormData(prev => ({ ...prev, project_id: value }));
              }}
            />
          </ConfigProvider>
        </div>
      </Form.Item>

      <Form.Item
        hasFeedback
        name="expiry"
        className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]"
      >
        <div className="w-full">
          <ThemedLabel text="Set Expiry" info="Set when this API key should expire" />
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
          <ConfigProvider
            theme={{
              token: {
                colorTextPlaceholder: '#808080',
                boxShadowSecondary: 'none',
              },
            }}
          >
            <Select
              variant="borderless"
              placeholder="Select Expiry"
              defaultValue={selectedApiKey?.expiry}
              style={{
                backgroundColor: "transparent",
                color: "#EEEEEE",
                border: "0.5px solid #757575",
                width: "100%",
              }}
              size="large"
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
              options={[
                { label: "Never", value: null },
                { label: "30 days", value: "30" },
                { label: "60 days", value: "60" },
                { label: "90 days", value: "90" },
              ]}
              onChange={(value) => {
                form.setFieldsValue({ expiry: value });
                form.validateFields(['expiry']);
                setFormData(prev => ({ ...prev, expiry: value || '' }));
              }}
            />
          </ConfigProvider>
        </div>
      </Form.Item>
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

          const response = await AppRequest.Put(`/credentials/${selectedApiKey?.id}`, payload);

          if (response?.status === 200 || response?.data) {
            successToast("API key updated successfully");
            closeDrawer();
          } else {
            errorToast("Failed to update API key");
          }
        } catch (error: any) {
          console.error("Error updating API key:", error);
          errorToast(error?.response?.data?.message || "Failed to update API key");
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
              <div className={`p-0 pt-[.4rem] m-0 text-[1rem] font-medium ${isLight ? "text-[#1a1a1a]" : "text-[#EEEEEE]"}`}>
                Edit API Key
              </div>
            </div>
            <div className={`pt-[.55rem] leading-[1.05rem] ${isLight ? "text-[#666666]" : "text-[#757575]"}`}>
              Update API key details
            </div>
          </div>
          <div>
            <EditApiKeyForm setDisableNext={setDisableNext} form={context.form} />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
