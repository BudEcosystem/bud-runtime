"use client";
import React, { useCallback, useEffect, useState } from "react";
import DashBoardLayout from "../../layout";
import { Button, Flex, Popover, Table, Text } from "@radix-ui/themes";
import moment from "moment";

import {
  ChevronLeftIcon,
  Cross1Icon,
  DotFilledIcon,
  MixerHorizontalIcon,
  SlashIcon,
} from "@radix-ui/react-icons";
import {
  Text_12_300_6A6E76,
  Text_12_400_787B83,
  Text_12_400_C7C7C7,
  Text_14_400_5B6168,
  Text_14_400_965CDE,
  Text_16_600_FFFFFF,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import { useRouter } from "next/router";
import { ButtonInput } from "@/components/ui/button";
import { SelectCustomInput, TextInput } from "@/components/ui/input";
import { AppRequest } from "src/pages/api/requests";
import Breadcrumb from "@/components/breadcrumb";
import { successToast } from "@/components/toast";
import { useLoader } from "src/context/appContext";
import { DotIcon } from "lucide-react";
import clsx from "clsx";
import ComboBox from "@/components/ui/comboBox";

type Props = {};
const tableHeader = [
  "Model provider",
  "Model name",
  "Clusters",
  "No. of workers",
  "Cache",
  "Status",
  "Throughput",
  "Latency/TPOT(Mean)",
  "Duration",
  "Date",
];

interface Range {
  min_value: number | null | string;
  max_value: number | null | string;
}

interface DataObject {
  output_throughput?: Range | null;
  mean_tpot_ms?: Range | null;
}

let initialVal = {
  output_throughput: null,
  mean_tpot_ms: null,
};

export default function BenchmarkHistory(props: Props) {
  const [filterOpen, setFilterOpen] = useState(false);
  const [formData, setFormData] = React.useState<{ [key: string]: string }>({});
  const [filteredData, setFilteredData] = useState([]);
  const { isLoading, showLoader, hideLoader } = useLoader();
  const [throghputVal, setThroghputVal] = useState<{
    [key: string]: number | null | string;
  }>(null);
  const [meanTpotVal, setMeanTpotVal] = useState<{
    [key: string]: number | null | string;
  }>(null);
  const router = useRouter();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [modelNames, setModelNames] = useState([]);

  let page = 1;
  let limit = 10;

  const [benchmarkHistoryData, setBenchmarkHistoryData] = useState([]);
  const getList = async (page: any, limit: any, filterPayload?: DataObject) => {
    try {
      showLoader();
      let url = `/benchmarks/history?page=${page}&limit=${limit}`;
      if (formData.name) {
        url += `&model_name=${formData.name}`;
      }
      if (formData?.status) {
        url += `&status=${formData?.status}`;
      }

      const response: any = await AppRequest.Post(url, filterPayload);
      setBenchmarkHistoryData(response.data.results);
      hideLoader();
    } catch (error) {
      setBenchmarkHistoryData([]);
      hideLoader();
      console.error("Error creating model:", error);
    }
  };

  useEffect(() => {
    getList(page, limit);
  }, [page, limit]);

  useEffect(() => {
    // applyFilters();
    setFilteredData(benchmarkHistoryData);
  }, [benchmarkHistoryData]);

  const getBenchMarkModels = useCallback(
    async (page: any, limit: any) => {
      showLoader();
      let url = `/benchmarks/models/?page=${page}&limit=${limit}&is_active=${true}`;
      try {
        const response: any = await AppRequest.Get(url);
        if (response.data) {
          let result = response.data.results;
          const modelNames = result.map((item) => item.name);
          const uniqueModelNamesArray = Array.from(new Set(modelNames));
          setModelNames(uniqueModelNamesArray);
          hideLoader();
        }
      } catch (error) {
        console.error("Error creating model:", error);
      }
    },
    [showLoader, hideLoader]
  );

  useEffect(() => {
    getBenchMarkModels(currentPage, pageSize);
  }, [currentPage, pageSize, getBenchMarkModels]);

  const handleApplyFilters = async () => {
    let formBody: any = {};
    formBody.output_throughput = throghputVal;
    formBody.mean_tpot_ms = meanTpotVal;
    await getList(page, limit, formBody);
    handleCloseFilterMenu();
  };

  const handleOpenChange = (open) => {
    setFilterOpen(open);
  };
  const handleCloseFilterMenu = () => {
    setThroghputVal(null);
    setMeanTpotVal(null);
    setFormData({});
    setFilterOpen(false);
  };
  const handleChange = (name: string, value: string) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const onThroughPutChange = (name: string, value: number | string) => {
    const normalizedValue = value === "" ? null : value;
    if (!throghputVal) {
      setThroghputVal({
        min_value: name === "min_value" ? normalizedValue : null,
        max_value: name === "max_value" ? normalizedValue : null,
      });
    } else {
      setThroghputVal((prev) => ({ ...prev, [name]: normalizedValue }));
    }
  };
  const onMeanTpotChange = (name: string, value: number | string) => {
    const normalizedValue = value === "" ? null : value;

    if (!meanTpotVal) {
      setMeanTpotVal({
        min_value: name === "min_value" ? normalizedValue : null,
        max_value: name === "max_value" ? normalizedValue : null,
      });
    } else {
      setMeanTpotVal((prev) => ({ ...prev, [name]: normalizedValue }));
    }
  };

  const navigateWithProps = (benchmarkId: string) => {
    router.push({
      pathname: "/modelRepo/benchmarkHistory/benchmarkResult",
      query: { benchmarkId },
    });
  };

  return (
    <>
      <DashBoardLayout>
        <Breadcrumb previousRoute="/modelRepo" />
        <Flex className="px-[5.1%]" align="center" justify="between">
          <Text_26_600_FFFFFF>Global Benchmark history</Text_26_600_FFFFFF>
          <Popover.Root open={filterOpen} onOpenChange={handleOpenChange}>
            <Popover.Trigger>
              <Text
                className="h-[1.7rem] text-[#FFFFFF] mr-2 flex items-center !border !border-[#18191B] cursor-pointer text-xs font-normal leading-3 rounded-[6px] px-[0.8rem] shadow-none bg-transparent"
                onClick={() => { }}
              >
                <MixerHorizontalIcon width="14" height="14" className="mr-2" />
                <Text_12_400_C7C7C7>Filter</Text_12_400_C7C7C7>
              </Text>
            </Popover.Trigger>
            <Popover.Content
              width="360px"
              align="end"
              className="bg-[#111113] shadow-none"
            >
              <Flex justify="between" align="center" className="mb-5">
                <Text_16_600_FFFFFF className="p-0 m-0">
                  Filter
                </Text_16_600_FFFFFF>
                <Button
                  className="m-0 p-0 bg-[transparent] h-[1.1rem] outline-none"
                  size="1"
                  onClick={handleCloseFilterMenu}
                >
                  <Cross1Icon />
                </Button>
              </Flex>
              <Flex direction="column" gap="3" mt="4">
                <div className="pb-1">
                  <Text_12_400_787B83 mb="1">Model</Text_12_400_787B83>
                  {/* <TextInput
                    textFieldSlot=""
                    name={'name'}
                    onChange={(e) => handleChange('name', e.target.value)}
                    placeholder={`Enter Model `}
                    className="text-[#FFFFFF]"
                  /> */}
                  <SelectCustomInput
                    size="2"
                    value={formData["name"] || ""}
                    onValueChange={(newValue) => handleChange("name", newValue)}
                    placeholder={`Select Model`}
                    selectItems={modelNames}
                    renderItem=""
                    className="mb-4"
                  />
                  <ComboBox></ComboBox>
                </div>
                <div className="pb-1">
                  <Text_12_400_787B83 mb="1">Status</Text_12_400_787B83>
                  <SelectCustomInput
                    size="2"
                    value={formData["status"] || ""}
                    onValueChange={(newValue) =>
                      handleChange("status", newValue)
                    }
                    showSearch={false}
                    placeholder={`Select Status`}
                    selectItems={["success", "failed", "processing"]}
                    renderItem=""
                  />
                </div>
                <div className="pb-1">
                  <Text_12_400_787B83 mb="1">Throughput</Text_12_400_787B83>
                  <Flex align="center">
                    <TextInput
                      textFieldSlot=""
                      type="number"
                      name={"throughput_min"}
                      onChange={(e) =>
                        onThroughPutChange("min_value", e.target.value)
                      }
                      placeholder={`Min`}
                      className="text-[#FFFFFF] !max-w-11"
                    />
                    <Text_12_300_6A6E76 className="mx-2">to</Text_12_300_6A6E76>
                    <TextInput
                      textFieldSlot=""
                      type="number"
                      name={"throughput_max"}
                      onChange={(e) =>
                        onThroughPutChange("max_value", e.target.value)
                      }
                      placeholder={`Max`}
                      className="text-[#FFFFFF] !max-w-11"
                    />
                  </Flex>
                </div>
                <div className="pb-1">
                  <Text_12_400_787B83 mb="1">Latency</Text_12_400_787B83>
                  <Flex align="center">
                    <TextInput
                      textFieldSlot=""
                      type="number"
                      name={"latency_min"}
                      onChange={(e) =>
                        onMeanTpotChange("min_value", e.target.value)
                      }
                      placeholder={`Min`}
                      className="text-[#FFFFFF] !max-w-11"
                    />
                    <Text_12_300_6A6E76 className="mx-2">to</Text_12_300_6A6E76>
                    <TextInput
                      textFieldSlot=""
                      type="number"
                      name={"latency_max"}
                      onChange={(e) =>
                        onMeanTpotChange("max_value", e.target.value)
                      }
                      placeholder={`Max`}
                      className="text-[#FFFFFF] !max-w-11"
                    />
                  </Flex>
                </div>
              </Flex>
              <Flex gap="3" mt="4" justify="center">
                <ButtonInput
                  size="1"
                  className="w-full"
                  onClick={handleApplyFilters}
                >
                  Apply
                </ButtonInput>
              </Flex>
            </Popover.Content>
          </Popover.Root>
        </Flex>
        <div className="boardPageView">
          <div className="boardMainContainer overflow-hidden">
            <div className="tableWrap h-[100vw_-_55rem]">
              <Table.Root variant="ghost" className="h-full" layout={"auto"}>
                <Table.Header className=" bg-[#0F0F0F]">
                  <Table.Row>
                    {tableHeader.map((item, index) => {
                      return (
                        <Table.ColumnHeaderCell
                          key={index}
                          className="text-xs text-[#B0B4BA] !sticky top-0 bg-[#0F0F0F] z-10 text-nowrap"
                        >
                          {item}
                        </Table.ColumnHeaderCell>
                      );
                    })}
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {filteredData.length ? (
                    filteredData.map((item, index) => {
                      return (
                        <Table.Row
                          // className="hover:bg-[#18191B]"
                          className={clsx(
                            item?.status === "success"
                              ? "cursor-pointer"
                              : "cursor-default"
                          )}
                          key={index}
                          onClick={() => {
                            if (item?.status === "success") {
                              navigateWithProps(item?.benchmark_id);
                            }
                          }}
                        >
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] rounded-s-[5px] text-nowrap">
                            {item.model_source}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item.model_name}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item.cluster}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item.num_of_workers}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item.use_cache ? "enabled" : "disabled"}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item?.status === "success" && (
                              <Flex>
                                <Text className="flex items-center">
                                  success
                                </Text>
                                <DotFilledIcon className="h-4 w-4 text-green-600" />
                              </Flex>
                            )}
                            {item?.status === "failed" && (
                              <Flex>
                                <Text className="flex items-center">
                                  failed{" "}
                                </Text>
                                <DotFilledIcon className="h-4 w-4 text-red-600" />
                              </Flex>
                            )}
                            {item?.status === "processing" && (
                              <Flex>
                                <Text>
                                  processing{" "}
                                </Text>
                                <DotFilledIcon className="h-4 w-4 text-orange-600" />
                              </Flex>
                            )}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item.output_throughput}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item.mean_tpot_ms}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap">
                            {item.duration}
                          </Table.Cell>
                          <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] text-nowrap rounded-e-[5px] pr-[4em]">
                            {moment.utc(item.created_at).local().format("DD/MM/YYYY HH:mm")}
                          </Table.Cell>
                        </Table.Row>
                      );
                    })
                  ) : (
                    <Table.Row className="hover:bg-[#18191B]">
                      <Table.Cell
                        className="!shadow-none text-xs text-center text-[#B0B4BA] rounded-s-[5px] text-nowrap"
                        colSpan={9}
                      >
                        No Benchmark found
                      </Table.Cell>
                    </Table.Row>
                  )}
                </Table.Body>
              </Table.Root>
            </div>
          </div>
        </div>
      </DashBoardLayout>
    </>
  );
}
