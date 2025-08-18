
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_757575, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE, Text_20_400_FFFFFF } from "@/components/ui/text";
import { Form, Image } from "antd";
import React, { useEffect, useState } from "react";
import Tags from "../components/DrawerTags";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import TextInput from "../components/TextInput";
import { useRouter } from "next/router";


export default function Publish() {
  const { drawerProps, closeDrawer } = useDrawer()
  const { clusterDetails, getPricingHistory, updateTokenPricing } = useEndPoints();
  const [form] = Form.useForm();
  const [disableNext, setDisableNext] = useState(true);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { projectId } = router.query;

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

  useEffect(() => {
    const fetchPricingHistory = async () => {
      if (drawerProps?.endpoint?.id) {
        try {
          const data = await getPricingHistory(drawerProps.endpoint.id);
        } catch (error) {
          console.error('Failed to fetch pricing history:', error);
        }
      }
    };

    fetchPricingHistory();
  }, [drawerProps?.endpoint?.id, getPricingHistory]);

  const tags = [
    {
      name: drawerProps?.endpoint?.model?.name || drawerProps?.name || clusterDetails?.model?.name,
      color: '#D1B854'
    },
    {
      name: drawerProps?.endpoint?.cluster?.name || drawerProps?.name || clusterDetails?.cluster?.name,
      color: '#D1B854'
    },
  ];

  const handleSubmit = async () => {
    try {
      setLoading(true);
      const values = await form.validateFields();

      if (drawerProps?.endpoint?.id) {
        await updateTokenPricing(drawerProps.endpoint.id, values, projectId as string);
        closeDrawer();
      }
    } catch (error) {
      console.error('Failed to update token pricing:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <BudForm
      data={{}}
      onNext={handleSubmit}
      nextText="Publish"
      onBack={() => {
        closeDrawer();
      }}
      backText="Close"
      disableNext={disableNext || loading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerCard>
            <div className="py-[.25rem]">
              <div className="flex justify-start items-center">
                <div className="text-[#EEEEEE] text-[1.125rem] leadign-[100%]">
                  {drawerProps?.endpoint?.name || drawerProps?.name || clusterDetails?.name}
                </div>
              </div>
              <div className="flex items-center justify-start gap-[.5rem] mt-[.3rem] flex-wrap	">
                {tags.map((item, index) => (
                  <Tags
                    key={index}
                    name={item.name}
                    color={item.color}
                  />
                ))}
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerCard>
            <div className="pt-[.9rem]">
              <Text_20_400_FFFFFF className="tracking-[.03rem]">Price History</Text_20_400_FFFFFF>
              <Text_12_400_757575 className="tracking-[.004rem] mt-[1rem]">Copy the code below and use it for deployment</Text_12_400_757575>
            </div>

          </DrawerCard>
        </BudDrawerLayout>

        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Token Pricing"
            description={`Enter the token pricing below in USD`}
          />

          <div className="mb-[1rem]">
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
                <Text_14_400_EEEEEE className="pt-[.55rem]">
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
                <TextInput
                  name="per_tokens"
                  placeholder="Price per token"
                  allowOnlyNumbers
                  rules={[
                    { required: true, message: "Enter price per token" },
                    {
                      validator: (_, value) => {
                        if (value && value.trim().length === 0) {
                          return Promise.reject("Price per token cannot be only whitespace");
                        }
                        return Promise.resolve();
                      }
                    }
                  ]}
                  ClassNames="mt-[.4rem] w-full"
                  InputClasses="py-[.5rem]"
                />
              </div>
            </Form>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
