import React from "react";
import { Checkbox, Image, Progress } from "antd";
import CustomPopover from "src/flows/components/customPopover";
import {
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_12_400_EEEEEE,
  Text_12_400_757575,
} from "@/components/ui/text";
import Tags from "src/flows/components/DrawerTags";
import { formatCost } from "@/utils/formatters";

// Safely extract numeric value from a benchmark field that can be a plain number or {label, value}
function getBenchmarkValue(bench: any): number | undefined {
  if (bench === undefined || bench === null) return undefined;
  if (typeof bench === "number") return bench;
  if (typeof bench === "object" && bench.value !== undefined) return bench.value;
  return undefined;
}

function getBenchmarkLabel(bench: any): string | undefined {
  if (typeof bench === "object" && bench?.label) return bench.label;
  return undefined;
}

function PerformanceTag({ label }: { label: string }) {
  let color = "";
  let textColor = "";
  switch (label) {
    case "Better":
      color = "bg-[#86541A33]";
      textColor = "text-[#ECAE75]";
      break;
    case "Worse":
      color = "bg-[#861A1A33]";
      textColor = "text-[#EC7575]";
      break;
    case "Expected":
      color = "bg-[#14581340]";
      textColor = "text-[#3EC564]";
      break;
    default:
      color = "";
      textColor = "";
      break;
  }

  return (
    <div
      className={`text-align-center font-[400] text-[0.625rem] px-[.2rem] py-[.15rem] px-[.3rem] rounded-[6px] ${color} ${textColor}`}
    >
      {label}
    </div>
  );
}

function PerformanceItem({
  label,
  value,
  tag,
  progress,
  fullWidth,
}: {
  label: string;
  value: string;
  tag?: string;
  progress?: number;
  fullWidth?: boolean;
}) {
  let icon = "/images/drawer/tag.png";
  if (label === "E2E Latency") {
    icon = "/images/drawer/per.png";
  }

  return (
    <div
      className={`w-[${fullWidth ? "100%" : "48%"}] flex items-center justify-start mb-[1.25rem]`}
    >
      <div className="w-[75%] flex justify-start align-center">
        <div className="h-[.75rem] flex justify-start align-center">
          <Image
            preview={false}
            src={icon}
            alt="info"
            style={{ width: ".75rem" }}
          />
        </div>
        <Text_12_400_B3B3B3 className="ml-[.4rem] max-w-[80%]">
          {label}
        </Text_12_400_B3B3B3>
      </div>
      <Text_12_400_EEEEEE className="min-w-[45px] flex-shrink-0 flex justify-start items-center">
        {value}
      </Text_12_400_EEEEEE>
      <div className="min-w-[55px] flex flex-shrink-0 justify-start items-center">
        {tag && <PerformanceTag label={tag} />}
        {progress && (
          <Progress
            strokeLinecap="butt"
            percent={progress}
            showInfo={false}
            size={{ height: 4 }}
            strokeColor={"#965CDE"}
            trailColor={"#1F1F1F"}
          />
        )}
      </div>
    </div>
  );
}

function GuardrailClusterDetail({ data }: { data: any }) {
  const benchmark = data.benchmarks || ({} as any);

  const replicas = getBenchmarkValue(benchmark.replicas);
  const replicasLabel = getBenchmarkLabel(benchmark.replicas);
  const e2e_latency = getBenchmarkValue(benchmark.e2e_latency);
  const e2eLabel = getBenchmarkLabel(benchmark.e2e_latency);
  const ttft = getBenchmarkValue(benchmark.ttft);
  const ttftLabel = getBenchmarkLabel(benchmark.ttft);
  const over_all_throughput = getBenchmarkValue(benchmark.over_all_throughput);
  const throughputLabel = getBenchmarkLabel(benchmark.over_all_throughput);
  const per_session_tokens_per_sec = getBenchmarkValue(benchmark.per_session_tokens_per_sec);
  const perSessionLabel = getBenchmarkLabel(benchmark.per_session_tokens_per_sec);
  const concurrency = getBenchmarkValue(benchmark.concurrency);
  const concurrencyLabel = getBenchmarkLabel(benchmark.concurrency);

  const benchmarkData = [
    { label: "Workers", value: replicas, tag: replicasLabel },
    { label: "E2E Latency", value: e2e_latency, tag: e2eLabel },
    { label: "TTFT(ms)", value: ttft, tag: ttftLabel },
    { label: "Overall token per sec", value: over_all_throughput, tag: throughputLabel },
    { label: "Per session token per sec", value: per_session_tokens_per_sec, tag: perSessionLabel },
    { label: "Concurrency", value: concurrency, tag: concurrencyLabel },
  ].filter(
    (item) =>
      item.value !== null && item.value !== undefined && !isNaN(item.value),
  );

  const resourceDetails = Array.isArray(data.resource_details)
    ? data.resource_details
    : [];

  const requiredDevices = Array.isArray(data.required_devices)
    ? data.required_devices
    : [];

  return (
    <div className="flex flex-col justify-start items-center w-full mb-[1rem]">
      {resourceDetails.length > 0 && (
        <div className="runningOn w-full rounded-[6px] mt-[1.2rem] border-b-[1px] border-[#282828] bg-[#FFFFFF08]">
          <div className="flex justify-start items-center px-[.75rem] pt-[.7rem] pb-[.4rem]">
            <Text_14_600_EEEEEE className="mr-[.35rem]">
              Hardware
            </Text_14_600_EEEEEE>
            <div className="w-[.75rem] w-[.75rem]">
              <CustomPopover title="Below is the hardware details of the cluster">
                <Image
                  preview={false}
                  width={12}
                  src="/images/drawer/info.png"
                  alt="Logo"
                />
              </CustomPopover>
            </div>
          </div>
          <div className="flex justify-start items-center w-full px-[.75rem] pt-[0] pb-[.6rem] border-b-[1px] border-b-[#282828]">
            <Text_12_400_757575>
              Below is the hardware details of the cluster
            </Text_12_400_757575>
          </div>
          <div className="flex flex-wrap justify-between w-full mt-[0.4rem] px-[.75rem] pt-[.7rem] pb-[.4rem]">
            {resourceDetails.map((item: any, index: number) => (
              <PerformanceItem
                key={index}
                label={`Available ${item.type} / Total ${item.type}`}
                value={`${item.available} / ${item.total}`}
                progress={Math.round((item.available / item.total) * 100)}
                fullWidth={true}
              />
            ))}
          </div>
        </div>
      )}
      {requiredDevices.length > 0 && (
        <div className="runningOn w-full rounded-[6px] mt-[1.2rem] bg-[#FFFFFF08]">
          <div className="flex justify-start items-center border-b-[1px] border-[#282828] px-[.75rem] pt-[.7rem] pb-[.4rem]">
            <Text_14_600_EEEEEE className="mr-[.35rem]">
              Running On
            </Text_14_600_EEEEEE>
            <div className="w-[.75rem] w-[.75rem]">
              <CustomPopover title="Below is the hardware will be used to run your guardrail models">
                <Image
                  preview={false}
                  width={12}
                  src="/images/drawer/info.png"
                  alt="Logo"
                />
              </CustomPopover>
            </div>
          </div>
          <div className="flex justify-start items-center w-full px-[.75rem] pt-[.9rem] pb-[.9rem]">
            {requiredDevices.map((device: any, index: number) => {
              const replicaVal = replicas || 1;
              return (
                <div
                  key={index}
                  className="rounded-[6px] text-[#D1B854] text-[0.625rem] font-[400] bg-[#423A1A40] px-[.3rem] py-[.15rem] mr-[.4rem]"
                >
                  Running{" "}
                  {Math.round(
                    (device?.num_replicas / replicaVal) * 100,
                  )}
                  % on {device?.device_type?.toUpperCase()}
                </div>
              );
            })}
          </div>
        </div>
      )}
      {benchmarkData.length > 0 && (
        <div className="runningOn w-full rounded-[6px] mt-[1.2rem] border-b-[1px] border-[#282828] bg-[#FFFFFF08]">
          <div className="flex justify-start items-center px-[.75rem] pt-[.7rem] pb-[.4rem]">
            <Text_14_600_EEEEEE className="mr-[.35rem]">
              Performance
            </Text_14_600_EEEEEE>
            <div className="w-[.75rem] w-[.75rem]">
              <CustomPopover title="This is the performance you will get on this cluster">
                <Image
                  preview={false}
                  width={12}
                  src="/images/drawer/info.png"
                  alt="Logo"
                />
              </CustomPopover>
            </div>
          </div>
          <div className="flex justify-start items-center w-full px-[.75rem] pt-[0] pb-[.6rem] border-b-[1px] border-b-[#282828]">
            <Text_12_400_757575>
              Below is the performance you will get on this cluster
            </Text_12_400_757575>
          </div>
          <div className="flex flex-wrap justify-between w-full mt-[0.4rem] px-[.75rem] pt-[.7rem] pb-[.4rem]">
            {benchmarkData.map((item, index) => (
              <PerformanceItem
                key={index}
                label={item.label}
                value={String(Math.round(item.value!))}
                tag={item.tag}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function GuardrailClusterCard({
  data,
  selected,
  index,
  handleClick,
}: {
  data: any;
  index: number;
  selected?: boolean;
  handleClick?: () => void;
}) {
  const [hover, setHover] = React.useState(false);
  const [openDetails, setOpenDetails] = React.useState<boolean>(false);

  const toggleDetail = (e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenDetails(!openDetails);
  };

  const resourceDetails = Array.isArray(data.resource_details)
    ? data.resource_details
    : [];

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className="clusterDropup border-b-[1px] border-[#757575] clusterCardRow w-full px-[1.4rem] py-[.8rem]"
    >
      <div className="flex justify-between items-center w-full">
        <div className="flex items-center justify-between w-[83%]">
          <div className="flex items-start justify-start">
            <div className="flex items-center justify-center w-[2.25rem] h-[1.75rem] rounded-[6px] bg-[#122F1140] border border-[#479D5F] mr-[0.75rem]">
              <Text_12_400_EEEEEE className="leading-[100%]">
                #{index + 1}
              </Text_12_400_EEEEEE>
            </div>
            <div>
              <div>
                <Text_14_400_EEEEEE className="max-w-[100px] 1920px:max-w-[150px] 2560px:max-w-[250px] truncate overflow-hidden whitespace-nowrap">
                  {data.name || data.cluster_name}
                </Text_14_400_EEEEEE>
              </div>
              <div className="flex items-center justify-start gap-[.5rem] mt-[.3rem]">
                {resourceDetails.map((item: any, idx: number) => (
                  <Tags
                    key={idx}
                    name={item.type}
                    color="#D1B854"
                    classNames="py-[.26rem] px-[.4rem]"
                  />
                ))}
                {data.cost_per_token !== undefined && (
                  <Tags
                    name={`${formatCost(data.cost_per_token)} USD / 1M tokens`}
                    color="#965CDE"
                    classNames="py-[.26rem] px-[.4rem]"
                  />
                )}
              </div>
            </div>
          </div>
        </div>

        {(hover || selected) && (
          <div className="flex justify-end items-center cursor-pointer hover:text-[#EEEEEE]">
            <div
              className="w-[0.9375rem] h-[0.9375rem] mr-[0.6rem]"
              onClick={toggleDetail}
            >
              <Image
                preview={false}
                width={15}
                src="/images/drawer/ChevronUp.png"
                alt="Logo"
                style={{
                  transform: !openDetails ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform 0.3s ease",
                }}
              />
            </div>
            <Checkbox
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
            />
          </div>
        )}
      </div>
      {openDetails && <GuardrailClusterDetail data={data} />}
    </div>
  );
}

export default function GuardrailClusterList({
  clusters,
  handleClusterSelection,
  selectedClusterId,
}: {
  clusters: any[];
  handleClusterSelection: (cluster: any) => void;
  selectedClusterId: string | null;
}) {
  return clusters?.map((cluster: any, clusterIndex: number) => (
    <GuardrailClusterCard
      key={cluster.cluster_id || cluster.id || clusterIndex}
      index={clusterIndex}
      data={cluster}
      selected={(cluster.cluster_id || cluster.id) === selectedClusterId}
      handleClick={() => handleClusterSelection(cluster)}
    />
  ));
}
