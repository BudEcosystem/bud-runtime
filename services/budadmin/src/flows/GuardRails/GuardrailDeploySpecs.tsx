import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Slider, Image } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import useGuardrails from "src/hooks/useGuardrails";
import { errorToast } from "@/components/toast";
import CustomPopover from "src/flows/components/customPopover";
import {
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";

const inputBoxClass =
  "inputClass border border-[#EEEEEE] px-[.5rem] text-center pt-[.3rem] pb-[.15rem] rounded-[0.31275rem] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] text-[#EEE] text-[0.75rem] font-[400] leading-[100%]";

const textInputClass =
  "drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]";

const sliderStyles = {
  track: { backgroundColor: "#965CDE" },
  rail: { backgroundColor: "#212225", height: 4 },
};

export default function GuardrailDeploySpecs() {
  const { openDrawerWithStep } = useDrawer();
  const { updateWorkflow, workflowLoading, setDeployConfig } = useGuardrails();

  const [avgContextLength, setAvgContextLength] = useState<string | number>(4096);
  const [avgSequenceLength, setAvgSequenceLength] = useState<string | number>(128);
  const [concurrentRequests, setConcurrentRequests] = useState<string | number>(10);
  const [ttft, setTtft] = useState<[number | string, number | string]>([50, 200]);
  const [e2eLatency, setE2eLatency] = useState<[number | string, number | string]>([100, 500]);
  const [tokensPerSec, setTokensPerSec] = useState<[number | string, number | string]>([10, 50]);

  const handleBack = () => {
    openDrawerWithStep("guardrail-hardware-mode");
  };

  const handleNext = async () => {
    const ttftMin = Number(ttft[0]);
    const ttftMax = Number(ttft[1]);
    const e2eMin = Number(e2eLatency[0]);
    const e2eMax = Number(e2eLatency[1]);
    const tpsMin = Number(tokensPerSec[0]);
    const tpsMax = Number(tokensPerSec[1]);

    if (ttftMin > ttftMax) {
      errorToast("TTFT min must be less than max");
      return;
    }
    if (e2eMin > e2eMax) {
      errorToast("E2E latency min must be less than max");
      return;
    }
    if (tpsMin > tpsMax) {
      errorToast("Tokens/sec min must be less than max");
      return;
    }

    const config = {
      avg_context_length: Number(avgContextLength),
      avg_sequence_length: Number(avgSequenceLength),
      concurrent_requests: Number(concurrentRequests),
      ttft: [ttftMin, ttftMax] as [number, number],
      e2e_latency: [e2eMin, e2eMax] as [number, number],
      per_session_tokens_per_sec: [tpsMin, tpsMax] as [number, number],
    };

    setDeployConfig(config);

    const success = await updateWorkflow({
      step_number: 9,
      deploy_config: config,
    });

    if (success) {
      openDrawerWithStep("guardrail-simulation-status");
    }
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Run Simulation"
      disableNext={workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Deployment Specifications"
            description="Configure the deployment specifications for the guardrail model simulation."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center w-full">
            <div className="w-full p-[1.35rem] pb-[1.1rem] border-b border-[#1F1F1F]">
              <Text_14_400_EEEEEE>Set Deployment Specifications</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.5rem]">
                Enter these specifications to optimize performance based on your
                requirements.
              </Text_12_400_757575>
            </div>
            <div className="px-[1.4rem] pt-[2.15rem] pb-[2.15rem] w-full">
              {/* Concurrent Requests & Context/Sequence Length */}
              <div className="flex gap-[1.5rem] w-full flex-row mb-[1.3rem]">
                <div className="w-[48%] relative">
                  <Text_12_300_EEEEEE className="absolute px-1.5 bg-[#101010] -top-1.5 left-1.5 tracking-[.035rem] z-10 flex items-center gap-1 text-[.75rem] text-[#EEEEEE] font-[400]">
                    Concurrent&nbsp;Requests
                    <CustomPopover title="The number of requests you want the model to handle at the same time.">
                      <Image
                        preview={false}
                        src="/images/info.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </CustomPopover>
                  </Text_12_300_EEEEEE>
                  <Input
                    type="number"
                    placeholder="Enter value"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                      border: "0.5px solid #757575",
                    }}
                    min={1}
                    value={concurrentRequests}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (value === "" || /^\d+$/.test(value)) {
                        setConcurrentRequests(value === "" ? "" : value);
                      }
                    }}
                    onBlur={(e) => {
                      const value = parseInt(e.target.value, 10) || 0;
                      if (value < 1) setConcurrentRequests(1);
                    }}
                    size="large"
                    className={textInputClass}
                  />
                </div>
              </div>

              {/* Context Length Slider */}
              <div className="flex gap-[1rem] w-full flex-row">
                <div className="w-full relative">
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1">
                    Context&nbsp;Length
                    <CustomPopover title="The maximum input length the model can process.">
                      <Image
                        preview={false}
                        src="/images/info.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </CustomPopover>
                  </Text_12_300_EEEEEE>
                  <div className="flex items-end justify-center mt-[.8rem] gap-[.75rem]">
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      30
                    </div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={30}
                      max={131072}
                      step={1}
                      value={Number(avgContextLength) || 30}
                      onChange={(value: number) => setAvgContextLength(value)}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body,
                      }}
                      styles={sliderStyles}
                    />
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      131072
                    </div>
                    <div className="mb-[.1rem]">
                      <Input
                        style={{ width: "4.5rem", height: "2rem" }}
                        value={avgContextLength}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setAvgContextLength(value === "" ? "" : value);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 30) setAvgContextLength(30);
                          else if (value > 131072) setAvgContextLength(131072);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Sequence Length Slider */}
              <div className="flex gap-[1rem] w-full flex-row">
                <div className="w-full relative">
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1">
                    Sequence&nbsp;Length
                    <CustomPopover title="The maximum sequence length the model can process.">
                      <Image
                        preview={false}
                        src="/images/info.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </CustomPopover>
                  </Text_12_300_EEEEEE>
                  <div className="flex items-end justify-center mt-[.8rem] gap-[.75rem]">
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      10
                    </div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={10}
                      max={131072}
                      step={1}
                      value={Number(avgSequenceLength) || 10}
                      onChange={(value: number) => setAvgSequenceLength(value)}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body,
                      }}
                      styles={sliderStyles}
                    />
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">
                      131072
                    </div>
                    <div className="mb-[.1rem]">
                      <Input
                        style={{ width: "4.5rem", height: "2rem" }}
                        value={avgSequenceLength}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setAvgSequenceLength(value === "" ? "" : value);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 10) setAvgSequenceLength(10);
                          else if (value > 131072) setAvgSequenceLength(131072);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* TTFT Range Slider */}
              <div className="flex gap-[1rem] w-full flex-row">
                <div className="w-full">
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 break-keep">
                    TTFT&nbsp;(ms)
                    <CustomPopover title="Time to first token. The time it takes to start generating the first token after a request is made.">
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
                        style={{ width: "3.125rem", height: "2rem" }}
                        value={ttft[0]}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setTtft([value === "" ? "" : value, ttft[1]]);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 1) setTtft([1, ttft[1]]);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">1</div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={1}
                      max={10000}
                      step={1}
                      value={[Number(ttft[0]) || 1, Number(ttft[1]) || 1]}
                      onChange={(value: number[]) => setTtft(value as [number, number])}
                      range={{ editable: true, minCount: 1, maxCount: 2 }}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body,
                      }}
                      styles={sliderStyles}
                    />
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">10000</div>
                    <div className="mb-[.1rem]">
                      <Input
                        style={{ width: "3.125rem", height: "2rem" }}
                        value={ttft[1]}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setTtft([ttft[0], value === "" ? "" : value]);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 1) setTtft([ttft[0], 1]);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* E2E Latency Range Slider */}
              <div className="flex gap-[1rem] w-full flex-row">
                <div className="w-full">
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 text-nowrap">
                    End&#8209;to&#8209;End&nbsp;Latency&nbsp;(ms)
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
                        style={{ width: "3.125rem", height: "2rem" }}
                        value={e2eLatency[0]}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setE2eLatency([value === "" ? "" : value, e2eLatency[1]]);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 1) setE2eLatency([1, e2eLatency[1]]);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">1</div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={1}
                      max={30000}
                      step={1}
                      value={[Number(e2eLatency[0]) || 1, Number(e2eLatency[1]) || 1]}
                      onChange={(value: number[]) => setE2eLatency(value as [number, number])}
                      range={{ editable: true, minCount: 1, maxCount: 2 }}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body,
                      }}
                      styles={sliderStyles}
                    />
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">30000</div>
                    <div className="mb-[.1rem]">
                      <Input
                        style={{ width: "3.125rem", height: "2rem" }}
                        value={e2eLatency[1]}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setE2eLatency([e2eLatency[0], value === "" ? "" : value]);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 1) setE2eLatency([e2eLatency[0], 1]);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Tokens Per Second Range Slider */}
              <div className="flex gap-[1rem] w-full flex-row">
                <div className="w-full">
                  <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 break-keep">
                    Per&#8209;Session&nbsp;Tokens/Sec
                    <CustomPopover title="The number of tokens processed per session. Affects throughput.">
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
                        style={{ width: "3.125rem", height: "2rem" }}
                        value={tokensPerSec[0]}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setTokensPerSec([value === "" ? "" : value, tokensPerSec[1]]);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 1) setTokensPerSec([1, tokensPerSec[1]]);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">1</div>
                    <Slider
                      className="budSlider mt-10 w-full"
                      min={1}
                      max={1000}
                      step={1}
                      value={[Number(tokensPerSec[0]) || 1, Number(tokensPerSec[1]) || 1]}
                      onChange={(value: number[]) => setTokensPerSec(value as [number, number])}
                      range={{ editable: true, minCount: 1, maxCount: 2 }}
                      tooltip={{
                        open: true,
                        getPopupContainer: (trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body,
                      }}
                      styles={sliderStyles}
                    />
                    <div className="text-[#757575] text-[.75rem] h-[1.6rem]">1000</div>
                    <div className="mb-[.1rem]">
                      <Input
                        style={{ width: "3.125rem", height: "2rem" }}
                        value={tokensPerSec[1]}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "" || /^\d+$/.test(value)) {
                            setTokensPerSec([tokensPerSec[0], value === "" ? "" : value]);
                          }
                        }}
                        onBlur={(e) => {
                          let value = parseInt(e.target.value, 10) || 0;
                          if (value < 1) setTokensPerSec([tokensPerSec[0], 1]);
                        }}
                        type="text"
                        className={inputBoxClass}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
