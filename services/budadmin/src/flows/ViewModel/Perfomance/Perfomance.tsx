import {
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_13_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { ConfigProvider, Image, Form, Select } from "antd"; // Added Checkbox import
import Leaderboards from "src/flows/components/LeaderboardsTable";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import { useCluster } from "src/hooks/useCluster";
import { useDeployModel } from "src/stores/useDeployModel";
import { Button, Popover } from "@radix-ui/themes";
import { Cross1Icon, MixerHorizontalIcon } from "@radix-ui/react-icons";
import CustomPopover from "src/flows/components/customPopover";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import ClusterList from "src/flows/components/ClusterList";
import ComingSoon from "@/components/ui/comingSoon";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { Model } from "src/hooks/useModels";
import { useDrawer } from "src/hooks/useDrawer";

function ClusterFilter() {
  const [filterOpen, setFilterOpen] = React.useState(false);

  const handleOpenChange = (open) => {
    setFilterOpen(open);
  };
  const handleCloseFilterMenu = () => {
    setFilterOpen(false);
  };
  const applyFilter = () => {};
  const clearFilter = () => {};
  const parentElement = document.querySelector(".BudWraperBox") as HTMLElement;

  if (filterOpen) {
    if (parentElement instanceof HTMLElement) {
      parentElement.classList.add("stop-scroll-class"); // Add your desired class
    }
  } else {
    if (parentElement instanceof HTMLElement) {
      parentElement.classList.remove("stop-scroll-class"); // Add your desired class
    }
  }
  return (
    <Popover.Root open={filterOpen} onOpenChange={handleOpenChange}>
      <Popover.Trigger>
        <label
          className="h-[1.7rem] text-[#FFFFFF] mx-2 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
          onClick={() => {}}
        >
          <MixerHorizontalIcon
            style={{ width: "0.875rem", height: "0.875rem" }}
            className="mr-2"
          />
          {/* <Text_12_400_C7C7C7>Filter</Text_12_400_C7C7C7> */}
        </label>
      </Popover.Trigger>
      <Popover.Content
        width="360px"
        align="end"
        className="bg-[#111113] shadow-none  border border-[#1F1F1F]"
      >
        <div className="flex mb-5 justify-between items-center">
          <Text_16_600_FFFFFF className="p-0 m-0">Filter</Text_16_600_FFFFFF>
          <Button
            className="m-0 p-0 bg-[transparent] h-[1.1rem] outline-none"
            size="1"
            onClick={handleCloseFilterMenu}
          >
            <Cross1Icon />
          </Button>
        </div>
        <Text_12_400_757575 className="mb-[1rem] pb-[1.5rem] border-b-[1px] border-b-[#1F1F1F]">
          Apply the following filters to find model of your choice.
        </Text_12_400_757575>
        <div className="w-full flex flex-col gap-[1.5rem]">
          <Form.Item
            hasFeedback
            rules={[{ required: true, message: "Please select author" }]}
            name={"author"}
            className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
          >
            <div className="w-full">
              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
                Author
                <CustomPopover title="This is the author">
                  <Image
                    src="/images/info.png"
                    preview={false}
                    alt="info"
                    style={{ width: ".75rem", height: ".75rem" }}
                  />
                </CustomPopover>
              </Text_12_300_EEEEEE>
            </div>
            <div className="custom-select-two w-full rounded-[6px] relative">
              <ConfigProvider
                theme={{
                  token: {
                    colorTextPlaceholder: "#808080",
                  },
                }}
              >
                <Select
                  placeholder="Select Author"
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE",
                    border: "0.5px solid #757575",
                    width: "100%",
                  }}
                  size="large"
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
                  options={[
                    // Input should be 'llm', 'image', 'embedding', 'text_to_speech' or 'speech_to_text'
                    { label: "LLM", value: "llm" },
                    { label: "Image", value: "image" },
                    { label: "Embedding", value: "embedding" },
                    { label: "Text to Speech", value: "text_to_speech" },
                    { label: "Speech to Text", value: "speech_to_text" },
                  ]}
                  onChange={null}
                />
              </ConfigProvider>
            </div>
          </Form.Item>
          <Form.Item
            hasFeedback
            rules={[{ required: true, message: "Please select task" }]}
            name={"task"}
            className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
          >
            <div className="w-full">
              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
                Task
                <CustomPopover title="This is the task">
                  <Image
                    src="/images/info.png"
                    preview={false}
                    alt="info"
                    style={{ width: ".75rem", height: ".75rem" }}
                  />
                </CustomPopover>
              </Text_12_300_EEEEEE>
            </div>
            <div className="custom-select-two w-full rounded-[6px] relative">
              <ConfigProvider
                theme={{
                  token: {
                    colorTextPlaceholder: "#808080",
                  },
                }}
              >
                <Select
                  placeholder="Select Task"
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE",
                    border: "0.5px solid #757575",
                    width: "100%",
                  }}
                  size="large"
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
                  options={[
                    // Input should be 'llm', 'image', 'embedding', 'text_to_speech' or 'speech_to_text'
                    { label: "LLM", value: "llm" },
                    { label: "Image", value: "image" },
                    { label: "Embedding", value: "embedding" },
                    { label: "Text to Speech", value: "text_to_speech" },
                    { label: "Speech to Text", value: "speech_to_text" },
                  ]}
                  onChange={null}
                />
              </ConfigProvider>
            </div>
          </Form.Item>
          <Form.Item
            hasFeedback
            rules={[{ required: true, message: "Please select model size" }]}
            name={"modelSize"}
            className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
          >
            <div className="w-full">
              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
                Model&nbsp;Size
                <CustomPopover title="This is the model size">
                  <Image
                    src="/images/info.png"
                    preview={false}
                    alt="info"
                    style={{ width: ".75rem", height: ".75rem" }}
                  />
                </CustomPopover>
              </Text_12_300_EEEEEE>
            </div>
            <div className="custom-select-two w-full rounded-[6px] relative">
              <ConfigProvider
                theme={{
                  token: {
                    colorTextPlaceholder: "#808080",
                  },
                }}
              >
                <Select
                  placeholder="Select Model Size"
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE",
                    border: "0.5px solid #757575",
                    width: "100%",
                  }}
                  size="large"
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
                  options={[
                    // Input should be 'llm', 'image', 'embedding', 'text_to_speech' or 'speech_to_text'
                    { label: "LLM", value: "llm" },
                    { label: "Image", value: "image" },
                    { label: "Embedding", value: "embedding" },
                    { label: "Text to Speech", value: "text_to_speech" },
                    { label: "Speech to Text", value: "speech_to_text" },
                  ]}
                  onChange={null}
                />
              </ConfigProvider>
            </div>
          </Form.Item>
          <Form.Item
            hasFeedback
            rules={[{ required: true, message: "Please select modality" }]}
            name={"modality"}
            className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
          >
            <div className="w-full">
              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
                Modality
                <CustomPopover title="This is the modality">
                  <Image
                    src="/images/info.png"
                    preview={false}
                    alt="info"
                    style={{ width: ".75rem", height: ".75rem" }}
                  />
                </CustomPopover>
              </Text_12_300_EEEEEE>
            </div>
            <div className="custom-select-two w-full rounded-[6px] relative">
              <ConfigProvider
                theme={{
                  token: {
                    colorTextPlaceholder: "#808080",
                  },
                }}
              >
                <Select
                  placeholder="Select Modality"
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE",
                    border: "0.5px solid #757575",
                    width: "100%",
                  }}
                  size="large"
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
                  options={[
                    // Input should be 'llm', 'image', 'embedding', 'text_to_speech' or 'speech_to_text'
                    { label: "LLM", value: "llm" },
                    { label: "Image", value: "image" },
                    { label: "Embedding", value: "embedding" },
                    { label: "Text to Speech", value: "text_to_speech" },
                    { label: "Speech to Text", value: "speech_to_text" },
                  ]}
                  onChange={null}
                />
              </ConfigProvider>
            </div>
          </Form.Item>
        </div>
        <div className="flex items-center justify-between mt-[1.5rem]">
          <SecondaryButton
            type="submit"
            onClick={clearFilter}
            classNames="!px-[.8rem] tracking-[.02rem]"
          >
            Reset
          </SecondaryButton>
          <PrimaryButton
            type="submit"
            onClick={applyFilter}
            classNames="!px-[.8rem] tracking-[.02rem]"
          >
            Apply
          </PrimaryButton>
        </div>
      </Popover.Content>
    </Popover.Root>
  );
}

export default function PerformanceDetailed({ data }: { data: Model }) {
  const { hasPermission } = useUser();
  const { openDrawer } = useDrawer();
  const [search, setSearch] = React.useState("");
  const { deploymentCluster, setDeploymentCluster } = useDeployModel();
  const { recommendedCluster, getRecommendedClusterById, currentProcessId } =
    useCluster();
  const filteredClusters = recommendedCluster?.clusters?.filter((cluster) =>
    cluster.name.toLowerCase().includes(search.toLowerCase()),
  );
  const [openDetails, setOpenDetails] = useState<number | null>(null); // State to track which cluster's detail is open
  const toggleDetail = (index: number) => {
    setOpenDetails(openDetails === index ? null : index);
  };
  useEffect(() => {
    if (currentProcessId !== "") {
      getRecommendedClusterById(currentProcessId);
    }
  }, [currentProcessId]);
  return (
    <div className="pt-[.45rem] relative">
      {/* <ComingSoon shrink={true} scaleValue={0.9} comingYpos="-50%" /> */}
      <div className="flex justify-between items-center">
        <Text_12_400_757575 className="leading-[1.125rem]">
          Recommended clusters
        </Text_12_400_757575>
        <PrimaryButton
          type="submit"
          onClick={() => {
            openDrawer("model_benchmark", { source: "modelDetails" });
          }}
          className="min-w-[7.7rem]"
          permission={hasPermission(PermissionEnum.ModelManage)}
        >
          Run Performance Benchmark
        </PrimaryButton>
      </div>
      <div className="clusterCard w-full">
        {recommendedCluster?.clusters?.length > 0 ? (
          <ClusterList
            clusters={filteredClusters}
            handleClusterSelection={setDeploymentCluster}
            selectedCluster={deploymentCluster}
          />
        ) : (
          <div className="my-[1rem]">
            <div>
              <Text_12_400_757575 className="mt-[.55rem]">
                Find out the recommended clusters
              </Text_12_400_757575>
            </div>
            {/* <PrimaryButton
                type="submit"
                onClick={() => {
                  null
                }}
                className="min-w-[7.7rem]"
              >
                Find Recommended Cluster
              </PrimaryButton> */}
            <div className="bg-[#1F1F1F] rounded-[6px] min-h-[126px] flex items-center justify-center my-[1rem]">
              <div className="text-center flex flex-col justify-center items-center">
                <div className="text-center w-[2.734375rem]">
                  <Image
                    preview={false}
                    src="/images/drawer/noData.png"
                    className="ml-[.2rem]"
                    alt=""
                    style={{ width: "2.734375rem" }}
                  />
                </div>
                <Text_13_400_B3B3B3>No data available</Text_13_400_B3B3B3>
              </div>
            </div>
          </div>
        )}
      </div>
      <div>
        <div>
          <Text_14_400_EEEEEE>Performace benchmarks ran</Text_14_400_EEEEEE>
          <Text_12_400_757575 className="mt-[.55rem]">
            Following is the list of recommended clusters
          </Text_12_400_757575>
        </div>
        <div className="rounded-es-lg rounded-ee-lg pb-[.15rem] flex justify-between items-center mt-[1.1rem]">
          <div className="flex items-center justify-between flex-auto mr-[.8rem]">
            <SearchHeaderInput
              placeholder="Search model, cluster, status"
              searchValue={search}
              setSearchValue={setSearch}
              expanded
            />
          </div>
          <PrimaryButton
            type="submit"
            onClick={() => {
              openDrawer("model_benchmark", { source: "modelDetails" });
            }}
            className="min-w-[7.7rem]"
            permission={hasPermission(PermissionEnum.ModelManage)}
          >
            Run Another Benchmark
          </PrimaryButton>
          <div className="ml-[.2rem]">
            <ClusterFilter />
          </div>
        </div>
        <Leaderboards showHeader={false} model={data} />
      </div>
    </div>
  );
}
