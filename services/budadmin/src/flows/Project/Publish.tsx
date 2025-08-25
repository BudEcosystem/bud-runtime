
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_757575, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE, Text_20_400_FFFFFF } from "@/components/ui/text";
import { Form, Image, Pagination, Spin } from "antd";
import React, { useEffect, useState } from "react";
import Tags from "../components/DrawerTags";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import TextInput from "../components/TextInput";
import CustomSelect from "../components/CustomSelect";
import { useRouter } from "next/router";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";


interface PricingHistoryItem {
  id: string;
  endpoint_id: string;
  input_cost: string;
  output_cost: string;
  currency: string;
  per_tokens: number;
  is_current: boolean;
  created_by: string;
  created_at: string;
  modified_at: string;
}

interface PricingHistoryResponse {
  object: string;
  message: string;
  page: number;
  limit: number;
  total_record: number;
  pricing_history: PricingHistoryItem[];
  total_pages: number;
}

const paginationStyle = `
  .custom-pagination .ant-pagination-item {
    background: #1a1a1a;
    border-color: #333333;
  }
  .custom-pagination .ant-pagination-item a {
    color: #EEEEEE;
  }
  .custom-pagination .ant-pagination-item-active {
    background: #4CAF50;
    border-color: #4CAF50;
  }
  .custom-pagination .ant-pagination-item-active a {
    color: #FFFFFF;
  }
  .custom-pagination .ant-pagination-prev .ant-pagination-item-link,
  .custom-pagination .ant-pagination-next .ant-pagination-item-link {
    background: #1a1a1a;
    border-color: #333333;
    color: #EEEEEE;
  }
  .custom-pagination .ant-pagination-options {
    color: #EEEEEE;
  }
  .custom-pagination .ant-select-selector {
    background: #1a1a1a !important;
    border-color: #333333 !important;
    color: #EEEEEE !important;
  }
  .custom-pagination .ant-select-arrow {
    color: #EEEEEE;
  }
`;

export default function Publish() {
  const { drawerProps, closeDrawer } = useDrawer()
  const { clusterDetails, getPricingHistory, publishEndpoint, getEndPoints } = useEndPoints();
  const [form] = Form.useForm();
  const [disableNext, setDisableNext] = useState(false);
  const [loading, setLoading] = useState(false);
  const [publishLoading, setPublishLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [pricingHistory, setPricingHistory] = useState<PricingHistoryItem[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const [pageSize, setPageSize] = useState(5);
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

    const hasErrors = form
      .getFieldsError()
      .some(({ errors }) => errors.length > 0);

    // Set button disabled state - note that per_tokens is handled via selectedTokenOption state
    setDisableNext(!allRequiredFieldsTouched || hasErrors || !selectedTokenOption);
  };

  const fetchPricingHistory = async (page: number = 1, limit: number = 5) => {
    if (drawerProps?.endpoint?.id) {
      try {
        setLoadingHistory(true);
        const response: PricingHistoryResponse = await getPricingHistory(
          drawerProps.endpoint.id,
          page,
          limit
        );
        if (response?.pricing_history) {
          setPricingHistory(response.pricing_history);
          setTotalRecords(response.total_record);
        }
      } catch (error) {
        console.error('Failed to fetch pricing history:', error);
      } finally {
        setLoadingHistory(false);
      }
    }
  };

  useEffect(() => {
    fetchPricingHistory(currentPage, pageSize);
  }, [drawerProps?.endpoint?.id, currentPage, pageSize]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handlePageChange = (page: number, pageSize?: number) => {
    setCurrentPage(page);
    if (pageSize) {
      setPageSize(pageSize);
    }
  };

  const tags = [
    {
      name: drawerProps?.endpoint?.model?.name || clusterDetails?.model?.name,
      color: '#D1B854'
    },
    {
      name: drawerProps?.endpoint?.cluster?.name || clusterDetails?.cluster?.name,
      color: '#D1B854'
    },
  ].filter(tag => tag.name); // Filter out tags with no name

  const handleSubmit = async () => {
    try {
      setLoading(true);

      if (drawerProps?.endpoint?.id && projectId) {
        await publishEndpoint(drawerProps.endpoint.id, { action: "unpublish" });
        // Refresh the endpoints list to update the is_published status
        getEndPoints({
          id: projectId as string,
          page: 1,
          limit: 1000,
        });
        closeDrawer();
      }
    } catch (error) {
      console.error('Failed to unpublish endpoint:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async () => {
    try {
      setPublishLoading(true);
      const values = await form.validateFields();

      if (drawerProps?.endpoint?.id && projectId) {
        await publishEndpoint(drawerProps.endpoint.id, {
          action: "publish",
          pricing: {
            input_cost: values.input_cost,
            output_cost: values.output_cost,
            currency: "USD",
            per_tokens: selectedTokenOption
          }
        });
        // Refresh the endpoints list to update the is_published status
        getEndPoints({
          id: projectId as string,
          page: 1,
          limit: 1000,
        });
        closeDrawer();
      }
    } catch (error) {
      console.error('Failed to publish endpoint:', error);
    } finally {
      setPublishLoading(false);
    }
  };

  return (
    <>
      <style>{paginationStyle}</style>
      <BudForm
      data={{}}
      onNext={handleSubmit}
      nextText="Un publish"
      onBack={() => {
        closeDrawer();
      }}
      backText="Close"
      disableNext={loading}
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
              {tags.length > 0 && (
                <div className="flex items-center justify-start gap-[.5rem] mt-[.3rem] flex-wrap	">
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
          <DrawerCard>
            <div className="pt-[.9rem]">
              <Text_20_400_FFFFFF className="tracking-[.03rem]">Price History</Text_20_400_FFFFFF>
              <Text_12_400_757575 className="tracking-[.004rem] mt-[.5rem]">Track the pricing changes over time</Text_12_400_757575>

              {loadingHistory ? (
                <div className="flex justify-center items-center py-8">
                  <Spin size="default" />
                </div>
              ) : pricingHistory.length > 0 ? (
                <div className="mt-6">
                  <div className="relative">
                    {/* Timeline line */}
                    <div className="absolute left-[10px] top-0 bottom-0 w-[2px] bg-[#333333]"></div>

                    {/* Timeline items */}
                    <div className="space-y-4">
                      {pricingHistory.map((item, index) => (
                        <div key={item.id} className="relative flex items-start">
                          {/* Timeline dot */}
                          <div className={`absolute left-0 w-[22px] h-[22px] rounded-full border-2 ${
                            item.is_current
                              ? 'bg-[#4CAF50] border-[#4CAF50]'
                              : 'bg-[#1a1a1a] border-[#555555]'
                          } flex items-center justify-center z-10`}>
                            {item.is_current && (
                              <div className="w-[8px] h-[8px] bg-white rounded-full"></div>
                            )}
                          </div>

                          {/* Content */}
                          <div className="ml-10 flex-1 bg-[#1a1a1a] rounded-lg p-4 border border-[#333333]">
                            <div className="flex justify-between items-start mb-2">
                              <div className="flex items-center gap-2">
                                <Text_12_600_EEEEEE>
                                  {formatDate(item.created_at)}
                                </Text_12_600_EEEEEE>
                                {item.is_current && (
                                  <span className="px-2 py-1 bg-[#4CAF50]/20 text-[#4CAF50] text-[10px] rounded">
                                    CURRENT
                                  </span>
                                )}
                              </div>
                            </div>

                            <div className="grid grid-cols-3 gap-4 mt-3">
                              <div>
                                <Text_12_400_757575>Input Cost</Text_12_400_757575>
                                <Text_14_400_EEEEEE className="mt-1">
                                  ${parseFloat(item.input_cost).toFixed(2)}
                                </Text_14_400_EEEEEE>
                              </div>
                              <div>
                                <Text_12_400_757575>Output Cost</Text_12_400_757575>
                                <Text_14_400_EEEEEE className="mt-1">
                                  ${parseFloat(item.output_cost).toFixed(2)}
                                </Text_14_400_EEEEEE>
                              </div>
                              <div>
                                <Text_12_400_757575>Per {item.per_tokens} Tokens</Text_12_400_757575>
                                <Text_14_400_EEEEEE className="mt-1">
                                  {item.currency}
                                </Text_14_400_EEEEEE>
                              </div>
                            </div>

                            {index === 0 && !item.is_current && (
                              <div className="mt-3 pt-3 border-t border-[#333333]">
                                <Text_12_400_757575>Modified at: {formatDate(item.modified_at)}</Text_12_400_757575>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Pagination */}
                  {totalRecords > pageSize && (
                    <div className="flex justify-center mt-6">
                      <Pagination
                        current={currentPage}
                        total={totalRecords}
                        pageSize={pageSize}
                        onChange={handlePageChange}
                        showSizeChanger
                        pageSizeOptions={['5', '10', '20']}
                        size="small"
                        className="custom-pagination"
                      />
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8">
                  <Text_12_400_757575>No pricing history available</Text_12_400_757575>
                </div>
              )}
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
                <div className="w-[41%]">
                  <CustomSelect
                    name="per_tokens"
                    label=""
                    placeholder="Select token count"
                    selectOptions={tokenOptions}
                    value={selectedTokenOption.toString()}
                    onChange={(value) => {
                      setSelectedTokenOption(Number(value));
                      // Trigger form validation
                      form.setFieldsValue({ per_tokens: value });
                      handleFieldsChange();
                    }}
                    ClassNames="mt-[.4rem]"
                  />
                </div>
              </div>
              <div className="flex justify-end items-start px-[1.4rem] pt-[0.85rem]">
                  <PrimaryButton
                    onClick={handlePublish}
                    disabled={disableNext || publishLoading}
                    loading={publishLoading}
                  >
                    Save
                  </PrimaryButton>
              </div>
            </Form>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
    </>
  );
}
