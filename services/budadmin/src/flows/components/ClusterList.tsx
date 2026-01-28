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

function ChooseClusterDetail({
  data,
  hidePerformance,
}: {
  data: Cluster;
  hidePerformance?: boolean;
}) {
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
      tag: replicas["label"],
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
    <div className="flex flex-col	justify-start items-center w-full mb-[1rem]">
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
          {data.resource_details.map((item, index) => (
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
      <div className="runningOn w-full rounded-[6px] mt-[1.2rem] bg-[#FFFFFF08]">
        <div className="flex justify-start items-center border-b-[1px] border-[#282828] px-[.75rem] pt-[.7rem] pb-[.4rem]">
          <Text_14_600_EEEEEE className="mr-[.35rem]">
            Running On
          </Text_14_600_EEEEEE>
          <div className="w-[.75rem] w-[.75rem]">
            <CustomPopover title="Below is the hardware will be used to run your model">
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
          {data.required_devices.map((device, index) => {
            return (
              <div
                key={index}
                className="rounded-[6px] text-[#D1B854] text-[0.625rem] font-[400] bg-[#423A1A40] px-[.3rem] py-[.15rem] mr-[.4rem]"
              >
                Running{" "}
                {Math.round(
                  (device?.num_replicas / data.benchmarks["replicas"]) * 100,
                )}
                % on {device?.device_type.toUpperCase()}
              </div>
            );
          })}
        </div>
      </div>
      {!hidePerformance && (
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
          {data.benchmarks && (
            <>
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
                    value={String(Math.round(item.value))}
                    tag={item.tag}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
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
  hidePerformance,
}: {
  data: Cluster;
  index: number;
  selected?: boolean;
  handleClick?: () => void;
  hideSelection?: boolean;
  hideRank?: boolean;
  hidePerformance?: boolean;
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
      className="clusterDropup border-b-[1px] border-[#757575] clusterCardRow w-full px-[1.4rem] py-[.8rem]"
    >
      <Dropdown
        menu={{ items }}
        placement="top"
        getPopupContainer={(trigger) =>
          (trigger.parentNode as HTMLElement) || document.body
        }
        // open
        // disabled = {data.resource_details?.length < 1 || !data.resource_details}
        disabled={true}
        className="tagDropDownDrop"
      >
        <div className="flex justify-between items-center w-full">
          <div
            className=" flex items-center justify-between"
            style={{
              width: hideSelection ? "100%" : "83%",
            }}
          >
            <div className="flex items-start justify-start">
              {!hideRank && (
                <div className="flex items-center justify-center w-[2.25rem] h-[1.75rem] rounded-[6px] bg-[#122F1140] border border-[#479D5F] mr-[0.75rem]">
                  <Text_12_400_EEEEEE className="leading-[100%]">
                    #{index + 1}
                  </Text_12_400_EEEEEE>
                </div>
              )}
              <div>
                <div>
                  <Text_14_400_EEEEEE className="max-w-[100px]  1920px:max-w-[150px] 2560px:max-w-[250px] truncate overflow-hidden whitespace-nowrap">
                    {data.name}
                  </Text_14_400_EEEEEE>
                </div>
                <div className="flex items-center justify-start gap-[.5rem] mt-[.3rem]">
                  {data.resource_details.map((item, index) => (
                    <Tags
                      key={index}
                      name={item.type}
                      color="#D1B854"
                      classNames="py-[.26rem] px-[.4rem]"
                    />
                  ))}
                  {hidePerformance && (
                    <Tags
                      name={`$${data.cost_per_token && data.cost_per_token < 0.01 ? data.cost_per_token.toFixed(4) : data.cost_per_token?.toFixed(2)} to run`}
                      color="#965CDE"
                      classNames="py-[.26rem] px-[.4rem]"
                    />
                  )}
                  {!hidePerformance && (
                    <Tags
                      name={`${data.cost_per_token && data.cost_per_token < 0.01 ? data.cost_per_token.toFixed(4) : data.cost_per_token?.toFixed(2)} USD / 1M tokens`}
                      color="#965CDE"
                      classNames="py-[.26rem] px-[.4rem]"
                    />
                  )}
                </div>
              </div>
            </div>
            {/* <div className="flex items-center justify-center min-w-[3.625rem]">
                            <ConfigProvider
                                theme={{
                                    components: {
                                        Slider: {
                                            handleSize: 0,
                                            handleColor: 'transparent',
                                            handleSizeHover: 0,
                                            handleActiveColor: 'transparent',
                                        },
                                    },
                                }}
                            >
                                <Slider
                                    className="budSlider mt-8 w-full w-[3.625rem]"
                                    value={Math.round(100 - (resource_details.available / resource_details.total) * 100)}
                                    max={100}
                                    tooltip={{
                                        open: true,
                                        getPopupContainer: trigger => (trigger.parentNode as HTMLElement) || document.body,  // Cast parentNode to HTMLElement
                                    }}
                                    styles={{
                                        track: {
                                            backgroundColor: "#965CDE",
                                            height: 3
                                        },
                                        rail: {
                                            backgroundColor: "#212225",
                                            height: 3,
                                        },

                                    }}
                                />
                            </ConfigProvider>

                        </div> */}
            {/* <div className="bg-[#1F1F1F] rounded-[6px] px-[.75rem] py-[.55rem]">
                            {!hidePerformance && <Text_10_400_EEEEEE>{data.cost_per_token?.toFixed(2)} USD / 1M tokens</Text_10_400_EEEEEE>}
                            {hidePerformance && <Text_10_400_EEEEEE>${data.cost_per_token?.toFixed(2)} to run</Text_10_400_EEEEEE>}
                        </div> */}
          </div>

          {(hover || selected) && !hideSelection && (
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
      </Dropdown>
      {openDetails && (
        <ChooseClusterDetail data={data} hidePerformance={hidePerformance} />
      )}
    </div>
  );
}

export default function ClusterList({
  clusters,
  handleClusterSelection,
  selectedCluster,
  hideSelection,
  hideRank,
  hidePerformance,
}: {
  clusters: Cluster[];
  handleClusterSelection: (cluster: Cluster) => void;
  selectedCluster: Cluster;
  hideSelection?: boolean;
  hideRank?: boolean;
  hidePerformance?: boolean;
}) {
  return clusters?.map((cluster, clusterIndex) => (
    <ClusterCard
      key={cluster.id}
      index={clusterIndex}
      data={cluster}
      hideRank={hideRank}
      hidePerformance={hidePerformance}
      hideSelection={hideSelection}
      selected={cluster.id === selectedCluster?.id} // Check if the cluster is selected
      handleClick={() => handleClusterSelection(cluster)} // Set the selected cluster
    />
  ));
}
