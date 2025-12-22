import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useProjects } from "src/hooks/useProjects";
import { useDeployModel } from "src/stores/useDeployModel";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { StepComponentsType } from "..";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import SearchHeaderInput from "../components/SearchHeaderInput";
import { Popover, Image, ConfigProvider, Select, Checkbox } from "antd";
import {
  Text_10_400_B3B3B3,
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import CustomPopover from "../components/customPopover";
import { UserRoles, UserStatus } from "src/hooks/useUsers";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { ModelListCard } from "@/components/ui/bud/deploymentDrawer/ModelListCard";
import Tags from "../components/DrawerTags";
import { color } from "echarts";
import {
  Dataset,
  usePerfomanceBenchmark,
} from "src/stores/usePerfomanceBenchmark";

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
const defaultFilter = {
  name: "",
};

const useCases = [
  {
    id: 1,
    icon: "/images/drawer/zephyr.png",
    title: "ShareGPT",
    description:
      "Need to add hardware description here, to add hardware descrip...",
    tags: [
      {
        name: "200/4000 Avg output/ input Length",
        color: "#D1B854",
      },
      {
        name: "600k Prompts",
        color: "#D1B854",
      },
    ],
  },
  {
    id: 2,
    icon: "/images/drawer/zephyr.png",
    title: "ShareGPT",
    description:
      "Need to add hardware description here, to add hardware descrip...",
    tags: [
      {
        name: "200/4000 Avg output/ input Length",
        color: "#D1B854",
      },
      {
        name: "600k Prompts",
        color: "#D1B854",
      },
    ],
  },
  {
    id: 3,
    icon: "/images/drawer/zephyr.png",
    title: "ShareGPT",
    description:
      "Need to add hardware description here, to add hardware descrip...",
    tags: [
      {
        name: "200/4000 Avg output/ input Length",
        color: "#D1B854",
      },
      {
        name: "600k Prompts",
        color: "#D1B854",
      },
    ],
  },
];

type cardProps = {
  data?: any;
  ClassNames?: string;
  selected?: boolean;
  handleClick?: () => void;
};

function CardWithCheckBox({
  data,
  ClassNames,
  selected,
  handleClick,
}: cardProps) {
  const [hover, setHover] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className={`py-[.85rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex items-start border-box ${ClassNames}`}
    >
      <div className="flex-auto max-w-[100%]">
        <div className="flex items-center justify-between max-w-[100%]">
          <div className="flex justify-start items-center gap-[.6rem] pb-[0.625rem]">
            <Text_14_400_EEEEEE className="leading-[100%]">
              {data.display_name || data.name}
            </Text_14_400_EEEEEE>
            <div className="flex justify-start items-center gap-[.5rem]">
              <Tags
                name={`${data.num_samples} Samples`}
                color="#D1B854"
                classNames="py-[.32rem] "
                textClass="leading-[100%] text-[.625rem] font-[400]"
              />
            </div>
          </div>
          <div className="w-[0.875rem] h-[0.875rem]">
            <Checkbox
              style={{
                display: hover || selected ? "flex" : "none",
              }}
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
            />
          </div>
        </div>
        <Text_10_400_B3B3B3 className="overflow-hidden truncate max-w-[95%]">
          {data.description}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}

export default function Datasets() {
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [order, setOrder] = useState<"-" | "">("-");
  const [orderBy, setOrderBy] = useState<string>("created_at");
  const [currentPage, setPage] = React.useState(1);
  const [pageSize, setLimit] = React.useState(1000);
  const [models, setModels] = React.useState([]);

  const [searchValue, setSearch] = React.useState("");
  const debouncedSearchValue = useDebounce(searchValue, 300);

  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step } =
    useDrawer();
  const {
    getDataset,
    totalDataset,
    dataset,
    selectedDataset,
    setSelectedDataset,
    setSelecteUnselectAllDataset,
    stepTwoDataset,
  } = usePerfomanceBenchmark();
  const [selectAllDataset, setSelectAllDataset] = useState<boolean>(false);

  const [tempFilter, setTempFilter] = useState<any>({});
  const [filter, setFilter] = useState<{
    name?: string;
  }>(defaultFilter);

  // Load all datasets once on mount
  const load = useCallback(async () => {
    getDataset({
      page: currentPage,
      limit: pageSize,
      order_by: `${order}${orderBy}`,
    });
  }, [currentPage, pageSize]);

  useEffect(() => {
    load();
  }, []);

  // Frontend filtering with debounced search
  const filteredDataset = useMemo(() => {
    if (!dataset) return [];
    if (!debouncedSearchValue.trim()) return dataset;

    const searchLower = debouncedSearchValue.toLowerCase().trim();
    return dataset.filter((item: Dataset) =>
      item.name?.toLowerCase().includes(searchLower) ||
      item.description?.toLowerCase().includes(searchLower) ||
      item.filename?.toLowerCase().includes(searchLower)
    );
  }, [dataset, debouncedSearchValue]);

  useEffect(() => {
    console.log("selectedDataset", selectedDataset);
  }, [selectedDataset]);

  const handleOpenChange = (open) => {
    setFilterOpen(open);
    // setTempFilter(filter);
  };

  const resetFilter = () => {
    setTempFilter(defaultFilter);
    setFilter(defaultFilter);
  };

  const handleSelectAll = () => {
    setSelectAllDataset(!selectAllDataset);
    setSelecteUnselectAllDataset(selectAllDataset);
  };

  return (
    <BudForm
      data={{}}
      disableNext={!selectedDataset.length}
      onNext={async () => {
        stepTwoDataset().then((result) => {
          if (result) {
            openDrawerWithStep("Select-Cluster");
          }
        });
      }}
      backText="Back"
      onBack={() => {
        openDrawerWithStep("model_benchmark");
      }}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Datasets"
            description="Pick the specific dataset you want to perform the benchmark"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DrawerCard>
            <div className="flex items-center justify-between gap-[0.625rem] pt-[.6rem] pb-[1.5rem]">
              <SearchHeaderInput
                placeholder="Dataset names"
                searchValue={searchValue}
                expanded
                setSearchValue={setSearch}
                classNames="border border-[.5px] border-[#757575]"
              />
              {/* <div>
                <Popover
                  placement="bottomRight"
                  arrow={false}
                  open={filterOpen}
                  onOpenChange={handleOpenChange}
                  content={
                    <div className="bg-[#111113] shadow-none  border border-[#1F1F1F] rounded-[6px] width-348">
                      <div className="p-[1.5rem] flex items-start justify-start flex-col">
                        <div className="text-[#FFFFFF] text-14 font-400">
                          Filter
                        </div>
                        <div className="text-12 font-400 text-[#757575]">
                          Apply the following filters to find model of your
                          choice.
                        </div>
                      </div>
                      <div className="height-1 bg-[#1F1F1F] mb-[1.5rem] w-full"></div>
                      <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">
                        <div
                          className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                        >
                          <div className="w-full">
                            <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                              Role
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
                                  boxShadowSecondary: "none",
                                },
                              }}
                            >
                              <Select
                                variant="borderless"
                                placeholder="Select Role"
                                style={{
                                  backgroundColor: "transparent",
                                  color: "#EEEEEE",
                                  border: "0.5px solid #757575",
                                  width: "100%",
                                }}
                                size="large"
                                value={tempFilter.role || undefined}
                                className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
                                options={UserRoles.map((item, index) => ({
                                  label: item.label,
                                  value: item.value,
                                }))}
                                onChange={(value) => {
                                  setTempFilter({ ...tempFilter, role: value });
                                }}
                              />
                            </ConfigProvider>
                          </div>
                        </div>
                        <div
                          className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                        >
                          <div className="w-full">
                            <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                              Status
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
                                placeholder="Select Status"
                                style={{
                                  backgroundColor: "transparent",
                                  color: "#EEEEEE",
                                  border: "0.5px solid #757575",
                                  width: "100%",
                                }}
                                size="large"
                                value={tempFilter.status || undefined}
                                className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.5rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]  outline-none"
                                options={UserStatus?.map((item, index) => ({
                                  label: item.label,
                                  value: item.value,
                                }))}
                                onChange={(value) => {
                                  setTempFilter({
                                    ...tempFilter,
                                    status: value,
                                  });
                                }}
                              />
                            </ConfigProvider>
                          </div>
                        </div>

                        <div className="flex items-center justify-between">
                          <SecondaryButton
                            type="button"
                            onClick={resetFilter}
                            classNames="!px-[.8rem] tracking-[.02rem] mr-[.5rem]"
                          >
                            Reset
                          </SecondaryButton>
                          <PrimaryButton
                            type="submit"
                            onClick={null}
                            classNames="!px-[.8rem] tracking-[.02rem]"
                          >
                            Apply
                          </PrimaryButton>
                        </div>
                      </div>
                    </div>
                  }
                  trigger={["click"]}
                >
                  <label
                    className="h-[1.7rem] text-[#FFFFFF] mx-[.1rem] flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                    onClick={() => {}}
                  >
                    <MixerHorizontalIcon
                      style={{ width: "0.875rem", height: "0.875rem" }}
                      className=""
                    />
                  </label>
                </Popover>
              </div> */}
            </div>
            <div className="flex items-center justify-between pt-[.45rem]">
              <div className="flex items-center justify-start gap-[.2rem]">
                <Text_12_400_757575>
                  Datasets Available&nbsp;
                </Text_12_400_757575>
                <Text_12_600_EEEEEE>
                  {debouncedSearchValue ? `${filteredDataset.length} / ${totalDataset}` : totalDataset}
                </Text_12_600_EEEEEE>
              </div>
              <div className="flex items-center justify-start gap-[.7rem]">
                <Text_12_600_EEEEEE>Select All</Text_12_600_EEEEEE>
                <Checkbox
                  checked={selectAllDataset}
                  className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                  onChange={handleSelectAll}
                />
              </div>
            </div>
          </DrawerCard>
          <div className="">
            {filteredDataset?.length > 0 ? (
              <>
                {filteredDataset?.map((data: Dataset, index) => (
                  <CardWithCheckBox
                    key={data.id || index}
                    data={data}
                    handleClick={() => {
                      setSelectedDataset(data);
                    }}
                    selected={selectedDataset?.some(
                      (selected) => selected.id === data.id,
                    )}
                  />
                ))}
              </>
            ) : (
              <div className="flex justify-center items-center min-h-[4rem]">
                <Text_12_300_EEEEEE>
                  {debouncedSearchValue ? "No datasets match your search" : "No dataset available"}
                </Text_12_300_EEEEEE>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
