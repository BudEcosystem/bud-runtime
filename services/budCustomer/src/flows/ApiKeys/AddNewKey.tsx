import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "@/hooks/useDrawer";
import { Input, Form, Select, ConfigProvider } from "antd";
import { AppRequest } from "@/services/api/requests";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useProjects } from "@/hooks/useProjects";
import { errorToast } from "@/components/toast";
import ThemedLabel from "@/components/ui/bud/dataEntry/ThemedLabel";

function AddKeyForm({ setApiKeyData }: { setApiKeyData: (data: any) => void }) {
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
      <Form.Item
        hasFeedback
        name={"name"}
        rules={[{ required: true, message: "Please input name!" }]}
        className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <ThemedLabel text="Credential Name" info="This is the name" />
        </div>
        <Input
          placeholder="Enter name"
          style={{
            backgroundColor: "transparent",
            color: "#EEEEEE",
            border: "0.5px solid #757575",
          }}
          size="large"
          onChange={(e) => {
            form.setFieldsValue({ name: e.target.value });
            form.validateFields(["name"]);
            setApiKeyData((prev: any) => ({
              ...prev,
              name: e.target.value,
            }));
          }}
          className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
        />
      </Form.Item>
      <Form.Item
        hasFeedback
        rules={[{ required: true, message: "Please select project!" }]}
        name={"project"}
        className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <ThemedLabel text="Project" info="This is the project" />
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
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
              placeholder="Select project"
              style={{
                backgroundColor: "transparent",
                color: "#EEEEEE",
                border: "0.5px solid #757575",
                width: "100%",
              }}
              size="large"
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
              options={projectData}
              onChange={(value) => {
                form.setFieldsValue({ project: value });
                form.validateFields(["project"]);
                setApiKeyData((prev: any) => ({
                  ...prev,
                  project_id: value,
                }));
              }}
            />
          </ConfigProvider>
        </div>
      </Form.Item>

      <Form.Item
        hasFeedback
        rules={[{ required: true, message: "Please select Set Expiry!" }]}
        name={"SetExpiry"}
        className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <ThemedLabel text="Set Expiry" info="This is the Set Expiry" />
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
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
              placeholder="Select Expiry"
              style={{
                backgroundColor: "transparent",
                color: "#EEEEEE",
                border: "0.5px solid #757575",
                width: "100%",
              }}
              size="large"
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
              options={[
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
          </ConfigProvider>
        </div>
      </Form.Item>
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
            description="Create New key here"
          />
          <div>
            <AddKeyForm setApiKeyData={setApiKeyData} />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
