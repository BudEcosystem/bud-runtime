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
import { Model, useModels } from "src/hooks/useModels";


export default function EvaluationSummary() {
  const { getWorkflowData, workflowData, currentWorkflow, createEvaluationWorkflow } = useEvaluations();
  const { getModel, selectedModel: selectedModelFromStore } = useModels();
  const [isLoadingData, setIsLoadingData] = React.useState(true);
  const [evaluations, setEvaluations] = React.useState<Evaluation[]>([]);
  const [selectedModelData, setSelectedModelData] = React.useState<Model | null>(null);
  const [modelId, setModelId] = React.useState<string | null>(null);

  // Mock evaluation data - will be replaced with actual data
  const mockEvaluations: Evaluation[] = [
    {
      id: "eval-1",
      name: "Truthfulness Evaluation",
      description: "Evaluates the model's ability to provide accurate and truthful responses",
      category: "accuracy",
      tags: ["accuracy", "truthfulness", "hallucination"]
    },
    {
      id: "eval-2",
      name: "Code Generation Benchmark",
      description: "Tests the model's ability to generate syntactically correct and functional code",
      category: "code",
      tags: ["code", "programming", "syntax"]
    },
    {
      id: "eval-3",
      name: "Language Understanding",
      description: "Comprehensive evaluation of natural language understanding capabilities",
      category: "language",
      tags: ["NLU", "comprehension", "context"]
    },
    {
      id: "eval-4",
      name: "Mathematical Reasoning",
      description: "Assesses mathematical problem-solving and logical reasoning abilities",
      category: "math",
      tags: ["math", "logic", "reasoning"]
    },
    {
      id: "eval-5",
      name: "Safety & Ethics",
      description: "Evaluates adherence to safety guidelines and ethical considerations",
      category: "safety",
      tags: ["safety", "ethics", "harmful content"]
    }
  ];

  // Mock selected model data - replace with actual data from store
  const mockSelectedModel: Model = {
    id: "model-1",
    name: "GPT-4o",
    author: "OpenAI",
    provider: {
      id: "provider-1",
      name: "OpenAI",
      icon: "/images/providers/openai.png",
      description: "OpenAI Provider",
      type: "cloud",
    },
    provider_type: "cloud_model",
    modality: {
      text: { input: true, output: true, label: "Text" },
      image: { input: true, output: false, label: "Image" },
      audio: { input: false, output: false, label: "Audio" }
    },
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: true, label: "Chat" },
      completion: { path: "/v1/completions", enabled: true, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: true, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: true, label: "Batch" },
      response: { path: "/v1/response", enabled: false, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: true, label: "Moderation" }
    },
    source: "OpenAI",
    uri: "openai/gpt-4o",
    model_size: 1000000000000, // 1T parameters
    tasks: [
      { name: "Chat Completion", color: "#4CAF50" },
      { name: "Text Generation", color: "#2196F3" },
      { name: "Code Generation", color: "#FF9800" }
    ],
    description: "GPT-4o is OpenAI's most advanced multimodal model",
    icon: "🤖",
    tags: [
      { name: "multimodal", color: "#9C27B0" },
      { name: "chat", color: "#4CAF50" },
      { name: "production-ready", color: "#2196F3" }
    ],
    languages: ["en"],
    use_cases: [],
    family: "GPT",
    kv_cache_size: 0,
    bud_verified: true,
    scan_verified: false,
    eval_verified: false,
    created_at: new Date().toISOString()
  };

  const [deploymentSpecs, detDeploymentSpecs] = React.useState<SpecificationTableItemProps[]>([
    {
      name: "Model",
      value: "GPT-4o",
      icon: "/images/drawer/tag.png",
    },
    {
      name: "Deployment",
      value: "production-deployment-1",
      icon: "/images/drawer/tag.png",
    },
    {
      name: "Template",
      value: "Evaluation Template v2",
      icon: "/images/drawer/template-1.png",
    },
    {
      name: "Cluster",
      value: "us-west-2-cluster",
      icon: "/images/drawer/tag.png",
    },
    {
      name: "Dataset Size",
      value: "10,000 samples",
      icon: "/images/drawer/context.png",
    },
    {
      name: "Evaluation Type",
      value: ["Accuracy"],
      tagColor: "#4CAF50",
    },
    {
      name: "Created By",
      value: "Admin User",
      icon: "/images/drawer/tag.png",
    },
    {
      name: "Status",
      value: "Ready",
      icon: "/images/drawer/current.png",
    }
  ]);
  const [selectedEvaluation, setSelectedEvaluation] = React.useState<Evaluation | null>(null);
  const { openDrawerWithStep, drawerProps } = useDrawer();
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  // Use existing workflowData if available, otherwise fetch it
  React.useEffect(() => {
    const initializeData = async () => {
      try {
        setIsLoadingData(true);

        let data = workflowData;

        // Only fetch if we don't have workflowData already
        if (!data && currentWorkflow?.experiment_id && currentWorkflow?.workflow_id) {
          data = await getWorkflowData(
            currentWorkflow.experiment_id,
            currentWorkflow.workflow_id
          );
        }

        // Extract data from workflow response
        if (data) {
          // Check for model ID in next_step_data.summary.model_selected
          const extractedModelId = data.next_step_data?.summary?.model_selected;

          if (extractedModelId) {
            // Store model ID to trigger separate effect for fetching
            setModelId(extractedModelId);
          } else if (data.selected_model) {
            setSelectedModelData(data.selected_model);
          } else if (data.workflow_steps?.stage_data?.selected_model) {
            setSelectedModelData(data.workflow_steps.stage_data.selected_model);
          } else {
            // Fallback to mock model
            setSelectedModelData(mockSelectedModel);
          }

          // Set evaluations from workflow data if available
          if (data.next_step_data?.summary?.evaluations) {
            setEvaluations(data.next_step_data.summary.evaluations);
          } else if (data.evaluations) {
            setEvaluations(data.evaluations);
          } else {
            // Fallback to mock data if no evaluations in response
            setEvaluations(mockEvaluations);
          }

          // Update deployment specs from workflow data
          if (data.next_step_data?.summary?.deployment_specs) {
            detDeploymentSpecs(data.next_step_data.summary.deployment_specs);
          } else if (data.deployment_specs) {
            detDeploymentSpecs(data.deployment_specs);
          } else if (data.workflow_steps?.stage_data?.deployment_specs) {
            detDeploymentSpecs(data.workflow_steps.stage_data.deployment_specs);
          }

          // Extract other relevant data from next_step_data.summary
          if (data.next_step_data?.summary) {
              const summary = data.next_step_data.summary;

              // Update deployment specs with data from summary if available
              const updatedSpecs: SpecificationTableItemProps[] = [];

              if (summary.model_name || selectedModelData?.name) {
                updatedSpecs.push({
                  name: "Model",
                  value: summary.model_name || selectedModelData?.name || "GPT-4o",
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
                detDeploymentSpecs(updatedSpecs);
              }
            }
        } else {
          // Use mock data if no workflow data available
          console.log('No workflow data available, using mock data');
          setEvaluations(mockEvaluations);
          setSelectedModelData(mockSelectedModel);
        }
      } catch (error) {
        console.error('Error fetching workflow data:', error);
        // Fallback to mock data on error
        setEvaluations(mockEvaluations);
        setSelectedModelData(mockSelectedModel);
      } finally {
        setIsLoadingData(false);
      }
    };

    initializeData();
  }, [currentWorkflow?.experiment_id, currentWorkflow?.workflow_id, workflowData]);

  // Separate effect to fetch model details when modelId changes
  React.useEffect(() => {
    if (modelId) {
      console.log('Fetching model details for ID:', modelId);
      getModel(modelId).then((response: any) => {
        if (response) {
          // The model data is in response.model and response.model_tree
          const modelData: any = {
            ...response.model,
            ...response.model_tree,
            endpoints_count: response.endpoints_count,
            eval_result: response.eval_result,
            scan_result: response.scan_result,
          };
          console.log('Model data fetched:', modelData);
          setSelectedModelData(modelData);
        }
      }).catch((error: any) => {
        console.error('Error fetching model details:', error);
        // Fallback to mock model
        setSelectedModelData(mockSelectedModel);
      });
    }
  }, [modelId]);

  // Watch for selectedModel changes from store (if model was already fetched)
  React.useEffect(() => {
    if (selectedModelFromStore && modelId) {
      console.log('Using selectedModel from store:', selectedModelFromStore);
      setSelectedModelData(selectedModelFromStore);
    }
  }, [selectedModelFromStore, modelId]);

  const filteredEvaluations = evaluations;



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
          const experimentId = currentWorkflow.experiment_id || drawerProps?.experimentId;

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
          const response = await createEvaluationWorkflow(experimentId, payload);

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
            title="Evaluation Summary"
            description="Description for ..."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <div className="flex flex-col	justify-start items-center w-full">


            <div className="evaluationCardWrap w-full ">
              <div className="evaluationCard w-full mt-[0rem]">
                {filteredEvaluations.length > 0 ?
                  <EvaluationList
                    evaluations={filteredEvaluations}
                    handleEvaluationSelection={(evaluation) => {
                      setSelectedEvaluation(evaluation);
                    }}
                    selectedEvaluation={selectedEvaluation} />
                  : (
                    <>
                      <div
                        className="mt-[1.5rem]"
                      />
                      <BudStepAlert
                        type="warining"
                        title='No Evaluations Found'
                        description='No evaluations match your search criteria. Try adjusting your search terms.'
                      />
                    </>
                  )}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
