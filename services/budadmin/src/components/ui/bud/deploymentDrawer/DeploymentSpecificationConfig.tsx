import React, { useContext, useEffect } from "react";

import {
  Text_14_400_EEEEEE,
  Text_12_400_757575,
  Text_12_300_EEEEEE,
} from "../../text";

import { Form, Input, Slider, Image } from "antd";
import { useDeployModel } from "src/stores/useDeployModel";
import CustomPopover from "src/flows/components/customPopover";
import { endpointNameRegex } from "@/lib/utils";
import { BudFormContext } from "../context/BudFormContext";

const DeploymentSpecificationConfig: React.FC = (props: {}) => {
  const { form } = useContext(BudFormContext);
  const {
    deploymentSpecifcation,
    setDeploymentSpecification,
    currentWorkflow,
    hardwareMode,
    selectedModel,
  } = useDeployModel();

  const isCloudModelFlow =
    currentWorkflow?.workflow_steps.model.provider_type === "cloud_model";

  // Hide context/sequence for models that don't need token-based configuration
  // (audio transcription, TTS, embedding models without chat capability)
  const hasChatEndpoint = selectedModel?.supported_endpoints?.chat?.enabled;
  const hasCompletionEndpoint = selectedModel?.supported_endpoints?.completion?.enabled;
  const hasAudioTranscription = selectedModel?.supported_endpoints?.audio_transcription?.enabled;
  const hasAudioSpeech = selectedModel?.supported_endpoints?.audio_speech?.enabled;
  const hasEmbeddingEndpoint = selectedModel?.supported_endpoints?.embedding?.enabled;

  // Hide for pure audio models (transcription/TTS) or embedding models that don't have chat/completion
  const hideContextSequence = (hasAudioTranscription || hasAudioSpeech || hasEmbeddingEndpoint) && !hasChatEndpoint && !hasCompletionEndpoint;

  // Compute max context length based on model architecture
  const getMaxContextLength = () => {
    const DEFAULT_MAX = 32000;

    // Check if audio model (has audio input capability)
    const isAudioModel = selectedModel?.modality?.audio?.input;

    if (isAudioModel && selectedModel?.architecture_audio_config) {
      const { max_source_positions, max_target_positions } =
        selectedModel.architecture_audio_config;
      // Sum both positions for total context
      const sum = (max_source_positions || 0) + (max_target_positions || 0);
      return sum > 0 ? sum : DEFAULT_MAX;
    }

    // Use text config context_length for text models
    return selectedModel?.architecture_text_config?.context_length || DEFAULT_MAX;
  };

  const maxContextLength = getMaxContextLength();

  // Sync form values with store when component mounts or store values change
  // This is needed when reopening the flow from task island
  useEffect(() => {
    if (form?.setFieldsValue && deploymentSpecifcation) {
      const values = {
        deployment_name: deploymentSpecifcation.deployment_name,
        concurrent_requests: deploymentSpecifcation.concurrent_requests,
        avg_context_length: deploymentSpecifcation.avg_context_length,
        avg_sequence_length: deploymentSpecifcation.avg_sequence_length,
      };
      form.setFieldsValue(values);
      // Clear any existing validation errors after setting values
      form.validateFields?.(['deployment_name', 'concurrent_requests']).catch(() => {});
    }
  }, [form, deploymentSpecifcation.deployment_name, deploymentSpecifcation.concurrent_requests]);

  // Clamp values when maxContextLength changes (e.g., when model is selected)
  useEffect(() => {
    if (!selectedModel || maxContextLength === 32000) return;

    const currentContext = deploymentSpecifcation.avg_context_length || 0;
    const currentSequence = deploymentSpecifcation.avg_sequence_length || 0;

    const updates: Partial<typeof deploymentSpecifcation> = {};

    if (currentContext > maxContextLength) {
      updates.avg_context_length = maxContextLength;
    }

    if (currentSequence > maxContextLength) {
      updates.avg_sequence_length = maxContextLength;
    }

    if (Object.keys(updates).length > 0) {
      setDeploymentSpecification({
        ...deploymentSpecifcation,
        ...updates,
      });
    }
  }, [maxContextLength, selectedModel?.id]);

  return (
    <div className="flex flex-col	justify-start items-center w-full">
      <div className="w-full p-[1.35rem] pb-[1.1rem] border-b border-[#1F1F1F]">
        <Text_14_400_EEEEEE>Set Deployment Specifications</Text_14_400_EEEEEE>
        <Text_12_400_757575 className="mt-[.5rem]">
          Enter these specifications to optimize performance based on your
          requirements.
        </Text_12_400_757575>
      </div>
      <div className="px-[1.4rem] pt-[2.15rem] w-full">
        <div className="flex gap-[1.5rem] w-full flex-row mb-[1.3rem]">
          <div className="w-[48%] relative">
            <Text_12_300_EEEEEE className="absolute px-1.5 bg-[#101010] -top-1.5 left-1.5 tracking-[.035rem] z-10 flex items-center gap-1 text-[.75rem] text-[#EEEEEE] font-[400]">
              Deployment&nbsp;Name
              <CustomPopover title="A unique name to identify your deployment.">
                <Image
                  preview={false}
                  src="/images/info.png"
                  alt="info"
                  style={{ width: ".75rem" }}
                />
              </CustomPopover>
            </Text_12_300_EEEEEE>
            <Form.Item
              hasFeedback
              name={"deployment_name"}
              className={`flex items-start rounded-[6px] relative !bg-[transparent] mb-[0]`}
              rules={[
                {
                  required: true,
                  message: "Please enter deployment name",
                },
                {
                  max: 50,
                  message: "Deployment name should be less than 50 characters",
                },
                {
                  pattern: endpointNameRegex,
                  message:
                    "Deployment name should contain only alphanumeric characters and hyphens",
                },
              ]}
            >
              <Input
                placeholder="Name Your Deployment"
                style={{
                  backgroundColor: "transparent",
                  color: "#EEEEEE",
                  border: "0.5px solid #757575",
                }}
                size="large"
                value={deploymentSpecifcation.deployment_name}
                onChange={(e) => {
                  form.setFieldsValue({ deployment_name: e.target.value });
                  form.validateFields(["deployment_name"]);
                  setDeploymentSpecification({
                    ...deploymentSpecifcation,
                    deployment_name: e.target.value,
                  });
                }}
                className="drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
              />
            </Form.Item>
          </div>
          <div className="w-[48%] relative">
            <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
              Concurrent&nbsp;Request
              <CustomPopover title="The number of requests you want the model to handle at the same time.">
                <Image
                  preview={false}
                  src="/images/info.png"
                  alt="info"
                  style={{ width: ".75rem", height: ".75rem" }}
                />
              </CustomPopover>
            </Text_12_300_EEEEEE>
            <Form.Item
              name={"concurrent_requests"}
              hasFeedback
              rules={[
                {
                  required: true,
                  message: "Please enter concurrent requests",
                },
                {
                  validator: (_, value) => {
                    const num = Number(value);
                    if (isNaN(num) || num < 1) {
                      return Promise.reject("Concurrent requests should be greater than 0");
                    }
                    return Promise.resolve();
                  },
                },
              ]}
              className={`flex items-start rounded-[6px] relative !bg-[transparent] mb-[0]`}
            >
              <Input
                type="number"
                placeholder="Enter value"
                style={{
                  backgroundColor: "transparent",
                  color: "#EEEEEE",
                  border: "0.5px solid #757575",
                }}
                min={1}
                value={deploymentSpecifcation.concurrent_requests}
                onChange={(e) => {
                  form.setFieldsValue({ concurrent_requests: e.target.value });
                  form.validateFields(["concurrent_requests"]);
                  if (
                    e.target.value.startsWith("0") &&
                    e.target.value.length > 1
                  ) {
                    e.target.value = e.target.value.slice(1);
                  }
                  setDeploymentSpecification({
                    ...deploymentSpecifcation,
                    concurrent_requests: e.target.value,
                  });
                }}
                size="large"
                className="drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
              />
            </Form.Item>
          </div>
        </div>
        {!hideContextSequence && (
        <div className="flex gap-[1rem] w-full flex-row">
          <div className="w-full relative">
            <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1">
              Context&nbsp;Length
              <CustomPopover title="The maximum input length you want the model can process.">
                <Image
                  preview={false}
                  src="/images/info.png"
                  alt="info"
                  style={{ width: ".75rem", height: ".75rem" }}
                />
              </CustomPopover>
            </Text_12_300_EEEEEE>
            <Form.Item name={"avg_context_length"} hasFeedback>
              <div className="flex items-end justify-center mt-[.8rem] gap-[.75rem]">
                <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                  30
                </div>
                <Slider
                  className="budSlider mt-10 w-full"
                  min={30}
                  max={maxContextLength}
                  step={1}
                  value={deploymentSpecifcation.avg_context_length}
                  onChange={(value) => {
                    setDeploymentSpecification({
                      ...deploymentSpecifcation,
                      avg_context_length: value,
                    });
                  }}
                  tooltip={{
                    open: true,
                    getPopupContainer: (trigger) =>
                      (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
                  }}
                  styles={{
                    track: {
                      backgroundColor: "#965CDE",
                    },
                    rail: {
                      backgroundColor: "#212225",
                      height: 4,
                    },
                  }}
                />
                <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                  {maxContextLength.toLocaleString()}
                </div>
                <div className="mb-[.1rem]">
                  <Input
                    name="ContextLength"
                    style={{
                      width: "4.5rem",
                      height: "2rem",
                    }}
                    value={deploymentSpecifcation.avg_context_length}
                    onChange={(e) => {
                      // perform regex check
                      const value = e.target.value;

                      if (value === "" || /^\d+$/.test(value)) {
                        const val = parseInt(value);
                        if (
                          true ||
                          value === "" ||
                          (val >= 30 && val <= maxContextLength)
                        ) {
                          setDeploymentSpecification({
                            ...deploymentSpecifcation,
                            avg_context_length: value,
                          });
                        }
                      }
                    }}
                    onBlur={(e) => {
                      let value = parseInt(e.target.value, 10) || 0;

                      // If value is below 30, reset it to 30
                      if (value < 30) {
                        setDeploymentSpecification({
                          ...deploymentSpecifcation,
                          avg_context_length: "30",
                        });
                      }
                    }}
                    type="text"
                    className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                  />
                </div>
              </div>
            </Form.Item>
          </div>
        </div>
        )}
        {!hideContextSequence && (
        <div className="flex gap-[1rem] w-full flex-row">
          <div className="w-full relative">
            <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1">
              Sequence&nbsp;Length
              <CustomPopover title="The maximum sequence length you want the model can process.">
                <Image
                  preview={false}
                  src="/images/info.png"
                  alt="info"
                  style={{ width: ".75rem", height: ".75rem" }}
                />
              </CustomPopover>
            </Text_12_300_EEEEEE>
            <Form.Item name={"avg_sequence_length"} hasFeedback>
              <div className="flex items-end justify-center mt-[.8rem] gap-[.75rem]">
                <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                  10
                </div>
                <Slider
                  className="budSlider mt-10 w-full"
                  min={10}
                  max={maxContextLength}
                  step={1}
                  value={deploymentSpecifcation.avg_sequence_length}
                  onChange={(value) => {
                    setDeploymentSpecification({
                      ...deploymentSpecifcation,
                      avg_sequence_length: value,
                    });
                  }}
                  tooltip={{
                    open: true,
                    getPopupContainer: (trigger) =>
                      (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
                  }}
                  styles={{
                    track: {
                      backgroundColor: "#965CDE",
                    },
                    rail: {
                      backgroundColor: "#212225",
                      height: 4,
                    },
                  }}
                />
                <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                  {maxContextLength.toLocaleString()}
                </div>
                <div className="mb-[.1rem]">
                  <Input
                    name="SequenceLength"
                    style={{
                      width: "4.5rem",
                      height: "2rem",
                    }}
                    value={deploymentSpecifcation.avg_sequence_length}
                    onChange={(event) => {
                      // perform regex check
                      const value = event.target.value;

                      if (value === "" || /^\d+$/.test(value)) {
                        const val = parseInt(value);
                        if (
                          true ||
                          value === "" ||
                          (val >= 10 && val <= maxContextLength)
                        ) {
                          setDeploymentSpecification({
                            ...deploymentSpecifcation,
                            avg_sequence_length: value,
                          });
                        }
                      }
                    }}
                    onBlur={(e) => {
                      let value = parseInt(e.target.value, 10) || 0;

                      // If value is below 30, reset it to 30
                      if (value < 10) {
                        setDeploymentSpecification({
                          ...deploymentSpecifcation,
                          avg_sequence_length: "10",
                        });
                      }
                    }}
                    type="text"
                    className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                  />
                </div>
              </div>
            </Form.Item>
          </div>
        </div>
        )}
        {!isCloudModelFlow && hardwareMode === "dedicated" && !hideContextSequence && (
          <>
            <div className="flex gap-[1rem] w-full flex-row">
              <div className="w-full">
                <Form.Item name={"tokens_per_sec"} hasFeedback>
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 break-keep">
                    Per&#8209;Session&nbsp;Tokens/Sec
                    <CustomPopover title="The number of tokens you want processed per session, it affects the throughput">
                      <Image
                        preview={false}
                        src="/images/info.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </CustomPopover>
                  </Text_12_300_EEEEEE>
                  <div className="flex items-end justify-center mt-[.8rem] gap-[.75rem]">
                    <div className="mb-[.1rem]">
                      <Input
                        defaultValue={
                          deploymentSpecifcation.per_session_tokens_per_sec[0]
                        }
                        name="PerSessionStart"
                        style={{
                          width: "3.125rem",
                          height: "2rem",
                        }}
                        value={
                          deploymentSpecifcation.per_session_tokens_per_sec[0]
                        }
                        onChange={(e) => {
                          // check for regex and min 5 max   100
                          const value = e.target.value;

                          if (value === "" || /^\d+$/.test(value)) {
                            const val = parseInt(value);
                            if (
                              true ||
                              value === "" ||
                              (val >= 5 && val <= 100)
                            ) {
                              setDeploymentSpecification({
                                ...deploymentSpecifcation,
                                per_session_tokens_per_sec: [
                                  e.target.value,
                                  deploymentSpecifcation
                                    .per_session_tokens_per_sec[1],
                                ],
                              });
                            }
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value) || 0;

                          // If value is less than 50, reset it to 50
                          if (value < 5) {
                            setDeploymentSpecification({
                              ...deploymentSpecifcation,
                              per_session_tokens_per_sec: [
                                "5",
                                deploymentSpecifcation
                                  .per_session_tokens_per_sec[1],
                              ],
                            });
                          }
                        }}
                        type="text"
                        className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                      />
                    </div>
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      5
                    </div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={5}
                      max={100}
                      step={1}
                      value={deploymentSpecifcation.per_session_tokens_per_sec}
                      onChange={(value) => {
                        setDeploymentSpecification({
                          ...deploymentSpecifcation,
                          per_session_tokens_per_sec: value,
                        });
                      }}
                      range={{ editable: true, minCount: 1, maxCount: 2 }}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
                      }}
                      styles={{
                        track: {
                          backgroundColor: "#965CDE",
                        },
                        rail: {
                          backgroundColor: "#212225",
                          height: 4,
                        },
                      }}
                    />

                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      100
                    </div>
                    <div className="mb-[.1rem]">
                      <Input
                        name="PerSessionEnd"
                        style={{
                          width: "3.125rem",
                          height: "2rem",
                        }}
                        value={
                          deploymentSpecifcation.per_session_tokens_per_sec[1]
                        }
                        onChange={(e) => {
                          const value = e.target.value;

                          if (value === "" || /^\d+$/.test(value)) {
                            const val = parseInt(value);
                            if (
                              true ||
                              value === "" ||
                              (val >= 5 && val <= 100)
                            ) {
                              setDeploymentSpecification({
                                ...deploymentSpecifcation,
                                per_session_tokens_per_sec: [
                                  deploymentSpecifcation
                                    .per_session_tokens_per_sec[0],
                                  e.target.value,
                                ],
                              });
                            }
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value) || 0;

                          // If value is less than 5, reset it to 5
                          if (value < 5) {
                            setDeploymentSpecification({
                              ...deploymentSpecifcation,
                              per_session_tokens_per_sec: [
                                deploymentSpecifcation
                                  .per_session_tokens_per_sec[0],
                                "5",
                              ],
                            });
                          }
                        }}
                        type="text"
                        className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                      />
                    </div>
                  </div>
                </Form.Item>
              </div>
            </div>
            <div className="flex gap-[1rem] w-full flex-row">
              <div className="w-full">
                <Form.Item>
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1">
                    TTFT(ms)
                    <CustomPopover title="Time to first token. The time it takes to start generating the first token after a request is made. ">
                      <Image
                        preview={false}
                        src="/images/info.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </CustomPopover>
                  </Text_12_300_EEEEEE>
                  <div className="flex items-end justify-center mt-[.8rem] gap-[.75rem]">
                    <div className="mb-[.1rem]">
                      <Input
                        defaultValue={deploymentSpecifcation.ttft[0]}
                        name="TTFTStart"
                        style={{
                          width: "3.125rem",
                          height: "2rem",
                        }}
                        min={50}
                        value={deploymentSpecifcation.ttft[0]}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            const val = parseInt(value);
                            if (
                              true ||
                              value === "" ||
                              (val >= 50 && val <= 5000)
                            ) {
                              setDeploymentSpecification({
                                ...deploymentSpecifcation,
                                ttft: [
                                  e.target.value,
                                  deploymentSpecifcation.ttft[1],
                                ],
                              });
                            }
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value) || 0;

                          // If value is less than 50, reset it to 50
                          if (value < 50) {
                            setDeploymentSpecification({
                              ...deploymentSpecifcation,
                              ttft: ["50", deploymentSpecifcation.ttft[1]],
                            });
                          }
                        }}
                        type="text"
                        className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                      />
                    </div>
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      50
                    </div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={50}
                      max={5000}
                      step={1}
                      value={deploymentSpecifcation.ttft}
                      onChange={(value) => {
                        setDeploymentSpecification({
                          ...deploymentSpecifcation,
                          ttft: value,
                        });
                      }}
                      range={{ editable: true, minCount: 1, maxCount: 2 }}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
                      }}
                      styles={{
                        track: {
                          backgroundColor: "#965CDE",
                        },
                        rail: {
                          backgroundColor: "#212225",
                          height: 4,
                        },
                      }}
                    />
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      5000
                    </div>
                    <div className="mb-[.1rem]">
                      <Input
                        defaultValue={deploymentSpecifcation.ttft[1]}
                        name="TTFTEnd"
                        style={{
                          width: "3.125rem",
                          height: "2rem",
                        }}
                        value={deploymentSpecifcation.ttft[1]}
                        onChange={(e) => {
                          const value = e.target.value;

                          if (value === "" || /^\d+$/.test(value)) {
                            const val = parseInt(value);
                            if (
                              true ||
                              value === "" ||
                              (val >= 50 && val <= 5000)
                            ) {
                              setDeploymentSpecification({
                                ...deploymentSpecifcation,
                                ttft: [
                                  deploymentSpecifcation.ttft[0],
                                  e.target.value,
                                ],
                              });
                            }
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value) || 0;

                          // If value is less than 5, reset it to 5
                          if (value < 300) {
                            setDeploymentSpecification({
                              ...deploymentSpecifcation,
                              ttft: [deploymentSpecifcation.ttft[0], "300"],
                            });
                          }
                        }}
                        type="text"
                        className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                      />
                    </div>
                  </div>
                </Form.Item>
              </div>
            </div>
            <div className="flex gap-[1rem] w-full flex-row">
              <div className="w-full">
                <Form.Item>
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 text-nowrap">
                    End to end latency(s)
                    <CustomPopover title="Time to complete a request from start to end.">
                      <Image
                        preview={false}
                        src="/images/info.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </CustomPopover>
                  </Text_12_300_EEEEEE>
                  <div className="flex items-end justify-center mt-[.8rem] gap-[.75rem]">
                    <div className="mb-[.1rem]">
                      <Input
                        defaultValue={deploymentSpecifcation.e2e_latency[0]}
                        name="EndToEndStart"
                        style={{
                          width: "3.125rem",
                          height: "2rem",
                        }}
                        value={deploymentSpecifcation.e2e_latency[0]}
                        onChange={(e) => {
                          const value = e.target.value;

                          if (value === "" || /^\d+$/.test(value)) {
                            const val = parseInt(value);
                            if (
                              true ||
                              value === "" ||
                              (val >= 1 && val <= 300)
                            ) {
                              setDeploymentSpecification({
                                ...deploymentSpecifcation,
                                e2e_latency: [
                                  e.target.value,
                                  deploymentSpecifcation.e2e_latency[1],
                                ],
                              });
                            }
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value) || 0;

                          // If value is less than 50, reset it to 50
                          if (value < 1) {
                            setDeploymentSpecification({
                              ...deploymentSpecifcation,
                              e2e_latency: [
                                "1",
                                deploymentSpecifcation.e2e_latency[1],
                              ],
                            });
                          }
                        }}
                        type="text"
                        className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                      />
                    </div>
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      1
                    </div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={1}
                      max={300}
                      step={1}
                      value={deploymentSpecifcation.e2e_latency}
                      onChange={(value) => {
                        setDeploymentSpecification({
                          ...deploymentSpecifcation,
                          e2e_latency: value,
                        });
                      }}
                      range={{ editable: true, minCount: 1, maxCount: 2 }}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
                      }}
                      styles={{
                        track: {
                          backgroundColor: "#965CDE",
                        },
                        rail: {
                          backgroundColor: "#212225",
                          height: 4,
                        },
                      }}
                    />
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      300
                    </div>
                    <div className="mb-[.1rem]">
                      <Input
                        defaultValue={deploymentSpecifcation.e2e_latency[1]}
                        name="EndToEndEnd"
                        style={{
                          width: "3.125rem",
                          height: "2rem",
                        }}
                        value={deploymentSpecifcation.e2e_latency[1]}
                        onChange={(e) => {
                          const value = e.target.value;

                          if (value === "" || /^\d+$/.test(value)) {
                            const val = parseInt(value);
                            if (
                              true ||
                              value === "" ||
                              (val >= 1 && val <= 300)
                            ) {
                              setDeploymentSpecification({
                                ...deploymentSpecifcation,
                                e2e_latency: [
                                  deploymentSpecifcation.e2e_latency[0],
                                  e.target.value,
                                ],
                              });
                            }
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value) || 0;

                          // If value is less than 5, reset it to 5
                          if (value < 1) {
                            setDeploymentSpecification({
                              ...deploymentSpecifcation,
                              e2e_latency: [
                                deploymentSpecifcation.e2e_latency[0],
                                "1",
                              ],
                            });
                          }
                        }}
                        type="text"
                        className={`inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]`}
                      />
                    </div>
                  </div>
                </Form.Item>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default DeploymentSpecificationConfig;
