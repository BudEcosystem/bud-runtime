"use client";
import React, { useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Flex, Button, Select, Tag, Input, Segmented } from "antd";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_14_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_15_600_EEEEEE,
  Text_19_600_EEEEEE,
  Text_24_500_EEEEEE
} from "@/components/ui/text";
import { Icon } from "@iconify/react/dist/iconify.js";
import styles from "./playground.module.scss";

const { TextArea } = Input;

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export default function PlaygroundPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hello! I'm your AI assistant. How can I help you today?",
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [selectedModel, setSelectedModel] = useState("gpt-4");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [isLoading, setIsLoading] = useState(false);

  const models = [
    { value: "gpt-4", label: "GPT-4", provider: "OpenAI" },
    { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo", provider: "OpenAI" },
    { value: "claude-3-opus", label: "Claude 3 Opus", provider: "Anthropic" },
    { value: "claude-3-sonnet", label: "Claude 3 Sonnet", provider: "Anthropic" }
  ];

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue,
      timestamp: new Date()
    };

    setMessages([...messages, userMessage]);
    setInputValue("");
    setIsLoading(true);

    // Simulate AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `I understand you're asking about "${inputValue}". This is a simulated response from the ${selectedModel} model. In a real implementation, this would connect to the actual AI service.`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, aiMessage]);
      setIsLoading(false);
    }, 1500);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearConversation = () => {
    setMessages([{
      id: "1",
      role: "assistant",
      content: "Hello! I'm your AI assistant. How can I help you today?",
      timestamp: new Date()
    }]);
  };

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem] h-full">
          <Flex className="h-full gap-[1.5rem]">
            {/* Chat Area */}
            <div className="flex-1 flex flex-col">
              {/* Header */}
              <Flex justify="space-between" align="center" className="mb-[1.5rem]">
                <div>
                  <Text_24_500_EEEEEE>Playground</Text_24_500_EEEEEE>
                  <Text_14_400_B3B3B3 className="mt-[0.5rem]">
                    Test and experiment with AI models
                  </Text_14_400_B3B3B3>
                </div>
                <Button
                  icon={<Icon icon="ph:trash" />}
                  onClick={clearConversation}
                  className="bg-transparent border-[#1F1F1F] text-[#B3B3B3] hover:text-[#EEEEEE] hover:border-[#965CDE]"
                >
                  Clear
                </Button>
              </Flex>

              {/* Messages Container */}
              <div className="cardBG border border-[#1F1F1F] rounded-[12px] flex-1 flex flex-col overflow-hidden">
                <div className="flex-1 overflow-y-auto p-[1.5rem]">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`mb-[1.5rem] ${
                        message.role === 'user' ? 'ml-[3rem]' : 'mr-[3rem]'
                      }`}
                    >
                      <Flex gap={12} align="start">
                        {message.role === 'assistant' && (
                          <div className="w-[2rem] h-[2rem] rounded-full bg-[#965CDE] flex items-center justify-center flex-shrink-0">
                            <Icon icon="ph:robot" className="text-white text-[1.25rem]" />
                          </div>
                        )}
                        <div className={`flex-1 ${message.role === 'user' ? 'text-right' : ''}`}>
                          <div className={`inline-block px-[1rem] py-[0.75rem] rounded-[8px] ${
                            message.role === 'user'
                              ? 'bg-[#965CDE1A] border border-[#965CDE33]'
                              : 'bg-[#1F1F1F]'
                          }`}>
                            <Text_14_400_EEEEEE className="whitespace-pre-wrap">
                              {message.content}
                            </Text_14_400_EEEEEE>
                          </div>
                          <Text_12_400_757575 className="mt-[0.5rem] px-[0.5rem]">
                            {message.timestamp.toLocaleTimeString()}
                          </Text_12_400_757575>
                        </div>
                        {message.role === 'user' && (
                          <div className="w-[2rem] h-[2rem] rounded-full bg-[#4077E6] flex items-center justify-center flex-shrink-0">
                            <Icon icon="ph:user" className="text-white text-[1.25rem]" />
                          </div>
                        )}
                      </Flex>
                    </div>
                  ))}
                  {isLoading && (
                    <div className="mr-[3rem]">
                      <Flex gap={12} align="start">
                        <div className="w-[2rem] h-[2rem] rounded-full bg-[#965CDE] flex items-center justify-center">
                          <Icon icon="ph:robot" className="text-white text-[1.25rem]" />
                        </div>
                        <div className="bg-[#1F1F1F] px-[1rem] py-[0.75rem] rounded-[8px]">
                          <div className="flex gap-[0.25rem]">
                            <span className="w-[0.5rem] h-[0.5rem] bg-[#757575] rounded-full animate-bounce" style={{animationDelay: '0ms'}}></span>
                            <span className="w-[0.5rem] h-[0.5rem] bg-[#757575] rounded-full animate-bounce" style={{animationDelay: '150ms'}}></span>
                            <span className="w-[0.5rem] h-[0.5rem] bg-[#757575] rounded-full animate-bounce" style={{animationDelay: '300ms'}}></span>
                          </div>
                        </div>
                      </Flex>
                    </div>
                  )}
                </div>

                {/* Input Area */}
                <div className="border-t border-[#1F1F1F] p-[1.5rem]">
                  <Flex gap={12}>
                    <TextArea
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Type your message..."
                      autoSize={{ minRows: 1, maxRows: 4 }}
                      className="flex-1 bg-[#1F1F1F] border-[#2F2F2F] text-[#EEEEEE] placeholder-[#757575] resize-none"
                      style={{
                        background: '#1F1F1F',
                        borderColor: '#2F2F2F'
                      }}
                    />
                    <Button
                      type="primary"
                      icon={<Icon icon="ph:paper-plane-tilt" />}
                      onClick={handleSendMessage}
                      loading={isLoading}
                      disabled={!inputValue.trim()}
                      className="bg-[#965CDE] border-[#965CDE] h-[2.5rem] px-[1.5rem]"
                    >
                      Send
                    </Button>
                  </Flex>
                </div>
              </div>
            </div>

            {/* Settings Panel */}
            <div className="w-[24rem]">
              <div className="cardBG border border-[#1F1F1F] rounded-[12px] p-[1.5rem]">
                <Text_15_600_EEEEEE className="mb-[1.5rem]">Model Settings</Text_15_600_EEEEEE>

                {/* Model Selection */}
                <div className="mb-[1.5rem]">
                  <Text_12_400_B3B3B3 className="mb-[0.75rem]">MODEL</Text_12_400_B3B3B3>
                  <Select
                    value={selectedModel}
                    onChange={setSelectedModel}
                    className="w-full"
                    style={{
                      height: '40px'
                    }}
                    options={models.map(model => ({
                      value: model.value,
                      label: (
                        <Flex justify="space-between" align="center">
                          <span>{model.label}</span>
                          <Tag className="bg-[#1F1F1F] border-[#2F2F2F] text-[#757575] text-[0.625rem]">
                            {model.provider}
                          </Tag>
                        </Flex>
                      )
                    }))}
                  />
                </div>

                {/* Temperature */}
                <div className="mb-[1.5rem]">
                  <Flex justify="space-between" align="center" className="mb-[0.75rem]">
                    <Text_12_400_B3B3B3>TEMPERATURE</Text_12_400_B3B3B3>
                    <Text_13_400_EEEEEE>{temperature}</Text_13_400_EEEEEE>
                  </Flex>
                  <div className="relative">
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.1"
                      value={temperature}
                      onChange={(e) => setTemperature(parseFloat(e.target.value))}
                      className={styles.slider}
                    />
                    <div className="flex justify-between mt-[0.5rem]">
                      <Text_12_400_757575>0</Text_12_400_757575>
                      <Text_12_400_757575>2</Text_12_400_757575>
                    </div>
                  </div>
                </div>

                {/* Max Tokens */}
                <div className="mb-[1.5rem]">
                  <Flex justify="space-between" align="center" className="mb-[0.75rem]">
                    <Text_12_400_B3B3B3>MAX TOKENS</Text_12_400_B3B3B3>
                    <Text_13_400_EEEEEE>{maxTokens}</Text_13_400_EEEEEE>
                  </Flex>
                  <div className="relative">
                    <input
                      type="range"
                      min="256"
                      max="4096"
                      step="256"
                      value={maxTokens}
                      onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                      className={styles.slider}
                    />
                    <div className="flex justify-between mt-[0.5rem]">
                      <Text_12_400_757575>256</Text_12_400_757575>
                      <Text_12_400_757575>4096</Text_12_400_757575>
                    </div>
                  </div>
                </div>

                {/* System Prompt */}
                <div>
                  <Text_12_400_B3B3B3 className="mb-[0.75rem]">SYSTEM PROMPT</Text_12_400_B3B3B3>
                  <TextArea
                    placeholder="Enter system prompt..."
                    rows={4}
                    className="bg-[#1F1F1F] border-[#2F2F2F] text-[#EEEEEE] placeholder-[#757575]"
                    style={{
                      background: '#1F1F1F',
                      borderColor: '#2F2F2F',
                      resize: 'none'
                    }}
                  />
                </div>

                {/* Cost Estimate */}
                <div className="mt-[1.5rem] pt-[1.5rem] border-t border-[#1F1F1F]">
                  <Text_12_400_B3B3B3 className="mb-[0.75rem]">ESTIMATED COST</Text_12_400_B3B3B3>
                  <Flex justify="space-between" className="mb-[0.5rem]">
                    <Text_12_400_757575>Input tokens</Text_12_400_757575>
                    <Text_13_400_EEEEEE>~250</Text_13_400_EEEEEE>
                  </Flex>
                  <Flex justify="space-between" className="mb-[0.5rem]">
                    <Text_12_400_757575>Output tokens</Text_12_400_757575>
                    <Text_13_400_EEEEEE>~{maxTokens}</Text_13_400_EEEEEE>
                  </Flex>
                  <Flex justify="space-between" className="pt-[0.5rem] border-t border-[#1F1F1F]">
                    <Text_12_400_B3B3B3>Total cost</Text_12_400_B3B3B3>
                    <Text_14_500_EEEEEE className="text-[#965CDE]">~$0.03</Text_14_500_EEEEEE>
                  </Flex>
                </div>
              </div>
            </div>
          </Flex>
        </div>
      </div>
    </DashboardLayout>
  );
}