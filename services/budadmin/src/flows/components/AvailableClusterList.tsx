import React from "react";
import {
  Checkbox,
  ConfigProvider,
  Dropdown,
  Image,
  MenuProps,
  Progress,
  Slider,
} from "antd";
import { Cluster } from "src/hooks/useCluster";
import CustomPopover from "src/flows/components/customPopover";
import {
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_12_400_EEEEEE,
  Text_12_400_757575,
  Text_10_400_EEEEEE,
  Text_10_400_B3B3B3,
} from "@/components/ui/text";
import Tags from "./DrawerTags";

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
}: {
  label: string;
  value: number;
  tag: string;
}) {
  let icon = "/images/drawer/tag.png";
  if (label === "E2E Latency") {
    icon = "/images/drawer/per.png";
  }

  return (
    <div className="w-[100%] flex items-center justify-start mb-[0.2rem]">
      <div className="w-[45.7%] flex justify-start align-center">
        <div className="h-[.75rem] flex justify-start align-center">
          <Image
            preview={false}
            src={icon}
            alt="info"
            style={{ width: ".75rem" }}
          />
        </div>
        <Text_12_400_B3B3B3 className="ml-[.4rem]">{label}</Text_12_400_B3B3B3>
      </div>
      <div className="flex justify-start items-center gap-x-[.4rem]">
        <div>
          <Text_12_400_EEEEEE>23/30</Text_12_400_EEEEEE>
        </div>
        <div className="w-[3.6rem]">
          <ConfigProvider
            theme={{
              token: {
                lineHeight: 0 /* here is your global tokens */,
              },
            }}
          >
            <Progress
              strokeLinecap="butt"
              percent={70}
              showInfo={false}
              size={{ height: 3 }}
              strokeColor={"#965CDE"}
              trailColor={"#1F1F1F"}
              className="h-[1.1rem]"
            />
          </ConfigProvider>
        </div>
      </div>
      {/* <Text_12_400_EEEEEE className="min-w-[45px] flex-shrink-0 flex justify-start items-center">{Math.round(value)}</Text_12_400_EEEEEE>
            <div className="w-[55px] flex flex-shrink-0 justify-start items-center">
                <PerformanceTag label={tag} />
            </div> */}
    </div>
  );
}

function ChooseClusterDetail({ data }: { data: Cluster }) {
  const benchmark = data.benchmarks || ({} as any);

  const {
    replicas,
    e2e_latency,
    ttft,
    over_all_throughput,
    per_session_tokens_per_sec,
  } = benchmark;

  const benchmarkData = [
    {
      label: "Workers",
      value: replicas,
      tag: replicas ? replicas["label"] : "",
    },
    {
      label: "E2E Latency",
      value: e2e_latency?.["value"],
      tag: e2e_latency?.["label"],
    },
    {
      label: "TTFT(ms)",
      value: ttft?.["value"],
      tag: ttft?.["label"],
    },
    {
      label: "Overall token per sec",
      value: over_all_throughput?.["value"],
      tag: over_all_throughput?.["label"],
    },
    {
      label: "Per session token per sec",
      value: per_session_tokens_per_sec?.["value"],
      tag: per_session_tokens_per_sec?.["label"],
    },
    {
      label: "Concurrency",
      value: benchmark["concurrency"]?.["value"],
      tag: benchmark["concurrency"]?.["label"],
    },
  ]?.filter(
    (item) =>
      item.value !== null && item.value !== undefined && !isNaN(item.value),
  );

  return (
    <div className="flex flex-col	justify-start items-center w-full ">
      <div className="runningOn w-full rounded-[6px] mt-[1.2rem] border-b-[1px] border-[#282828] bg-[#FFFFFF08]">
        <div className="flex justify-start items-center px-[.75rem] pt-[.65rem] pb-[.1rem]">
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
        {data.benchmarks && (
          <>
            <div className="flex justify-start items-center w-full px-[.75rem] pt-[0] pb-[.6rem] border-b-[1px] border-b-[#282828]">
              <Text_12_400_757575>
                Below is the performance you will get on this cluster
              </Text_12_400_757575>
            </div>
            <div className="flex flex-wrap justify-between w-full mt-[0.4rem] px-[.75rem] pt-[0rem] pb-[.2rem]">
              {benchmarkData.map((item, index) => (
                <PerformanceItem
                  key={index}
                  label={item.label}
                  value={item.value}
                  tag={item.tag}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function ClusterCard({
  data,
  selected,
  index,
  handleClick,
  hideSelection,
  hideRank,
}: {
  data: Cluster;
  index: number;
  selected?: boolean;
  handleClick?: () => void;
  hideSelection?: boolean;
  hideRank?: boolean;
}) {
  const [hover, setHover] = React.useState(false);
  const [openDetails, setOpenDetails] = React.useState<boolean>(hideSelection);

  const toggleDetail = () => {
    setOpenDetails(!openDetails);
  };

  const resource_details = {
    total: data.resource_details?.reduce(
      (sum, resource) => sum + resource.total,
      0,
    ),
    available: data.resource_details?.reduce(
      (sum, resource) => sum + resource.available,
      0,
    ),
  };

  const items: MenuProps["items"] = [
    {
      key: "1",
      label: (
        <div className="flex flex-col justify-center items-start gap-[.5rem] py-[1.6rem] px-[1.8rem]">
          {data.resource_details?.map((item, index) => (
            <Text_12_400_EEEEEE
              key={index}
            >{`Total number of ${item.type}'s vs Available : ${item.available}`}</Text_12_400_EEEEEE>
          ))}
        </div>
      ),
    },
  ];
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className="clusterDropup border-b-[1px] border-[#757575] clusterCardRow w-full px-[1.4rem] pt-[.95rem] pb-[.95rem]"
    >
      <Dropdown
        menu={{ items }}
        placement="top"
        getPopupContainer={(trigger) =>
          (trigger.parentNode as HTMLElement) || document.body
        }
        // open
        disabled={data.resource_details?.length < 1 || !data.resource_details}
        className="tagDropDownDrop"
      >
        <div className="flex justify-between items-center w-full">
          <div
            className=""
            style={{
              width: hideSelection ? "100%" : "83%",
            }}
          >
            <div className="flex items-center justify-start">
              <Text_14_400_EEEEEE className="max-w-[100px]  1920px:max-w-[150px] 2560px:max-w-[250px] truncate overflow-hidden whitespace-nowrap leading-[150%]">
                {data.name}
              </Text_14_400_EEEEEE>
            </div>
            <div className="flex items-center justify-start gap-[.5rem] mt-[.55rem]">
              {data.cpu_count > 0 && (
                <Tags
                  name={`${data.cpu_count} CPU`}
                  color="#D1B854"
                  classNames="py-[.26rem] px-[.4rem]"
                />
              )}
              {data.gpu_count > 0 && (
                <Tags
                  name={`${data.gpu_count} GPU`}
                  color="#D1B854"
                  classNames="py-[.26rem] px-[.4rem]"
                />
              )}
              {data.hpu_count > 0 && (
                <Tags
                  name={`${data.hpu_count} HPU`}
                  color="#D1B854"
                  classNames="py-[.26rem] px-[.4rem]"
                />
              )}
            </div>
          </div>

          {(hover || selected) && !hideSelection && (
            <div className="flex justify-end items-center cursor-pointer hover:text-[#EEEEEE]">
              {data.benchmarks && (
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
                      transform: !openDetails
                        ? "rotate(180deg)"
                        : "rotate(0deg)",
                      transition: "transform 0.3s ease",
                    }}
                  />
                </div>
              )}
              <Checkbox
                checked={selected}
                className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
              />
            </div>
          )}
        </div>
      </Dropdown>
      {openDetails && <ChooseClusterDetail data={data} />}
    </div>
  );
}

export default function ClusterList({
  clusters,
  handleClusterSelection,
  selectedCluster,
  hideSelection,
  hideRank,
}: {
  clusters: Cluster[];
  handleClusterSelection: (cluster: Cluster) => void;
  selectedCluster: Cluster;
  hideSelection?: boolean;
  hideRank?: boolean;
}) {
  return clusters?.map((cluster, clusterIndex) => (
    <ClusterCard
      key={cluster.id}
      index={clusterIndex}
      data={cluster}
      hideRank={hideRank}
      hideSelection={hideSelection}
      selected={cluster.id === selectedCluster?.id} // Check if the cluster is selected
      handleClick={() => handleClusterSelection(cluster)} // Set the selected cluster
    />
  ));
}
