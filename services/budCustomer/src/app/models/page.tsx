"use client";
import React from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button, Card, Row, Col, Flex } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_15_600_EEEEEE,
  Text_16_400_EEEEEE,
  Text_19_600_EEEEEE,
  Text_24_500_EEEEEE
} from "@/components/ui/text";
import dayjs from "dayjs";

interface Model {
  id: string;
  name: string;
  author: string;
  description: string;
  provider_type: "model" | "cloud_model";
  model_size: number;
  icon: string;
  status: "Available" | "Deprecated" | "Coming Soon";
  modality: {
    text: { input: boolean; output: boolean };
    image: { input: boolean; output: boolean };
    audio: { input: boolean; output: boolean };
  };
  tasks: { name: string; color: string }[];
  tags: { name: string; color: string }[];
  pricing?: {
    cost_per_million_tokens: number;
  };
  availability_percentage?: number;
  created_at: string;
  updated_at: string;
}

// Mock data matching the reference app structure
const mockModels: Model[] = [
  {
    id: "1",
    name: "GPT-4",
    author: "OpenAI",
    description: "Most capable GPT-4 model, great for tasks that require creativity and advanced reasoning.",
    provider_type: "cloud_model",
    model_size: 175,
    icon: "/icons/openAi.png",
    status: "Available",
    modality: {
      text: { input: true, output: true },
      image: { input: true, output: false },
      audio: { input: false, output: false }
    },
    tasks: [
      { name: "Text Generation", color: "#965CDE" },
      { name: "Question Answering", color: "#4077E6" },
      { name: "Code Generation", color: "#479D5F" }
    ],
    tags: [
      { name: "Large", color: "#EC7575" },
      { name: "Multimodal", color: "#D1B854" }
    ],
    pricing: { cost_per_million_tokens: 30 },
    availability_percentage: 99.9,
    created_at: "2024-01-15",
    updated_at: "2024-01-20"
  },
  {
    id: "2", 
    name: "Claude-3.5-Sonnet",
    author: "Anthropic",
    description: "Claude 3.5 Sonnet delivers better-than-Opus capabilities, faster-than-Sonnet speeds.",
    provider_type: "cloud_model",
    model_size: 200,
    icon: "/icons/default.png",
    status: "Available",
    modality: {
      text: { input: true, output: true },
      image: { input: true, output: false },
      audio: { input: false, output: false }
    },
    tasks: [
      { name: "Text Generation", color: "#965CDE" },
      { name: "Analysis", color: "#4077E6" }
    ],
    tags: [
      { name: "Large", color: "#EC7575" },
      { name: "Fast", color: "#479D5F" }
    ],
    pricing: { cost_per_million_tokens: 15 },
    availability_percentage: 98.5,
    created_at: "2024-02-01",
    updated_at: "2024-02-05"
  },
  {
    id: "3",
    name: "Llama-2-70B",
    author: "Meta",
    description: "Large language model trained on a diverse dataset for general-purpose text generation.",
    provider_type: "model",
    model_size: 70,
    icon: "/icons/huggingFace.png",
    status: "Available",
    modality: {
      text: { input: true, output: true },
      image: { input: false, output: false },
      audio: { input: false, output: false }
    },
    tasks: [
      { name: "Text Generation", color: "#965CDE" },
      { name: "Summarization", color: "#D1B854" }
    ],
    tags: [
      { name: "Open Source", color: "#479D5F" },
      { name: "Local", color: "#4077E6" }
    ],
    availability_percentage: 95.2,
    created_at: "2024-01-10",
    updated_at: "2024-01-15"
  },
  {
    id: "4",
    name: "DALL-E 3",
    author: "OpenAI", 
    description: "Most advanced image generation model with exceptional quality and prompt adherence.",
    provider_type: "cloud_model",
    model_size: 50,
    icon: "/icons/openAi.png",
    status: "Available",
    modality: {
      text: { input: true, output: false },
      image: { input: false, output: true },
      audio: { input: false, output: false }
    },
    tasks: [
      { name: "Image Generation", color: "#EC7575" },
      { name: "Art Creation", color: "#D1B854" }
    ],
    tags: [
      { name: "Image", color: "#EC7575" },
      { name: "Creative", color: "#D1B854" }
    ],
    pricing: { cost_per_million_tokens: 40 },
    availability_percentage: 97.8,
    created_at: "2024-01-25",
    updated_at: "2024-01-30"
  },
  {
    id: "5",
    name: "Whisper Large",
    author: "OpenAI",
    description: "State-of-the-art speech recognition model supporting 99+ languages.",
    provider_type: "model",
    model_size: 1.5,
    icon: "/icons/openAi.png", 
    status: "Available",
    modality: {
      text: { input: false, output: true },
      image: { input: false, output: false },
      audio: { input: true, output: false }
    },
    tasks: [
      { name: "Speech Recognition", color: "#4077E6" },
      { name: "Transcription", color: "#479D5F" }
    ],
    tags: [
      { name: "Audio", color: "#4077E6" },
      { name: "Multilingual", color: "#965CDE" }
    ],
    availability_percentage: 96.5,
    created_at: "2024-01-05",
    updated_at: "2024-01-12"
  },
  {
    id: "6",
    name: "Stable Diffusion XL",
    author: "Stability AI",
    description: "Advanced text-to-image model with high-resolution output and artistic capabilities.",
    provider_type: "model",
    model_size: 3.5,
    icon: "/icons/huggingFace.png",
    status: "Available",
    modality: {
      text: { input: true, output: false },
      image: { input: false, output: true },
      audio: { input: false, output: false }
    },
    tasks: [
      { name: "Image Generation", color: "#EC7575" },
      { name: "Art Creation", color: "#D1B854" }
    ],
    tags: [
      { name: "Open Source", color: "#479D5F" },
      { name: "Image", color: "#EC7575" }
    ],
    availability_percentage: 94.1,
    created_at: "2024-01-08",
    updated_at: "2024-01-18"
  }
];


export default function ModelsPage() {

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <Text_24_500_EEEEEE>Models</Text_24_500_EEEEEE>
          </div>
          <Flex gap={16} align="center">
            <Icon icon="ph:magnifying-glass" className="text-[#757575] text-[1.25rem] cursor-pointer hover:text-[#EEEEEE]" />
            <Button
              type="text"
              icon={<Icon icon="ph:chart-line-up" />}
              className="text-[#EEEEEE] hover:text-[#965CDE]"
            >
              Benchmark history
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              className="bg-[#965CDE] border-[#965CDE] hover:bg-[#7B4BC3] px-[1.5rem]"
            >
              Model
            </Button>
          </Flex>
        </div>


        {/* Models Grid */}
        <Row gutter={[24, 24]}>
          {mockModels.map((model) => (
            <Col key={model.id} xs={24} sm={12} lg={8}>
              <Card
                className="h-full bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#965CDE] hover:shadow-lg transition-all duration-300 cursor-pointer"
                bodyStyle={{ padding: 0 }}
              >
                <div className="p-6">
                  {/* Header with Icon and Date */}
                  <div className="flex items-start justify-between mb-6">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#965CDE] to-[#7B4BC3] flex items-center justify-center">
                      {model.name.includes("GPT") && (
                        <Icon icon="simple-icons:openai" className="text-white text-[1.5rem]" />
                      )}
                      {model.name.includes("Claude") && (
                        <Icon icon="simple-icons:anthropic" className="text-white text-[1.5rem]" />
                      )}
                      {model.name.includes("Llama") && (
                        <Icon icon="simple-icons:meta" className="text-white text-[1.5rem]" />
                      )}
                      {model.name.includes("DALL-E") && (
                        <Icon icon="ph:image" className="text-white text-[1.5rem]" />
                      )}
                      {model.name.includes("Whisper") && (
                        <Icon icon="ph:microphone" className="text-white text-[1.5rem]" />
                      )}
                      {model.name.includes("Stable") && (
                        <Icon icon="ph:palette" className="text-white text-[1.5rem]" />
                      )}
                    </div>
                    <Text_12_400_757575>{dayjs(model.updated_at).format('DD MMM, YYYY')}</Text_12_400_757575>
                  </div>

                  {/* Model Title */}
                  <Text_19_600_EEEEEE className="mb-3 line-clamp-1">
                    {model.name}
                  </Text_19_600_EEEEEE>

                  {/* Description */}
                  <Text_13_400_EEEEEE className="mb-6 line-clamp-2 text-[#B3B3B3] leading-relaxed">
                    {model.description}
                  </Text_13_400_EEEEEE>

                  {/* Tags Row */}
                  <div className="flex flex-wrap gap-2 mb-6">
                    <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-[#965CDE20] text-[#965CDE]">
                      <Icon icon="ph:star" className="text-xs" />
                      <Text_12_400_B3B3B3 className="text-[#965CDE]">0</Text_12_400_B3B3B3>
                    </div>
                    
                    <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-[#1F1F1F] text-[#B3B3B3]">
                      <Icon icon="ph:hard-drives" className="text-xs" />
                      <Text_12_400_B3B3B3>{model.provider_type === "cloud_model" ? "Cloud" : "Local"}</Text_12_400_B3B3B3>
                    </div>

                    <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-[#1F1F1F] text-[#B3B3B3]">
                      <Icon icon="ph:link" className="text-xs" />
                      <Text_12_400_B3B3B3>{model.name.replace(/[^a-zA-Z0-9]/g, '').toLowerCase()}</Text_12_400_B3B3B3>
                    </div>
                  </div>

                  {/* Author Tag */}
                  <div className="flex items-center gap-2 mb-6">
                    <Icon icon="ph:user" className="text-[#B3B3B3] text-sm" />
                    <Text_12_400_B3B3B3 className="text-[#D1B854]">{model.author}</Text_12_400_B3B3B3>
                    {model.tasks.length > 1 && (
                      <Text_12_400_B3B3B3 className="text-[#757575]">+{model.tasks.length - 1} more</Text_12_400_B3B3B3>
                    )}
                  </div>
                </div>

                {/* Recommended Cluster Section */}
                <div className="bg-[#0F0F0F] px-6 py-4 border-t border-[#1F1F1F]">
                  <Text_12_400_757575 className="mb-2">Recommended Cluster</Text_12_400_757575>
                  <Text_13_400_EEEEEE className="text-[#757575]">No data available</Text_13_400_EEEEEE>
                </div>
              </Card>
            </Col>
          ))}
        </Row>

      </div>
    </DashboardLayout>
  );
}