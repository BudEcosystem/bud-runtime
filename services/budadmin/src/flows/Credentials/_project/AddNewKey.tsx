
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Form } from "antd";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useProjects } from "src/hooks/useProjects";
import { useCredentials } from "src/stores/useCredentials";
import TextInput from "src/flows/components/TextInput";
import CustomSelect from "src/flows/components/CustomSelect";

function AddKeyForm({ setDisableNext }) {
  const { form } = useContext(BudFormContext);
  const { setProjectCredentialsDetails, projectCredentialDetails } = useCredentials();
  const [projectData, setProjectData] = useState<any>();
  const { projects, getProjects } = useProjects();
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
      <TextInput
        name="name"
        label="Credential Name"
        placeholder="Enter name"
        infoText="This is the name"
        rules={[
          { required: true, message: "Please input name!" },
        ]}
        onChange={(value) => {
          form.setFieldsValue({ name: value });
          form.validateFields(['name']);
          setProjectCredentialsDetails({
            ...projectCredentialDetails,
            name: value
          });
        }}
        formItemClassnames="mb-0"
      />
      <Form.Item hasFeedback
        rules={[{ required: true, message: "Please select project!" }]}
        name={"project"}
        className={`mb-0`}
      >
        <CustomSelect
          name="project"
          label="Project"
          placeholder="Select project"
          info="This is the project"
          selectOptions={projectData}
          InputClasses="py-[.3rem]"
          rules={[{ required: true, message: "Please select project!" }]}
          onChange={(value) => {
            form.setFieldsValue({ project: value });
            form.validateFields(['project']);
            setProjectCredentialsDetails({
              ...projectCredentialDetails,
              project: value
            });
          }}
        />
      </Form.Item>

      <Form.Item hasFeedback
        rules={[{ required: true, message: "Please select Set Expiry!" }]}
        name={"SetExpiry"}
        className={`mb-0`}
      >
        <CustomSelect
          name="SetExpiry"
          label="Set Expiry"
          placeholder="Select Expiry"
          info="This is the Set Expiry"
          rules={[{ required: true, message: "Please select project!" }]}
          selectOptions={[
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
      </Form.Item>
      <TextInput
        name="SetMaxBudget"
        label="Set Max Budget"
        placeholder="Enter Max Budget"
        infoText="This is the Set Max Budget"
        allowOnlyNumbers={true}
        rules={[
          { required: true, message: "Please input Max Budget!" },
          { min: 1, message: "Please enter a valid number" },
          { pattern: /^[0-9]*$/, message: "Please enter a valid number" },
        ]}
        onChange={(value) => {
          form.setFieldsValue({ SetMaxBudget: value });
          form.validateFields(['SetMaxBudget']);
          setProjectCredentialsDetails({
            ...projectCredentialDetails,
            SetMaxBudget: value
          });
        }}
        formItemClassnames="mb-0"
      />
    </div>
  )
}

export default function AddNewKey() {
  const { openDrawerWithStep, closeDrawer } = useDrawer()
  const { projectCredentialDetails, addProjectCredentials } = useCredentials();

  return (
    <BudForm
      data={{

      }}
      disableNext={!projectCredentialDetails?.name ||!projectCredentialDetails?.project || !projectCredentialDetails?.SetExpiry || !projectCredentialDetails?.SetMaxBudget}
      onNext={async () => {
        try {
          const values = projectCredentialDetails // Get form values
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
            <AddKeyForm setDisableNext={() => {}} />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
