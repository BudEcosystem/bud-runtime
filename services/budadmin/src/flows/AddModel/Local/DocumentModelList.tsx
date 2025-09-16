import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

// Curated list of document processing models from Hugging Face
const CURATED_DOCUMENT_MODELS = [
  {
    id: "microsoft/TrOCR-base-handwritten",
    name: "TrOCR Base Handwritten",
    uri: "microsoft/TrOCR-base-handwritten",
    author: "Microsoft",
    description: "Transformer-based OCR model for handwritten text recognition. Ideal for digitizing handwritten documents.",
    tags: [
      { name: "OCR", color: "#1890ff" },
      { name: "Handwriting", color: "#52c41a" },
      { name: "Text Recognition", color: "#722ed1" }
    ],
    tasks: [
      { name: "OCR", color: "#1890ff" },
      { name: "Text Recognition", color: "#722ed1" }
    ],
    languages: ["en", "multilingual"],
    use_cases: ["Document Digitization", "Handwriting Recognition", "OCR"],
    family: "TrOCR",
    kv_cache_size: 0,
    model_size: 334000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: true, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: false, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
  {
    id: "microsoft/TrOCR-large-printed",
    name: "TrOCR Large Printed",
    uri: "microsoft/TrOCR-large-printed",
    author: "Microsoft",
    description: "Large transformer model optimized for printed text OCR with high accuracy on various fonts and layouts.",
    tags: [
      { name: "OCR", color: "#1890ff" },
      { name: "Printed Text", color: "#52c41a" },
      { name: "Text Recognition", color: "#722ed1" }
    ],
    tasks: [
      { name: "OCR", color: "#1890ff" },
      { name: "Text Recognition", color: "#722ed1" }
    ],
    languages: ["en", "multilingual"],
    use_cases: ["Document Digitization", "Printed Text Recognition", "OCR"],
    family: "TrOCR",
    kv_cache_size: 0,
    model_size: 558000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: true, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: false, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
  {
    id: "microsoft/layoutlmv3-base",
    name: "LayoutLMv3 Base",
    uri: "microsoft/layoutlmv3-base",
    author: "Microsoft",
    description: "Multimodal model for document understanding with layout awareness. Excels at form understanding and information extraction.",
    tags: [
      { name: "Document Understanding", color: "#1890ff" },
      { name: "Layout Analysis", color: "#f5222d" },
      { name: "Multimodal", color: "#fa8c16" }
    ],
    tasks: [
      { name: "Document Understanding", color: "#1890ff" },
      { name: "Information Extraction", color: "#52c41a" }
    ],
    languages: ["en", "multilingual"],
    use_cases: ["Form Understanding", "Document Layout Analysis", "Information Extraction"],
    family: "LayoutLM",
    kv_cache_size: 0,
    model_size: 368000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: true, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: false, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
  {
    id: "impira/layoutlm-document-qa",
    name: "LayoutLM Document QA",
    uri: "impira/layoutlm-document-qa",
    author: "Impira",
    description: "Fine-tuned LayoutLM for document question answering. Perfect for extracting specific information from forms and documents.",
    tags: [
      { name: "Document QA", color: "#1890ff" },
      { name: "Information Extraction", color: "#52c41a" },
      { name: "Question Answering", color: "#722ed1" }
    ],
    tasks: [
      { name: "Document QA", color: "#1890ff" },
      { name: "Question Answering", color: "#722ed1" }
    ],
    languages: ["en"],
    use_cases: ["Document Question Answering", "Form Processing", "Information Extraction"],
    family: "LayoutLM",
    kv_cache_size: 0,
    model_size: 427000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: true, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: false, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
  {
    id: "naver-clova-ix/donut-base",
    name: "Donut Base",
    uri: "naver-clova-ix/donut-base",
    author: "Naver Clova",
    description: "Document understanding transformer without OCR dependency. End-to-end processing for various document types.",
    tags: [
      { name: "Document Understanding", color: "#1890ff" },
      { name: "End-to-end", color: "#52c41a" },
      { name: "Vision Transformer", color: "#eb2f96" }
    ],
    tasks: [
      { name: "Document Understanding", color: "#1890ff" },
      { name: "Vision Processing", color: "#eb2f96" }
    ],
    languages: ["en", "multilingual"],
    use_cases: ["Document Understanding", "Receipt Processing", "Form Processing"],
    family: "Donut",
    kv_cache_size: 0,
    model_size: 201000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: false, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: false, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
  {
    id: "microsoft/table-transformer-detection",
    name: "Table Transformer Detection",
    uri: "microsoft/table-transformer-detection",
    author: "Microsoft",
    description: "Specialized model for detecting and extracting tables from documents. Essential for processing structured data.",
    tags: [
      { name: "Table Detection", color: "#1890ff" },
      { name: "Layout Analysis", color: "#f5222d" },
      { name: "Structure Recognition", color: "#13c2c2" }
    ],
    tasks: [
      { name: "Table Detection", color: "#1890ff" },
      { name: "Structure Recognition", color: "#13c2c2" }
    ],
    languages: ["en", "multilingual"],
    use_cases: ["Table Extraction", "Document Structure Analysis", "Data Extraction"],
    family: "Table Transformer",
    kv_cache_size: 0,
    model_size: 288000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: false, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: false, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
  {
    id: "Qwen/Qwen2-VL-7B-Instruct",
    name: "Qwen2-VL 7B Instruct",
    uri: "Qwen/Qwen2-VL-7B-Instruct",
    author: "Qwen",
    description: "Vision-language model for advanced document understanding and reasoning. Handles complex document analysis tasks.",
    tags: [
      { name: "Vision-Language", color: "#1890ff" },
      { name: "Document Understanding", color: "#722ed1" },
      { name: "Instruction Following", color: "#fa541c" }
    ],
    tasks: [
      { name: "Document Understanding", color: "#722ed1" },
      { name: "Vision-Language", color: "#1890ff" }
    ],
    languages: ["en", "zh", "multilingual"],
    use_cases: ["Document Analysis", "Visual QA", "Complex Reasoning"],
    family: "Qwen2",
    kv_cache_size: 0,
    model_size: 7000000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: true, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: true, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
  {
    id: "microsoft/Florence-2-base",
    name: "Florence-2 Base",
    uri: "microsoft/Florence-2-base",
    author: "Microsoft",
    description: "Advanced vision foundation model for comprehensive document understanding. Supports OCR, captioning, and visual grounding.",
    tags: [
      { name: "Vision Foundation", color: "#1890ff" },
      { name: "Document Analysis", color: "#52c41a" },
      { name: "Multi-task", color: "#faad14" }
    ],
    tasks: [
      { name: "Document Analysis", color: "#52c41a" },
      { name: "OCR", color: "#1890ff" },
      { name: "Visual Grounding", color: "#faad14" }
    ],
    languages: ["en", "multilingual"],
    use_cases: ["OCR", "Image Captioning", "Visual Grounding", "Document Understanding"],
    family: "Florence",
    kv_cache_size: 0,
    model_size: 232000000,
    provider_type: "hugging_face",
    modality: {
      audio: { input: false, output: false, label: "Audio" },
      image: { input: true, output: false, label: "Image" },
      text: { input: true, output: true, label: "Text" }
    },
    source: "huggingface",
    supported_endpoints: {
      chat: { path: "/v1/chat/completions", enabled: false, label: "Chat" },
      completion: { path: "/v1/completions", enabled: false, label: "Completion" },
      image_generation: { path: "/v1/images/generations", enabled: false, label: "Image Generation" },
      audio_transcription: { path: "/v1/audio/transcriptions", enabled: false, label: "Audio Transcription" },
      audio_speech: { path: "/v1/audio/speech", enabled: false, label: "Audio Speech" },
      embedding: { path: "/v1/embeddings", enabled: false, label: "Embedding" },
      batch: { path: "/v1/batches", enabled: false, label: "Batch" },
      response: { path: "/v1/response", enabled: true, label: "Response" },
      rerank: { path: "/v1/rerank", enabled: false, label: "Rerank" },
      moderation: { path: "/v1/moderations", enabled: false, label: "Moderation" }
    },
    provider: {
      id: "huggingface",
      name: "Hugging Face",
      description: "Hugging Face Model Hub",
      icon: "/icons/providers/huggingface.png",
      type: "huggingface"
    },
    icon: null,
    bud_verified: false,
    scan_verified: false,
    eval_verified: false
  },
];

export default function DocumentModelList() {
  const { openDrawerWithStep } = useDrawer();
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const {
    selectedModel,
    setSelectedModel,
    currentWorkflow,
    updateCloudModel,
    setLocalModelDetails,
    setCameFromDocumentList
  } = useDeployModel();

  const [models, setModels] = useState(CURATED_DOCUMENT_MODELS);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      setSelectedModel(currentWorkflow.workflow_steps.model);
    }
  }, [currentWorkflow]);

  const filteredModels = models.filter(model => {
    return model.name?.toLowerCase().includes(search.toLowerCase()) ||
           model.tags?.some((tag) => tag.name?.toLowerCase().includes(search.toLowerCase())) ||
           model.description?.toLowerCase().includes(search.toLowerCase());
  });

  const handleModelSelect = (model) => {
    setSelectedModel(model);
    // Pre-fill the local model details - use URI as the name
    setLocalModelDetails({
      name: model.uri,  // Use URI as the model name
      uri: model.uri,
      author: model.author,
      tags: model.tags,
      icon: "",
    });
  };

  const handleAddCustom = () => {
    setSelectedModel(null);
    setLocalModelDetails({
      name: "",
      uri: "",
      author: "",
      tags: [],
      icon: "",
    });
    setCameFromDocumentList(true);
    openDrawerWithStep("add-local-model");
  };

  const handleNext = async () => {
    if (selectedModel) {
      // Pre-populate the local model details with selected curated model
      setLocalModelDetails({
        name: selectedModel.uri,  // Use URI as the model name
        uri: selectedModel.uri,
        author: selectedModel.author,
        tags: selectedModel.tags,
        icon: "",
      });
      setCameFromDocumentList(true);
      // Go to the Enter Model Information step with pre-filled data
      openDrawerWithStep("add-local-model");
    }
  };

  return (
    <BudForm
      data={{}}
      onBack={() => {
        openDrawerWithStep("model-source");
      }}
      disableNext={!selectedModel?.id || isExpandedViewOpen}
      onNext={handleNext}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select a Document Model"
            description="Choose from our curated list of document processing models from Hugging Face or add your own custom model"
          />
          <DeployModelSelect
            models={models}
            filteredModels={filteredModels}
            setSelectedModel={handleModelSelect}
            selectedModel={selectedModel}
            hideSeeMore
          >
            <ModelFilter
              search={search}
              setSearch={setSearch}
              buttonLabel="+&nbsp;Custom&nbsp;Model"
              onButtonClick={handleAddCustom}
            />
          </DeployModelSelect>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
