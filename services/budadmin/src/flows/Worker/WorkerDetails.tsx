import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import {
  Text_10_400_757575,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
  Text_13_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_19_600_EEEEEE,
  Text_24_400_EEEEEE,
  Text_26_400_EEEEEE,
  Text_32_400_EEEEEE,
  Text_9_400_EEEEEE,
} from "@/components/ui/text";
import { ReloadIcon } from "@radix-ui/react-icons";
import { Button, Image, Spin } from "antd";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import NoChartData from "@/components/ui/noChartData";
import LineChartCustom from "@/components/charts/lineChart/LineChartCustom";
import { SpecificationTableItem } from "../components/SpecificationTableItem";
import {
  formatDistanceCustom,
  formdateDateTime,
  getSpecValueWidthOddEven,
} from "@/lib/utils";
import { useWorkers } from "src/hooks/useWorkers";
import { useRouter } from "next/router";
import BudStepAlert from "../components/BudStepAlert";
import { errorToast, successToast } from "@/components/toast";
import {
  calculateEta,
  calculateEtaInDays,
  calculateEtaInHoursAndMinutesExcludeDays,
} from "../utils/calculateETA";
import { formatDate } from "src/utils/formatDate";
import { formatDistance } from "date-fns";
import loaderIcn from "./../../../public/icons/loader.gif";

const transformMetricsData = (metrics: Record<string, number>) => {
  if (!metrics) return null;

  const timestamps = Object.keys(metrics).sort();
  const values = timestamps.map((ts) => metrics[ts]);

  // Convert timestamps to readable time format (HH:mm)
  const formattedTimes = timestamps.map((ts) => {
    const date = new Date(parseInt(ts) * 1000); // Convert seconds to milliseconds
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  });

  return {
    smooth: true,
    color: "#FFC442",
    categories: formattedTimes,
    data: values,
  };
};

function ShortCards({ item }: { item: any }) {
  return (
    <div
      className={`cardBG flex flex-col h-[47.3%] border border-[#1F1F1F] rounded-md pt-[.75rem] pb-[.9rem] px-[1.15rem] pr-[.2rem] justify-between min-h-[144px] ${item.className}`}
      style={{ width: item.width }}
    >
      <div>
        <Text_14_600_EEEEEE className="">{item.nameText}</Text_14_600_EEEEEE>
        <span className="block h-[3px] bg-[#965CDE] w-[1.6875rem] mt-[.1em] ml-[.1rem]"></span>
      </div>
      <div className="flex justify-between w-full items-end	">
        <div>
          <div className="flex mb-[.2rem] items-end">{item.val1}</div>
          {item.val2}
        </div>
      </div>
    </div>
  );
}

function Log({ item }: { item: any }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className={`flex flex-col justify-start items-center  rounded-[8px] bg-[#FFFFFF08] transition-all duration-300 p-[0.5rem]  ${
        isExpanded ? "h-auto" : "h-[2.8rem]"
      }`}
    >
      <div
        className="flex justify-start items-start w-full cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div
          className={`w-[.9rem] h-[0.9rem] ml-[.5rem] mr-[.95rem] transition-transform origin-center duration-300 ${
            isExpanded ? "rotate-[180deg]" : "rotate-90"
          }`}
        >
          <Image
            preview={false}
            style={{ width: "0.9rem", height: "0.9rem" }}
            src="/images/drawer/ChevronUp.png"
            alt=""
          />
        </div>
        <div className="flex justify-start items-start max-w-[90%]">
          <Text_12_400_B3B3B3 className="mr-[1rem] leading-[1rem]">
            {new Date(item.timestamp).toLocaleString()}
          </Text_12_400_B3B3B3>
          <div
            className={`ibm text-[#EEEEEE] self-center  font-[500] text-[.75rem] leading-[1rem] overflow-hidden ${
              isExpanded ? "whitespace-normal" : "text-nowrap"
            }`}
          >
            {item.message}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorkerDetails() {
  const router = useRouter();
  const [showConfirm, setShowConfirm] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [wrokerMetrics, setWrokerMetrics] = useState<any>(null);
  const [workerLogs, setWorkerLogs] = useState<any>(null);

  const deploymentId = router.query.deploymentId as string;
  const projectId = router.query.projectId as string;

  const { closeDrawer } = useDrawer();
  const { submittable } = useContext(BudFormContext);
  const {
    deleteWorker,
    getWorkers,
    selectedWorker,
    getWorker,
    loading,
    workers,
    getWorkerMetrics,
    isMetricsLoading,
    getWorkerLogs,
  } = useWorkers();

  useEffect(() => {
    if (selectedWorker) {
      getWorkerMetrics(deploymentId, selectedWorker.id, projectId).then(
        (metrics) => {
          setWrokerMetrics(metrics);
        },
      );
      getWorkerLogs(deploymentId, selectedWorker.id, projectId).then((logs) => {
        setWorkerLogs(logs);
      });
    }
  }, [selectedWorker]);

  const specs = [
    {
      icon: "/images/drawer/template-1.png",
      name: "Node IP",
      value: selectedWorker?.node_ip,
      type: "text",
    },
    {
      icon: "/images/drawer/calander.png",
      name: "Created Date",
      value:
        selectedWorker?.created_datetime &&
        formatDate(new Date(selectedWorker?.created_datetime)),
      // value: selectedWorker?.created_datetime,
      type: "text",
    },
    {
      icon: "/images/drawer/tag.png",
      name: "Status",
      value: selectedWorker?.status && [selectedWorker?.status],
      type: "tag",
    },
    {
      icon: "/images/drawer/calander.png",
      name: "Last Updated",
      value:
        selectedWorker?.last_updated_datetime &&
        formatDistanceCustom(new Date(selectedWorker?.last_updated_datetime)),
      // value: selectedWorker?.last_updated_datetime,
      type: "text",
    },
    {
      icon: "/images/drawer/hardware.png",
      name: "Hardware Type",
      value: selectedWorker?.hardware?.toUpperCase(),
      type: "text",
    },
  ]?.filter((item) => item.value);

  const specsTwo = [
    {
      icon: "/images/drawer/template-1.png",
      name: "Cores",
      value: selectedWorker?.cores,
      type: "text",
    },
    {
      icon: "/images/drawer/hardware.png",
      name: "Scheduled Version",
      value: "", // TODO: get from API
      type: "text",
    },
    {
      icon: "/images/drawer/context.png",
      name: "Cache",
      value: "", // TODO: get from API
      type: "text",
    },
    {
      icon: "/images/drawer/per.png",
      name: "Memory",
      value: selectedWorker?.memory,
      type: "text",
    },
    {
      icon: "/images/drawer/tag.png",
      name: "Libraries",
      // value: [], // TODO: get from API
      value: undefined,
      type: "tag",
    },
  ]?.filter((item) => item.value);

  const onDeleteClick = () => {
    if (workers.length === 1) {
      errorToast("At least one worker is required");
      return;
    }
    if (
      selectedWorker?.status === "deleted" ||
      selectedWorker?.status === "deleting"
    ) {
      errorToast("Worker is already deleted");
      return;
    }
    if (
      workers?.length -
        workers?.filter(
          (worker) =>
            worker.status === "deleted" || worker.status === "deleting",
        ).length <=
      1
    ) {
      errorToast("At least one active worker is required");
      return;
    }

    setShowConfirm(true);
  };

  return (
    <BudForm
      data={{}}
      onNext={() => {
        closeDrawer();
      }}
      nextText="Close"
      disableNext={!submittable}
    >
      <BudWraperBox>
        {showConfirm && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title={"You're about to delete the worker"}
              description={"Are you sure you want to delete this worker?"}
              confirmText={"Delete Worker"}
              cancelText={"Cancel"}
              confirmAction={async () => {
                const result = await deleteWorker(
                  deploymentId,
                  selectedWorker,
                  projectId,
                );
                console.log(result);
                if (result) {
                  closeDrawer();
                  successToast(result?.data?.message);
                }
                setShowConfirm(false);
              }}
              cancelAction={() => {
                setShowConfirm(false);
              }}
            />
          </BudDrawerLayout>
        )}
        {showSuccess && (
          <BudDrawerLayout>
            <BudStepAlert
              type="success"
              title={"Worker is successfully Reloaded"}
              description={
                "Worker has been successfully reloaded and is now active"
              }
              confirmText={"Ok"}
              confirmAction={async () => {
                setShowSuccess(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <BudDrawerLayout>
          <DrawerCard>
            <div className="flex justify-between items-center pt-[.55rem]">
              <Text_14_400_EEEEEE className="leading-[1.125rem]">
                {selectedWorker?.name}
              </Text_14_400_EEEEEE>
              <div className="flex justify-end items-center gap-[.3rem]">
                <PrimaryButton
                  type="submit"
                  onClick={async () => {
                    await getWorker(
                      deploymentId,
                      selectedWorker.id,
                      true,
                      projectId,
                    );
                    setShowSuccess(true);
                  }}
                  disabled={loading}
                  className="min-w-[7.7rem]"
                >
                  <div className="flex justify-start items-center gap-[.3rem]">
                    <Text_12_600_EEEEEE>Reload</Text_12_600_EEEEEE>
                    <ReloadIcon
                      className={`text-[#EEEEEE] group-hover:text-[#FFFFFF] text-[0.5em] w-[.75rem] ${loading ? "animate-spin" : ""}`}
                    />
                  </div>
                </PrimaryButton>
                <Button
                  disabled={loading}
                  className="flex items-center bg-transparent border-none p-0"
                  onClick={onDeleteClick}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width=".875rem"
                    height=".875rem"
                    viewBox="0 0 14 14"
                    fill="none"
                  >
                    <path
                      fillRule="evenodd"
                      clipRule="evenodd"
                      d="M5.13327 0.898438C4.85713 0.898438 4.63327 1.1223 4.63327 1.39844C4.63327 1.67458 4.85713 1.89844 5.13327 1.89844H8.8666C9.14274 1.89844 9.3666 1.67458 9.3666 1.39844C9.3666 1.1223 9.14274 0.898438 8.8666 0.898438H5.13327ZM2.7666 3.2651C2.7666 2.98896 2.99046 2.7651 3.2666 2.7651H10.7333C11.0094 2.7651 11.2333 2.98896 11.2333 3.2651C11.2333 3.54125 11.0094 3.7651 10.7333 3.7651H10.2661C10.2664 3.77617 10.2666 3.78728 10.2666 3.79844V11.1318C10.2666 11.6841 9.81889 12.1318 9.2666 12.1318H4.73327C4.18098 12.1318 3.73327 11.6841 3.73327 11.1318V3.79844C3.73327 3.78728 3.73345 3.77617 3.73381 3.7651H3.2666C2.99046 3.7651 2.7666 3.54125 2.7666 3.2651ZM9.2666 3.79844L4.73327 3.79844V11.1318L9.2666 11.1318V3.79844Z"
                      fill="#B3B3B3"
                    />
                  </svg>
                </Button>
              </div>
            </div>
            <div className="flex justify-start items-center flex-wrap mt-[3.05rem] gap-x-[.5rem] gap-y-[1.15rem]">
              {specs.map((item, index) => (
                <SpecificationTableItem
                  key={index}
                  item={item}
                  valueWidth={index % 2 === 0 ? 70 : 90}
                />
              ))}
            </div>
            {/* cardBG */}
            <div className="cardBG w-[100%] cardSetTwo h-[448px]  py-[1.9rem] border border-[#1F1F1F] rounded-md mt-[1.5rem]">
              <div className="px-[1.65rem]">
                <Text_19_600_EEEEEE>Compute Utilization</Text_19_600_EEEEEE>
                <Text_13_400_757575 className="mt-[1.35rem]">
                  Compute Utilized over time
                </Text_13_400_757575>
              </div>
              {isMetricsLoading ? (
                <div className="flex justify-center items-center h-full">
                  <Spin />
                </div>
              ) : wrokerMetrics &&
                wrokerMetrics.cpu_metrics &&
                Object.keys(wrokerMetrics.cpu_metrics).length > 0 ? (
                <>
                  <div className="flex flex-col items-start	mt-[1.6rem] px-[1.65rem] pb-[0]">
                    <Text_26_400_EEEEEE>
                      {wrokerMetrics.cpu_metrics &&
                      Object.keys(wrokerMetrics.cpu_metrics).length > 0
                        ? (() => {
                            const timestamps = Object.keys(
                              wrokerMetrics.cpu_metrics,
                            ).sort();
                            const latestTimestamp =
                              timestamps[timestamps.length - 1];
                            const latestValue =
                              wrokerMetrics.cpu_metrics[latestTimestamp];
                            return latestValue !== null
                              ? `${latestValue.toFixed(1)}%`
                              : "0%";
                          })()
                        : "0%"}
                    </Text_26_400_EEEEEE>
                    <div className="flex bg-[#122F1140] rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.35rem]">
                      {wrokerMetrics.cpu_metrics &&
                      Object.keys(wrokerMetrics.cpu_metrics).length > 0 ? (
                        (() => {
                          const values = Object.values(
                            wrokerMetrics.cpu_metrics,
                          ).filter((value): value is number => value !== null);

                          if (values.length === 0) {
                            return (
                              <>
                                <span className="text-[#479D5F] font-[400] text-[0.8125rem] leading-[100%]">
                                  Avg. +0.00%
                                </span>
                                <Image
                                  preview={false}
                                  width={12}
                                  src="/images/dashboard/greenArrow.png"
                                  className="ml-[.2rem]"
                                  alt=""
                                />
                              </>
                            );
                          }

                          const average =
                            values.reduce((sum, value) => sum + value, 0) /
                            values.length;
                          const firstValue = values[0];
                          const percentageChange =
                            ((average - firstValue) / firstValue) * 100;

                          return (
                            <>
                              <span
                                className={`font-[400] text-[0.8125rem] leading-[100%] ${percentageChange >= 0 ? "text-[#479D5F]" : "text-[#D74D4D]"}`}
                              >
                                Avg. {percentageChange >= 0 ? "+" : ""}
                                {percentageChange.toFixed(2)}%
                              </span>
                              <Image
                                preview={false}
                                width={12}
                                src={
                                  percentageChange >= 0
                                    ? "/images/dashboard/greenArrow.png"
                                    : "/images/dashboard/redArrow.png"
                                }
                                className="ml-[.2rem]"
                                alt=""
                              />
                            </>
                          );
                        })()
                      ) : (
                        <>
                          <span className="text-[#479D5F] font-[400] text-[0.8125rem] leading-[100%]">
                            Avg. +0.00%
                          </span>
                          <Image
                            preview={false}
                            width={12}
                            src="/images/dashboard/greenArrow.png"
                            className="ml-[.2rem]"
                            alt=""
                          />
                        </>
                      )}
                    </div>
                  </div>
                  <div className="h-[232px] ">
                    {/* <AccuracyChart data={accuracyChartData} /> */}
                    {wrokerMetrics.cpu_metrics &&
                    Object.keys(wrokerMetrics.cpu_metrics).length > 0 ? (
                      <LineChartCustom
                        data={transformMetricsData(wrokerMetrics.cpu_metrics)}
                      />
                    ) : (
                      <NoChartData
                        textMessage="Once the data is available, we will populate a line chart for you representing Flops Utilization."
                        image="/images/dashboard/noFlops.png"
                      ></NoChartData>
                    )}
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a line chart for you representing Flops Utilization."
                  image="/images/dashboard/noFlops.png"
                  classNames="px-6"
                ></NoChartData>
              )}
            </div>
            <div className="flex justify-start items-start mt-[.8rem] mb-[1.4rem] gap-x-[.9rem]">
              {/* <ShortCards item={{
                nameText: 'Average Requests',
                width: '36%',
                val1: <Text_32_400_EEEEEE className="leading-[100%]">126</Text_32_400_EEEEEE>,
                val2: <Text_10_400_757575>Requests</Text_10_400_757575>
              }} /> */}
              <ShortCards
                item={{
                  nameText: "Uptime",
                  width: "auto",
                  className: "flex-auto",
                  val1: (
                    <Text_24_400_EEEEEE className="leading-[100%]">
                      {calculateEtaInDays(selectedWorker?.uptime)}
                    </Text_24_400_EEEEEE>
                  ),
                  val2: (
                    <Text_9_400_EEEEEE className="">
                      {calculateEtaInHoursAndMinutesExcludeDays(
                        selectedWorker?.uptime,
                      )}
                    </Text_9_400_EEEEEE>
                  ),
                }}
              />
              <ShortCards
                item={{
                  nameText: "Memory",
                  width: "auto",
                  className: "flex-auto",
                  val1: (
                    <Text_24_400_EEEEEE className="leading-[100%]">
                      {wrokerMetrics && wrokerMetrics.memory_usage ? (
                        <>
                          {" "}
                          {(
                            (wrokerMetrics.memory_usage /
                              ((Number(
                                selectedWorker?.memory
                                  .replace("Ki", "")
                                  .replace("Mi", ""),
                              ) *
                                1024) /
                                Math.pow(1024, 3))) *
                            100
                          ).toFixed(1)}{" "}
                          <span className="text-[1rem]">%</span>
                        </>
                      ) : (
                        <Text_24_400_EEEEEE className="leading-[100%]">
                          <span className="text-[1rem]">0</span>
                        </Text_24_400_EEEEEE>
                      )}
                    </Text_24_400_EEEEEE>
                  ),
                  val2: <Text_9_400_EEEEEE>This week</Text_9_400_EEEEEE>,
                }}
              />
            </div>
            <div className="hR"></div>
            <div className="mt-[1rem] mb-[.5rem]">
              <Text_14_600_EEEEEE>Worker Specification</Text_14_600_EEEEEE>
              <div className="flex justify-start items-center flex-wrap mt-[.9rem] gap-x-[1rem] gap-y-[1.55rem]">
                {specsTwo.map((item, index) => (
                  <SpecificationTableItem
                    key={index}
                    item={item}
                    valueWidth={getSpecValueWidthOddEven(specsTwo, index)}
                  />
                ))}
              </div>
            </div>
            <div className="hR"></div>
            <div className="mt-[1rem] mb-[.5rem]">
              <Text_14_600_EEEEEE>Logs</Text_14_600_EEEEEE>
              <div className="mt-[.75rem] flex flex-col gap-[.8rem]">
                {workerLogs?.map((item: any, index: number) => (
                  <Log key={index} item={item} />
                ))}
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
