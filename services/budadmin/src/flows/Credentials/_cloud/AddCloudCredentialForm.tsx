import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { useCloudCredentials } from "src/stores/useCloudCredentials";
import { Form, Image, Input } from "antd";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import { useDrawer } from "src/hooks/useDrawer";
import { useEffect, useState } from "react";
import { Cog } from "lucide-react";
import { useCloudInfraProviders } from "src/hooks/useCloudInfraProviders";

export default function AddCloudCredentialForm() {
  const { selectedProvider, addCloudCredential } = useCloudCredentials();
  const { openDrawerWithStep } = useDrawer();
  const [disableNext, setDisableNext] = useState(true);
  const { refreshCloudCredentials } = useCloudInfraProviders();

  const [form] = Form.useForm();

  const handleFieldsChange = () => {
    const fieldsValue = form.getFieldsValue(true);
    const allFields = Object.keys(fieldsValue);

    const allTouched = allFields.every((field) => form.isFieldTouched(field));

    const hasErrors = form
      .getFieldsError()
      .some(({ errors }) => errors.length > 0);

    // Set button disabled state
    setDisableNext(!allTouched || hasErrors);
  };

  return (
    <BudForm
      data={{}}
      onNext={async () => {
        try {
          const values = await form.validateFields();
          const hasErrors = form
            .getFieldsError()
            .some(({ errors }) => errors.length > 0);

          // check for any errors
          if (hasErrors) {
            console.error("Form has errors");
            return;
          }

          // Extract credential_name from values
          const { credential_name, ...credentialValues } = values;

          const payload = {
            provider_id: selectedProvider.id,
            credential_name: credential_name,
            credential_values: {
              ...credentialValues,
            },
          };

          await addCloudCredential(payload);

          // Refresh
          await refreshCloudCredentials();
          openDrawerWithStep("cloud-credentials-success");
          // Go To Success Page

          // Send Request to API
          console.log(values);
        } catch (error) {
          console.error(error);
        }
      }}
      onBack={() => {
        openDrawerWithStep("add-new-cloud-provider");
      }}
      disableNext={disableNext}
      nextText="Save"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Provider Credentials"
            description={`Enter information below to add credentials to ${selectedProvider.name}`}
          />

          <div>
            <Form
              form={form}
              layout="vertical"
              validateTrigger="onBlur"
              // onFinish={handleSubmit}
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
                  Enter Credential Name
                </Text_14_400_EEEEEE>
              </div>
              <div className="px-[1.4rem] pb-[2rem]">
                <Form.Item
                  hasFeedback
                  name="credential_name"
                  rules={[
                    {
                      required: true,
                      message: "Please input a name for these credentials",
                    },
                  ]}
                  className="flex justify-between items-center w-full flex-row"
                >
                  <div className="w-full flex justify-between items-center gap-[.8rem] relative">
                    <div className="min-width-150">
                      <Text_12_400_B3B3B3 className="text-nowrap">
                        Credential Name
                      </Text_12_400_B3B3B3>
                    </div>

                    <Input
                      name="credential_name"
                      className="border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full pr-[1.5rem]"
                      placeholder="Enter a name for these credentials"
                      type="text"
                      required={true}
                      onChange={(e) =>
                        form.setFieldsValue({ credential_name: e.target.value })
                      }
                    />
                  </div>
                </Form.Item>
              </div>

              <div className="flex justify-between items-start px-[1.4rem] pt-[0.85rem] pb-[1.35rem]">
                <Text_14_400_EEEEEE className="pt-[.55rem]">
                  Enter Credential Details
                </Text_14_400_EEEEEE>
              </div>
              <div className="px-[1.4rem] flex justify-between items-center flex-wrap gap-[2rem] pb-[2rem]">
                {selectedProvider &&
                  selectedProvider.jsonSchema &&
                  selectedProvider.jsonSchema.properties &&
                  Object.keys(selectedProvider.jsonSchema.properties).map(
                    (key: string) => {
                      const property =
                        selectedProvider.jsonSchema.properties[key];
                      const rules = property.rules
                        ? property.rules.map((rule: any) => ({
                            validator: rule,
                          }))
                        : [];
                      return (
                        <Form.Item
                          hasFeedback
                          key={key}
                          name={key}
                          rules={[
                            {
                              required: true,
                              message: `Please input your ${property.label}`,
                            },
                          ]}
                          className="flex justify-between items-center w-full flex-row"
                        >
                          <div className="w-full flex justify-between items-center gap-[.8rem] relative">
                            <div className="min-width-150">
                              <Text_12_400_B3B3B3 className="text-nowrap">
                                {property.label}
                              </Text_12_400_B3B3B3>
                            </div>

                            <Input
                              name={key}
                              className="border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full pr-[1.5rem]"
                              placeholder={property.description}
                              type={
                                property.type === "password"
                                  ? "password"
                                  : "text"
                              }
                              required={property.required}
                              onChange={(e) =>
                                form.setFieldsValue({ [key]: e.target.value })
                              }
                              autoComplete="new-password"
                            />
                          </div>
                        </Form.Item>
                      );
                    },
                  )}
              </div>
            </Form>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
