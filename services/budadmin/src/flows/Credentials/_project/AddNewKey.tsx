
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_300_EEEEEE } from "@/components/ui/text";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Input, Image, Form, Select, ConfigProvider } from "antd"; // Added Checkbox import
import CustomPopover from "src/flows/components/customPopover";
import { tempApiBaseUrl } from "@/components/environment";
import { axiosInstance } from "src/pages/api/requests";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useProjects } from "src/hooks/useProjects";
import { useCredentials } from "src/stores/useCredentials";

function AddKeyForm({ setDisableNext }) {
  const { form } = useContext(BudFormContext);
  const { setProjectCredentialsDetails, projectCredentialDetails } = useCredentials();
  const [options, setOptions] = useState([]);
  const [projectData, setProjectData] = useState<any>();
  const { projects, getProjects } = useProjects();
  async function fetchList(tagname) {
    await axiosInstance(`${tempApiBaseUrl}/models/tags?page=1&limit=1000`).then((result) => {
      const data = result.data?.tags?.map((result) => ({
        name: result.name,
        color: result.color,
      }));
      setOptions(data);
    });
  }

  useEffect(() => {
    fetchList("");
  }, []);
  useEffect(() => {
    getProjects(1, 100);
  }, []);

  useEffect(() => {
    const data = projects.map((item) => ({
      ...item,
      label: item?.['project'].name,
      value: item?.['project'].id,
    }));
    setProjectData(data)
  }, [projects]);


  return (
    <div className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
      <Form.Item hasFeedback
        name={"name"}
        rules={[
          { required: true, message: "Please input name!" },
        ]}
        className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
            Credential Name
            <CustomPopover title="This is the name" >
              <Image
                src="/images/info.png"
                preview={false}
                alt="info"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </CustomPopover>
          </Text_12_300_EEEEEE>
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
            form.validateFields(['name']);
            setProjectCredentialsDetails({
              ...projectCredentialDetails,
              name: e.target.value
            });
          }}
          className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
        />
      </Form.Item>
      <Form.Item hasFeedback
        rules={[{ required: true, message: "Please select project!" }]}
        name={"project"}
        className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
            Project
            {/* <span className="text-[red] text-[1rem]">*</span> */}
            <CustomPopover title="This is the project " >
              <Image
                src="/images/info.png"
                preview={false}
                alt="info"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
          <ConfigProvider
            theme={{
              token: {
                colorTextPlaceholder: '#808080',
              },
            }}
          >
            <Select
              placeholder="Select project"
              style={{
                backgroundColor: "transparent",
                color: "#EEEEEE",
                border: "0.5px solid #757575",
              }}
              size="large"
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] py-[1rem]"
              options={projectData}
              onChange={(value) => {
                form.setFieldsValue({ project: value });
                form.validateFields(['project']);
                setProjectCredentialsDetails({
                  ...projectCredentialDetails,
                  project: value
                });
              }}
            />
          </ConfigProvider>
        </div>
      </Form.Item>

      <Form.Item hasFeedback
        rules={[{ required: true, message: "Please select Set Expiry!" }]}
        name={"SetExpiry"}
        className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
            Set Expiry
            {/* <span className="text-[red] text-[1rem]">*</span> */}
            <CustomPopover title="This is the Set Expiry " >
              <Image
                src="/images/info.png"
                preview={false}
                alt="info"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
          <ConfigProvider
            theme={{
              token: {
                colorTextPlaceholder: '#808080',
              },
            }}
          >
            <Select
              placeholder="Select Expiry"
              style={{
                backgroundColor: "transparent",
                color: "#EEEEEE",
                border: "0.5px solid #757575",
              }}
              size="large"
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] py-[1rem]"
              options={[
                { label: "30 days", value: "30" },
                { label: "60 days", value: "60" },
              ]}
              onChange={(value) => {
                form.setFieldsValue({ SetExpiry: value });
                form.validateFields(['SetExpiry']);
                setProjectCredentialsDetails({
                  ...projectCredentialDetails,
                  SetExpiry: value
                });
              }}
            />
          </ConfigProvider>
        </div>
      </Form.Item>
      <Form.Item hasFeedback
        name={"SetMaxBudget"}
        rules={[
          { required: true, message: "Please input Max Budget!" },
          { min: 1, message: "Please enter a valid number" },
          { pattern: /^[0-9]*$/, message: "Please enter a valid number" },
        ]}
        className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
            Set Max Budget
            <CustomPopover title="This is the Set Max Budget" >
              <Image
                src="/images/info.png"
                preview={false}
                alt="info"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <Input
          type="number"
          placeholder="Enter Max Budget"
          style={{
            backgroundColor: "transparent",
            color: "#EEEEEE",
            border: "0.5px solid #757575",
          }}
          size="large"
          onChange={(e) => {
            form.setFieldsValue({ SetMaxBudget: e.target.value });
            form.validateFields(['SetMaxBudget']);
            setProjectCredentialsDetails({
              ...projectCredentialDetails,
              SetMaxBudget: e.target.value
            });
          }}
          className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem] px-[1rem]"
        />
      </Form.Item>
    </div>
  )
}

export default function AddNewKey() {
  const { openDrawerWithStep, closeDrawer } = useDrawer()
  const { setProjectCredentialsDetails, projectCredentialDetails, addProjectCredentials } = useCredentials();
  // const imageUrl = assetBaseUrl + (selectedProvider?.icon)
  const [disableNext, setDisableNext] = useState(true);
  const [loading, setLoading] = useState(false);

  return (
    <BudForm
      data={{

      }}
      disableNext={!projectCredentialDetails?.name ||!projectCredentialDetails?.project || !projectCredentialDetails?.SetExpiry || !projectCredentialDetails?.SetMaxBudget}
      onNext={async () => {
        try {
          const values = await projectCredentialDetails // Get form values
          setLoading(true);
          const payload = {
            name: values.name,
            project_id: values.project,
            expiry: values.SetExpiry,
            max_budget: values.SetMaxBudget,
            // model_budgets: {
            //   additionalProp1: 1,
            //   additionalProp2: 1,
            //   additionalProp3: 1
            // }
          };
          const response = await addProjectCredentials(payload);

          if (response?.success) {
            openDrawerWithStep("credentials-success")
          } else {
            console.error("Submission failed:", response);
          }
        } catch (error) {
          console.error("Error during form submission:", error);
        } finally {
          setLoading(false);
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
            title="New Key"
            description="Create New key here"
          />
          <div>
            <AddKeyForm setDisableNext={setDisableNext} />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
