import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Input } from 'antd';
import { SearchOutlined } from "@ant-design/icons";
import { Text_12_400_757575, Text_12_600_EEEEEE, Text_14_400_EEEEEE, Text_14_600_EEEEEE } from "@/components/ui/text";
import EvaluationList, { Evaluation } from "src/flows/components/AvailableEvaluations";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { SpecificationTableItem, SpecificationTableItemProps } from "src/flows/components/SpecificationTableItem";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import IconRender from "src/flows/components/BudIconRender";
import ModelTags from "src/flows/components/ModelTags";
import { Model } from "src/hooks/useModels";


export default function EvaluationSummary() {
  // Mock evaluation data - replace with actual API call
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
  const selectedModel: Model = {
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
  
  const [search, setSearch] = React.useState("");
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
  const { openDrawerWithStep } = useDrawer();

  const filteredEvaluations = mockEvaluations.filter((evaluation) =>
    evaluation.name.toLowerCase().includes(search.toLowerCase()) ||
    evaluation.description?.toLowerCase().includes(search.toLowerCase()) ||
    evaluation.tags?.some(tag => tag.toLowerCase().includes(search.toLowerCase()))
  );



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
      onNext={() => {
        openDrawerWithStep("select-traits");
      }}
      nextText="Next"
    >

      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Selected Evaluations"
            description="Description for ..."
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
                          icon={selectedModel?.icon || selectedModel?.icon}
                          size={44}
                          imageSize={28}
                          type={selectedModel?.provider_type}
                          model={selectedModel}
                        />
                      </div>
                      <div>
                        <Text_14_400_EEEEEE className="mb-[0.65rem] leading-[140%]">
                          {selectedModel?.name}
                        </Text_14_400_EEEEEE>
                        <ModelTags model={selectedModel} maxTags={3} />
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
