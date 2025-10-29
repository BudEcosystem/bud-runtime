import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useEvaluations } from "src/hooks/useEvaluations";
import { Text_14_400_EEEEEE, Text_14_600_EEEEEE } from "@/components/ui/text";
import EvaluationList, { Evaluation } from "src/flows/components/AvailableEvaluations";
import { successToast, errorToast } from "@/components/toast";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { SpecificationTableItem, SpecificationTableItemProps } from "src/flows/components/SpecificationTableItem";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import IconRender from "src/flows/components/BudIconRender";
import ModelTags from "src/flows/components/ModelTags";
import { Model } from "src/hooks/useModels";


export default function EvaluationSummary() {
  const { getWorkflowData, workflowData, currentWorkflow, createWorkflow } = useEvaluations();
  const [isLoadingData, setIsLoadingData] = React.useState(true);
  const [evaluations, setEvaluations] = React.useState<Evaluation[]>([]);
  const [selectedModelData, setSelectedModelData] = React.useState<Model | null>(null);
  const [deploymentSpecs, setDeploymentSpecs] = React.useState<SpecificationTableItemProps[]>([]);
  const [selectedEvaluation, setSelectedEvaluation] = React.useState<Evaluation | null>(null);
  const { openDrawerWithStep, drawerProps } = useDrawer();
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  // Use existing workflowData if available, otherwise fetch it
  React.useEffect(() => {
    const initializeData = async () => {
      try {
        setIsLoadingData(true);

        let data = workflowData || currentWorkflow;

        // Only fetch if we don't have workflowData already
        if (!data && currentWorkflow?.experiment_id && currentWorkflow?.workflow_id) {
          data = await getWorkflowData(
            currentWorkflow.experiment_id,
            currentWorkflow.workflow_id
          );
        }

        // Extract data from workflow response
        console.log("data",data)

        if (data) {
          // Check for model in workflow_steps.model first (prioritize currentWorkflow)
          if (currentWorkflow?.workflow_steps?.model) {
            setSelectedModelData(currentWorkflow.workflow_steps.model);
          } else if (data.workflow_steps?.endpoint) {
            setSelectedModelData(data.workflow_steps.endpoint);
          } else if (data.selected_model) {
            setSelectedModelData(data.selected_model);
          } else if (data.workflow_steps?.stage_data?.selected_model) {
            setSelectedModelData(data.workflow_steps.stage_data.selected_model);
          }

          // Set evaluations from workflow data if available
          if (data.next_step_data?.summary?.evaluations) {
            setEvaluations(data.next_step_data.summary.evaluations);
          } else if (data.evaluations) {
            setEvaluations(data.evaluations);
          } else {
            // Fallback to empty array if no evaluations in response
            setEvaluations([]);
          }

          // Build deployment specs from model data
          const modelData = currentWorkflow?.workflow_steps?.model || data.workflow_steps?.model;
          const specs: SpecificationTableItemProps[] = [];

          // Add model specifications
          if (modelData) {
            specs.push({
              name: "Model",
              value: modelData.name || "Unknown Model",
              icon: "/images/drawer/tag.png",
            });

            if (modelData.provider?.name) {
              specs.push({
                name: "Provider",
                value: modelData.provider.name,
                icon: "/images/drawer/tag.png",
              });
            }

            if (modelData.family) {
              specs.push({
                name: "Model Family",
                value: modelData.family,
                icon: "/images/drawer/template-1.png",
              });
            }

            if (modelData.model_size) {
              specs.push({
                name: "Model Size",
                value: `${(modelData.model_size / 1000000000).toFixed(2)}B parameters`,
                icon: "/images/drawer/context.png",
              });
            }

            if (modelData.provider_type) {
              specs.push({
                name: "Type",
                value: modelData.provider_type.replace(/_/g, ' '),
                icon: "/images/drawer/tag.png",
              });
            }

            // Add status indicators
            if (modelData.bud_verified) {
              specs.push({
                name: "Verification",
                value: ["Bud Verified"],
                tagColor: "#4CAF50",
              });
            }

            specs.push({
              name: "Status",
              value: "Ready",
              icon: "/images/drawer/current.png",
            });
          }

          // Override with deployment specs from workflow data if available
          if (data.next_step_data?.summary?.deployment_specs) {
            setDeploymentSpecs(data.next_step_data.summary.deployment_specs);
          } else if (data.deployment_specs) {
            setDeploymentSpecs(data.deployment_specs);
          } else if (data.workflow_steps?.stage_data?.deployment_specs) {
            setDeploymentSpecs(data.workflow_steps.stage_data.deployment_specs);
          } else if (specs.length > 0) {
            setDeploymentSpecs(specs);
          }

          // Extract other relevant data from next_step_data.summary
          if (data.next_step_data?.summary) {
            const summary = data.next_step_data.summary;

            // Update deployment specs with data from summary if available
            const updatedSpecs: SpecificationTableItemProps[] = [];

            if (summary.model_name || modelData?.name) {
              updatedSpecs.push({
                name: "Model",
                value: summary.model_name || modelData?.name || "Unknown Model",
                icon: "/images/drawer/tag.png",
              });
            }

            if (summary.deployment_name) {
              updatedSpecs.push({
                name: "Deployment",
                value: summary.deployment_name,
                icon: "/images/drawer/tag.png",
              });
            }

            if (summary.template_name) {
              updatedSpecs.push({
                name: "Template",
                value: summary.template_name,
                icon: "/images/drawer/template-1.png",
              });
            }

            if (summary.cluster_name) {
              updatedSpecs.push({
                name: "Cluster",
                value: summary.cluster_name,
                icon: "/images/drawer/tag.png",
              });
            }

            if (summary.dataset_size) {
              updatedSpecs.push({
                name: "Dataset Size",
                value: summary.dataset_size,
                icon: "/images/drawer/context.png",
              });
            }

            if (summary.evaluation_type) {
              updatedSpecs.push({
                name: "Evaluation Type",
                value: Array.isArray(summary.evaluation_type) ? summary.evaluation_type : [summary.evaluation_type],
                tagColor: "#4CAF50",
              });
            }

            if (summary.created_by) {
              updatedSpecs.push({
                name: "Created By",
                value: summary.created_by,
                icon: "/images/drawer/tag.png",
              });
            }

            if (summary.status) {
              updatedSpecs.push({
                name: "Status",
                value: summary.status,
                icon: "/images/drawer/current.png",
              });
            }

            // Only update specs if we have data from summary
            if (updatedSpecs.length > 0) {
              setDeploymentSpecs(updatedSpecs);
            }
          }
        } else {
          // No workflow data available
          console.log('No workflow data available');
          setEvaluations([]);
        }
      } catch (error) {
        console.error('Error fetching workflow data:', error);
        // Clear data on error
        setEvaluations([]);
      } finally {
        setIsLoadingData(false);
      }
    };

    initializeData();
  }, [currentWorkflow?.experiment_id, currentWorkflow?.workflow_id, workflowData]);

  return (
    <BudForm
      data={{}}
      // disableNext={!selectedModel?.id}
      // onNext={async () => {
      //   openDrawerWithStep("Benchmark-Configuration");
      // }}
      onBack={async () => {
        openDrawerWithStep("select-evaluation");
      }
      }
      backText="Back"
      disableNext={isSubmitting}
      onNext={async () => {
        try {
          setIsSubmitting(true);

          if (!currentWorkflow?.workflow_id) {
            errorToast("Workflow not found. Please start over.");
            return;
          }

          // Get experiment ID from workflow or drawer props
          const experimentId = currentWorkflow?.workflow_steps?.experiment_id || currentWorkflow?.experiment_id || drawerProps?.experimentId;

          if (!experimentId) {
            errorToast("Experiment ID not found");
            return;
          }

          // Prepare payload for step 5 - trigger the workflow
          const payload = {
            workflow_id: currentWorkflow.workflow_id,
            step_number: 5,
            workflow_total_steps: 5,
            trigger_workflow: true,
            stage_data: {}
          };

          console.log("Triggering evaluation workflow with payload:", payload);

          // Call the API to trigger the evaluation
          const response = await createWorkflow(experimentId, payload);

          console.log("Evaluation workflow triggered successfully:", response);

          successToast("Evaluation workflow started successfully!");

          // Navigate to status page
          openDrawerWithStep("run-evaluation-status");

        } catch (error: any) {
          console.error("Failed to trigger evaluation workflow:", error);
          errorToast(error.message || "Failed to start evaluation workflow");
        } finally {
          setIsSubmitting(false);
        }
      }}
      nextText={isSubmitting ? "Starting..." : "Run Evaluation"}
    >

      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Selected Evaluations"
            description={isLoadingData ? "Loading workflow data..." : "Review the selected evaluations and model configuration"}
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DrawerCard classNames="pb-0">
            <div>
              <div className="pt-[.8rem] flex justify-between items-center flex-wrap gap-y-[1.5rem]">
                <div className="w-full">
                  <Text_14_600_EEEEEE>
                    <div className="flex items-start justify-start max-w-[72%]">

                      <div className="mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
                        <IconRender
                          icon={selectedModelData?.icon || selectedModelData?.icon}
                          size={44}
                          imageSize={28}
                          type={selectedModelData?.provider_type}
                          model={selectedModelData}
                        />
                      </div>
                      <div>
                        <Text_14_400_EEEEEE className="mb-[0.65rem] leading-[140%]">
                          {selectedModelData?.name}
                        </Text_14_400_EEEEEE>
                        <ModelTags model={selectedModelData} maxTags={3} />
                      </div>
                    </div>
                  </Text_14_600_EEEEEE>
                </div>
                {deploymentSpecs.map((item, index) => (
                  <SpecificationTableItem
                    key={index}
                    item={item}
                    valueWidth={220}
                  // valueWidth={getSpecValueWidthOddEven(
                  //   deploymentSpecs,
                  //   index
                  // )}
                  />
                ))}
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Selected Triats"
            description="Evaluation criteria chosen to test and benchmark the model's capabilities"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <div className="flex flex-col	justify-start items-center w-full">


            <div className="evaluationCardWrap w-full ">
              <div className="evaluationCard w-full mt-[0rem]">
                {currentWorkflow?.workflow_steps?.traits_details && (
                  <EvaluationList
                    evaluations={currentWorkflow.workflow_steps.traits_details}
                    handleEvaluationSelection={(evaluation) => {
                      setSelectedEvaluation(evaluation);
                    }}
                    hideSelection={true}
                    selectedEvaluation={selectedEvaluation} />
                )}
                {!currentWorkflow?.workflow_steps?.traits_details && (
                  <div className="text-center py-4 text-gray-400">
                    No traits available
                  </div>
                )}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
