import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useCallback, useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "src/flows/components/TextInput";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import { useEvaluations } from "src/hooks/useEvaluations";
import { errorToast } from "@/components/toast";
import { Form, Select, ConfigProvider, Image, Spin } from "antd";
import { Text_12_300_EEEEEE } from "@/components/ui/text";
import CustomPopover from "src/flows/components/customPopover";

export default function NewEvaluation() {
  const { openDrawerWithStep, drawerProps } = useDrawer();
  const { form } = useContext(BudFormContext);
  const { createWorkflow, getExperiments, currentWorkflow } = useEvaluations();

  // Get experiment ID from drawer props - if provided, we don't show the experiment select
  const initialExperimentId = drawerProps?.experimentId as string;
  // Check if we need to show experiment selector (only when no experimentId is provided)
  const showExperimentSelect = drawerProps?.showExperimentSelect === true;
  // Get endpoint ID from drawer props - if provided, we skip the "Select Model" step
  const endpointId = drawerProps?.endpointId as string;

  // State for experiments select with pagination
  const [experiments, setExperiments] = useState<Array<{ id: string; name: string }>>([]);
  const [experimentsLoading, setExperimentsLoading] = useState(false);
  const [experimentsPage, setExperimentsPage] = useState(1);
  const [hasMoreExperiments, setHasMoreExperiments] = useState(true);
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | undefined>(initialExperimentId);
  const PAGE_SIZE = 10;

  // Fetch experiments with pagination - only when experiment select is shown
  const fetchExperiments = useCallback(async (page: number, append: boolean = false) => {
    if (experimentsLoading || !showExperimentSelect) return;

    setExperimentsLoading(true);
    try {
      const response = await getExperiments({ page, limit: PAGE_SIZE });
      const newExperiments = response?.experiments || [];
      const total = response?.total || 0;

      if (append) {
        setExperiments(prev => [...prev, ...newExperiments]);
      } else {
        setExperiments(newExperiments);
      }

      setHasMoreExperiments(page * PAGE_SIZE < total);
    } catch (error) {
      console.error("Failed to fetch experiments:", error);
    } finally {
      setExperimentsLoading(false);
    }
  }, [getExperiments, showExperimentSelect]);

  // Initial fetch - only when experiment select is shown
  useEffect(() => {
    if (showExperimentSelect) {
      fetchExperiments(1, false);
    }
  }, [showExperimentSelect]);

  // Handle scroll pagination
  const handleExperimentsScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement;
    const { scrollTop, scrollHeight, clientHeight } = target;

    // Load more when scrolled to bottom (with 50px threshold)
    if (scrollHeight - scrollTop - clientHeight < 50 && hasMoreExperiments && !experimentsLoading) {
      const nextPage = experimentsPage + 1;
      setExperimentsPage(nextPage);
      fetchExperiments(nextPage, true);
    }
  }, [hasMoreExperiments, experimentsLoading, experimentsPage, fetchExperiments]);

  // Handle experiment selection
  const handleExperimentChange = useCallback((value: string) => {
    setSelectedExperimentId(value);
    form.setFieldValue('ExperimentId', value);
  }, [form]);

  useEffect(() => {
    form.resetFields();
    // Set initial experiment ID if available
    if (initialExperimentId) {
      form.setFieldValue('ExperimentId', initialExperimentId);
      setSelectedExperimentId(initialExperimentId);
    }
  }, [form, initialExperimentId]);

  // Generate options for the select
  const experimentOptions = experiments.map(exp => ({
    label: exp.name,
    value: exp.id,
  }));

  return (
    <BudForm
      data={""}
      onNext={async (values) => {
        try {
          // Use selected experiment ID from form, state, or initial prop
          const experimentId = values.ExperimentId || selectedExperimentId || initialExperimentId;

          // Check if experimentId is available
          if (!experimentId) {
            errorToast(showExperimentSelect ? "Please select an experiment" : "Experiment ID not found");
            return;
          }

          // Prepare payload for step 1
          const step1Payload = {
            step_number: 1,
            stage_data: {
              name: values.EvaluationName,
              description: values.Description,
            },
          };

          // Call step 1 API
          const step1Response = await createWorkflow(experimentId, step1Payload);

          // If endpointId is provided (coming from modelEvaluations page), skip step 2 (Select Model)
          if (endpointId) {
            // Get workflow_id from the step 1 response or current workflow
            const workflowId = step1Response?.workflow_id || currentWorkflow?.workflow_id;

            if (!workflowId) {
              errorToast("Workflow not found. Please try again.");
              return;
            }

            // Prepare payload for step 2 with the provided endpoint_id
            const step2Payload = {
              step_number: 2,
              workflow_id: workflowId,
              stage_data: {
                endpoint_id: endpointId,
              },
            };

            // Call step 2 API automatically
            await createWorkflow(experimentId, step2Payload);

            // Navigate directly to step 3 (Select Traits), skipping step 2 (Select Model)
            openDrawerWithStep("select-traits");
          } else {
            // No endpointId provided, navigate to step 2 (Select Model) as usual
            openDrawerWithStep("select-model-new-evaluation");
          }
        } catch (error) {
          console.error("Failed to create evaluation workflow:", error);
          errorToast("Failed to create evaluation workflow");
        }
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={"New Evaluation"}
            description="Create a new evaluation to assess and measure your model's performance within this experiment"
          />
          <DrawerCard classNames="">
            <TextInput
              name="EvaluationName"
              label={"Evaluation Name"}
              placeholder={"Enter evaluation name"}
              rules={[
                { required: true, message: "Please enter evaluation name" },
              ]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[1.5rem]"
              infoText={"Enter evaluation name"}
            />

            {/* Experiment Select with Scroll Pagination - Only shown when triggered from modelEvaluations page */}
            {showExperimentSelect && (
              <Form.Item
                name="ExperimentId"
                rules={[{ required: true, message: "Please select an experiment" }]}
                className="mb-[1.5rem]"
                hasFeedback
              >
                <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]">
                  <div className="w-full">
                    <Text_12_300_EEEEEE className="absolute h-[3px] bg-[#0d0d0d] top-[0rem] left-[.75rem] px-[0.025rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap bg-[#0d0d0d] pl-[.35rem] pr-[.55rem]">
                      Experiment
                      <b className="text-[#FF4D4F]">*</b>
                      <CustomPopover title="Select the experiment to associate this evaluation with">
                        <Image
                          src="/images/info.png"
                          preview={false}
                          alt="info"
                          style={{ width: ".75rem", height: ".75rem" }}
                        />
                      </CustomPopover>
                    </Text_12_300_EEEEEE>
                  </div>
                  <div className="custom-select-two w-full rounded-[6px] relative">
                    <ConfigProvider
                      theme={{
                        token: {
                          colorTextPlaceholder: "#808080",
                        },
                      }}
                    >
                      <Select
                        placeholder="Select an experiment"
                        style={{
                          backgroundColor: "transparent",
                          color: "#EEEEEE",
                          border: "0.5px solid #757575",
                          width: "100%",
                        }}
                        size="large"
                        className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] outline-none"
                        options={experimentOptions}
                        value={selectedExperimentId}
                        onChange={handleExperimentChange}
                        onPopupScroll={handleExperimentsScroll}
                        loading={experimentsLoading}
                        notFoundContent={
                          experimentsLoading ? (
                            <div className="flex justify-center py-2">
                              <Spin size="small" />
                            </div>
                          ) : (
                            <span className="text-[#808080]">No experiments found</span>
                          )
                        }
                        dropdownRender={(menu) => (
                          <>
                            {menu}
                            {experimentsLoading && experiments.length > 0 && (
                              <div className="flex justify-center py-2">
                                <Spin size="small" />
                              </div>
                            )}
                          </>
                        )}
                        suffixIcon={
                          <Image
                            src="/images/icons/dropD.png"
                            preview={false}
                            alt="dropdown"
                            style={{ width: "auto", height: "auto" }}
                          />
                        }
                      />
                    </ConfigProvider>
                  </div>
                </div>
              </Form.Item>
            )}

            <TextAreaInput
              name="Description"
              label="Description"
              required
              info="Enter description"
              placeholder="Enter description"
              rules={[{ required: true, message: "Enter description" }]}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
