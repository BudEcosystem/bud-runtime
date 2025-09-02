import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_757575, Text_14_400_EEEEEE, Text_20_400_FFFFFF } from "@/components/ui/text";
import { Form, Image } from "antd";
import React, { useEffect, useState } from "react";
import Tags from "../components/DrawerTags";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import TextInput from "../components/TextInput";
import CustomSelect from "../components/CustomSelect";
import { useRouter } from "next/router";
import { errorToast, successToast } from "@/components/toast";

export default function PublishEndpoint() {
  const { drawerProps, closeDrawer } = useDrawer();
  const { publishEndpoint, getEndPoints } = useEndPoints();
  const [form] = Form.useForm();
  const [disableNext, setDisableNext] = useState(true);
  const [loading, setLoading] = useState(false);
  const [selectedTokenOption, setSelectedTokenOption] = useState<number>(1000);
  const router = useRouter();
  const { projectId } = router.query;

  const tokenOptions = [
    { value: 1000, label: '1K' },
    { value: 5000, label: '5K' },
    { value: 10000, label: '10K' },
    { value: 50000, label: '50K' },
    { value: 1000000, label: '1M' },
    { value: 10000000, label: '10M' }
  ];

  const handleFieldsChange = () => {
    const requiredFields = ['input_cost', 'output_cost'];
    const allRequiredFieldsTouched = requiredFields.every((field) => form.isFieldTouched(field));
    const hasErrors = form.getFieldsError().some(({ errors }) => errors.length > 0);
    setDisableNext(!allRequiredFieldsTouched || hasErrors || !selectedTokenOption);
  };

  const tags = [
    {
      name: drawerProps?.endpoint?.model?.name,
      color: '#D1B854'
    },
    {
      name: drawerProps?.endpoint?.cluster?.name,
      color: '#D1B854'
    },
  ].filter(tag => tag.name);

  const handlePublish = async () => {
    try {
      setLoading(true);
      const values = await form.validateFields();

      if (drawerProps?.endpoint?.id && projectId) {
        // Publish the endpoint with pricing data
        await publishEndpoint(drawerProps.endpoint.id, {
          action: "publish",
          pricing: {
            input_cost: parseFloat(values.input_cost),
            output_cost: parseFloat(values.output_cost),
            currency: "USD",
            per_tokens: selectedTokenOption
          }
        });

        // Refresh the endpoints list
        await getEndPoints({
          id: projectId as string,
          page: 1,
          limit: 1000,
        });

        successToast('Endpoint published successfully');
        closeDrawer();
      }
    } catch (error) {
      console.error('Failed to publish endpoint:', error);
      errorToast('Failed to publish endpoint');
    } finally {
      setLoading(false);
    }
  };

  return (
    <BudForm
      data={{}}
      onNext={handlePublish}
      nextText="Publish"
      onBack={() => {
        closeDrawer();
      }}
      backText="Cancel"
      disableNext={disableNext || loading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerCard>
            <div className="py-[.25rem]">
              <div className="flex justify-start items-center">
                <div className="text-[#EEEEEE] text-[1.125rem] leadign-[100%]">
                  {drawerProps?.endpoint?.name}
                </div>
              </div>
              {tags.length > 0 && (
                <div className="flex items-center justify-start gap-[.5rem] mt-[.3rem] flex-wrap">
                  {tags.map((item, index) => (
                    <Tags
                      key={index}
                      name={item.name}
                      color={item.color}
                    />
                  ))}
                </div>
              )}
            </div>
          </DrawerCard>
        </BudDrawerLayout>

        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Token Pricing"
            description={`Enter the token pricing below in USD to publish this endpoint`}
          />

          <div className="mb-[1rem]">
            <Form
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
                <Text_14_400_EEEEEE className="pt-[.55rem] whitespace-nowrap mr-4">
                  Input cost
                </Text_14_400_EEEEEE>
                <TextInput
                  name="input_cost"
                  placeholder="Input cost"
                  allowOnlyNumbers
                  rules={[
                    { required: true, message: "Enter input cost" },
                    {
                      validator: (_, value) => {
                        if (value && value.trim().length === 0) {
                          return Promise.reject("Input cost cannot be only whitespace");
                        }
                        return Promise.resolve();
                      }
                    }
                  ]}
                  ClassNames="mt-[.4rem] w-full"
                  InputClasses="py-[.5rem]"
                />
              </div>
              <div className="flex justify-between items-start px-[1.4rem] pt-[0.85rem] pb-[1.35rem]">
                <Text_14_400_EEEEEE className="pt-[.55rem] whitespace-nowrap mr-4">
                  Output Cost
                </Text_14_400_EEEEEE>
                <TextInput
                  name="output_cost"
                  placeholder="Output cost"
                  allowOnlyNumbers
                  rules={[
                    { required: true, message: "Enter output cost" },
                    {
                      validator: (_, value) => {
                        if (value && value.trim().length === 0) {
                          return Promise.reject("Output cost cannot be only whitespace");
                        }
                        return Promise.resolve();
                      }
                    }
                  ]}
                  ClassNames="mt-[.4rem] w-full"
                  InputClasses="py-[.5rem]"
                />
              </div>
              <div className="flex justify-between items-start px-[1.4rem] pt-[0.85rem] pb-[1.35rem]">
                <Text_14_400_EEEEEE className="pt-[.55rem]">
                  Price per token
                </Text_14_400_EEEEEE>
                <div className="w-[41%]">
                  <CustomSelect
                    name="per_tokens"
                    label=""
                    placeholder="Select token count"
                    selectOptions={tokenOptions}
                    value={selectedTokenOption.toString()}
                    onChange={(value) => {
                      setSelectedTokenOption(Number(value));
                      form.setFieldsValue({ per_tokens: value });
                      handleFieldsChange();
                    }}
                    ClassNames="mt-[.4rem]"
                  />
                </div>
              </div>
            </Form>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
