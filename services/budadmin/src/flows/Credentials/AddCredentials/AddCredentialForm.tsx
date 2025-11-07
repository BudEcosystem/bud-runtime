import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import { Form, Image, Input } from "antd";
import React, { useContext, useEffect, useState } from "react";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { EyeOutlined, EyeInvisibleOutlined } from "@ant-design/icons";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { useProprietaryCredentials } from "src/stores/useProprietaryCredentials";

export default function AddCredentialForm() {
  const [loading, setLoading] = useState(false);
  const [showKey, setShowKey] = useState<any>({});
  const [form] = Form.useForm();
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const [search, setSearch] = React.useState("");
  const { openDrawerWithStep } = useDrawer();
  const { currentWorkflow, updateProvider } = useDeployModel();
  const {
    credentials,
    getCredentials,
    setSelectedCredential,
    selectedProvider,
    providerInfo,
    addproprietaryCredentials,
    createProprietaryCredentials,
  } = useProprietaryCredentials();
  const [disableNext, setDisableNext] = useState(true);

  const handleFieldsChange = () => {
    // Get all field values
    const fieldsValue = form.getFieldsValue(true);
    const allFields = Object.keys(fieldsValue); // Convert to an array of field names

    // Check if all fields have been touched
    const allTouched = allFields.every((field) => form.isFieldTouched(field));

    // Check if there are any validation errors
    const hasErrors = form
      .getFieldsError()
      .some(({ errors }) => errors.length > 0);

    // Set button disabled state
    setDisableNext(!allTouched || hasErrors);
  };
  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      const payload = { ...values };
      delete payload.name;

      Object.keys(payload).forEach((key) => {
        if (!payload[key]) {
          delete payload[key];
        }
      });

      const result = await createProprietaryCredentials(
        values.name,
        selectedProvider.type,
        payload,
      );

      // Only show success if credential was created successfully
      if (result) {
        openDrawerWithStep("credentials-success");
      }
    } catch (error) {
      console.error("Error creating credentials:", error);
    } finally {
      setLoading(false);
    }
  };
  return (
    <BudForm
      data={{}}
      onBack={() => {
        openDrawerWithStep("add-credentials-choose-provider");
      }}
      disableNext={disableNext}
      onNext={async () => {
        const values = await form.validateFields();
        handleSubmit(values);
        // try {
        //   const values = await form.validateFields(); // Get form values

        //   setLoading(true);
        //   let providers = values;
        //   const payload = {
        //     name: values.name,
        //     type: selectedProvider.type,
        //     // provider_id: "",
        //     other_provider_creds: { ...providers },
        //   };
        //   delete payload.other_provider_creds.name;
        //   const response = await addproprietaryCredentials(payload);

        //   if (response?.success) {
        //     openDrawerWithStep("credentials-success");
        //   } else {
        //     console.error("Submission failed:", response);
        //   }
        // } catch (error) {
        //   console.error("Error during form submission:", error);
        // } finally {
        //   setLoading(false);
        // }
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Credentials"
            description={`Enter information below to add credentials to ${selectedProvider.name}`}
          />
          <div>
            <Form
              className=""
              form={form}
              layout="vertical"
              validateTrigger="onBlur"
              onFieldsChange={handleFieldsChange}
              feedbackIcons={() => {
                return {
                  error: (
                    <Image
                      src="/icons/warning.svg"
                      alt="error"
                      width={"1rem"}
                      height={"1rem"}
                    />
                  ),
                  success: <div />,
                  warning: <div />,
                  "": <div />,
                };
              }}
            >
              <div className="flex justify-between items-start px-[1.4rem] pt-[0.85rem] pb-[1.35rem]">
                <Text_14_400_EEEEEE className="pt-[.55rem]">
                  Enter Credential Details
                </Text_14_400_EEEEEE>
              </div>
              <div className="px-[1.4rem] flex justify-between items-center flex-wrap gap-[2rem] pb-[2rem]">
                <Form.Item
                  hasFeedback
                  name="name"
                  rules={[
                    {
                      required: true,
                      message: "Please input your API key name",
                    },
                  ]}
                  className="flex justify-between items-center flex-row w-full"
                >
                  <div className="w-full flex justify-between items-center gap-[.8rem]">
                    <div className="min-width-150">
                      <Text_12_400_B3B3B3 className="text-nowrap">
                        API key name
                      </Text_12_400_B3B3B3>
                    </div>
                    <Input
                      name="name"
                      className="border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full"
                      placeholder="Enter API key name"
                      onChange={(e) =>
                        form.setFieldsValue({ name: e.target.value })
                      }
                    />
                  </div>
                </Form.Item>
                {providerInfo?.map((item, index) => (
                  <Form.Item
                    hasFeedback
                    key={index}
                    name={item.field}
                    rules={[
                      {
                        required: item.required,
                        message: `Please input your ${item.label}`,
                      },
                      item?.type === "email" && {
                        required: item.required,
                        type: "email",
                        message: "Please input a valid email",
                      },
                      item?.type === "url" && {
                        required: item.required,
                        type: "url",
                        message: "Please input a valid URL",
                      },
                    ]}
                    className="flex justify-between items-center w-full flex-row"
                  >
                    <div className="w-full flex justify-between items-center gap-[.8rem] relative">
                      <div className="min-width-150">
                        <Text_12_400_B3B3B3 className="text-nowrap">
                          {item.label}
                        </Text_12_400_B3B3B3>
                      </div>
                      <Input
                        name={item.field}
                        className="border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full pr-[1.5rem]"
                        placeholder={item.description}
                        type={
                          item.type === "password" && showKey?.[item.field]
                            ? "text"
                            : item.type
                        }
                        required={item.required}
                        onChange={(e) =>
                          form.setFieldsValue({ [item.field]: e.target.value })
                        }
                        autoComplete="new-password"
                      />
                      {item.type === "password" && (
                        <div
                          onClick={() =>
                            setShowKey({
                              ...showKey,
                              [item.field]: !showKey?.[item.field],
                            })
                          }
                          className="ml-[.5rem] absolute right-[.4rem] z-10 cursor-pointer"
                        >
                          {showKey?.[item.field] ? (
                            <EyeOutlined className="text-[#B3B3B3]" />
                          ) : (
                            <EyeInvisibleOutlined className="text-[#B3B3B3]" />
                          )}
                        </div>
                      )}
                    </div>
                  </Form.Item>
                ))}
              </div>
            </Form>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
