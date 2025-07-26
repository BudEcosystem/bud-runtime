"use client";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import {
  Ibm_12_500_EEEEEE,
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_26_600_EEEEEE,
} from "@/components/ui/text";
import { useLoader } from "src/context/appContext";
import { ConfigProvider, Flex, Popover, Table } from "antd";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import { useProjects } from "src/hooks/useProjects";
import DashBoardLayout from "src/pages/home/layout";
import { TableProps, Image } from "antd";
import Tags from "src/flows/components/DrawerTags";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import CustomSelect from "src/flows/components/CustomSelect";
import CustomInput from "src/flows/components/CustomInput";
import CustomPopover from "src/flows/components/customPopover";
import { PromptDetail, useEndPoints } from "src/hooks/useEndPoint";
import { formatDate } from "src/utils/formatDate";
import CustomDatepicker from "src/flows/components/CustomDatePicker";
import type { DatePickerProps } from "antd";
import { DatePicker } from "antd";
import React from "react";
import { set } from "date-fns";
import { useCluster } from "src/hooks/useCluster";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
const defaultFilter = {
  min_score: 0,
  max_score: 10,
  created_at: "",
};

const promptKeys = [
  {
    title: "Harmfulness",
    key: "harmfulness",
  },
  {
    title: "Hallucinations",
    key: "hallucination",
  },
  {
    title: "Sensitive Information",
    key: "sensitive_info",
  },
  {
    title: "Prompt Injection",
    key: "prompt_injection",
  },
];

const HarmfulnessPromptList = () => {
  const [filter, setFilter] = useState<{
    min_score?: any;
    max_score?: any;
    created_at?: any;
  }>(defaultFilter);
  const [tempFilter, setTempFilter] = useState<any>({});
  const [filterReset, setFilterReset] = useState(false);
  const { selectedProject, getProject } = useProjects();
  const { getClusterById } = useCluster();
  const {
    getInferenceQualityPrompts,
    inferenceQualityPrompts,
    totalRecords,
    pageSource,
    clusterDetails,
    getEndpointClusterDetails,
    pageTitle,
    setPromptPage
  } = useEndPoints();
  const [copyText, setCopiedText] = useState<string>("Copy");
  const { showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [showPrompt, setShowPrompt] = useState<boolean>(false);
  const { projectId, clustersId, deploymentId } = router.query;
  const [order, setOrder] = useState<"-" | "">("-");
  const [orderBy, setOrderBy] = useState<string>("field1");
  const [promptDetail, setPromptDetail] = useState<PromptDetail>();
  const [searchValue, setSearchValue] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [isMounted, setIsMounted] = useState(false);
  const [filterOpen, setFilterOpen] = React.useState(false);

  // Get last route segment
  const lastSegment = router.asPath.split('/').filter(Boolean).pop();

  // Find matching title
  const matched = promptKeys.find(item => item.key === lastSegment);
  const matchedTitle = matched ? matched.title : 'Unknown';

  const handlePageChange = (currentPage, pageSize) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };
  const handleOpenChange = (open) => {
    setFilterOpen(open);
    setTempFilter(filter);
  };
  type ColumnsType<T extends object> = TableProps<T>["columns"];

  const handleCopy = (text: string) => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        // message.success('Text copied to clipboard!');
        setCopiedText("Copied..");
      })
      .catch(() => {
        // message.error('Failed to copy text.');
        setCopiedText("Failed to copy");
      });
  };

  useEffect(() => {
    setTimeout(() => {
      setCopiedText("Copy");
    }, 3000);
  }, [copyText]);

  useEffect(() => {
    if (!router.isReady) return;
    console.log("router.isReady", router);
    console.log("query", router.query);
  }, [router.isReady]);

  const initialLoad = async () => {
    showLoader();
    // if (!selectedProject || selectedProject.id !== projectId && projectId) {
    //   await getProject(projectId as string);
    // }
    if (projectId) {
      await getProject(projectId as string);
    }
    if (clustersId) {
      getClusterById(clustersId as string);
    }
    if (deploymentId) {
      await getEndpointClusterDetails(deploymentId as string, projectId as string);
    }
    hideLoader();
  }

  useEffect(() => {
    if (projectId || clustersId && deploymentId) {
      initialLoad();
    }
  }, [projectId, clustersId, deploymentId]);

  const textToCopy1 = promptDetail?.prompt;
  const textToCopy2 = promptDetail?.response;

  const applyFilter = () => {
    setFilterOpen(false);
    if (deploymentId) {
      setFilter(tempFilter);
      load();
    }
    setFilterReset(false);
  };

  const clearFilter = () => {
    setTempFilter({ defaultFilter });
    setCurrentPage(1);
    setFilterReset(true);
    // setFilterOpen(false);
    // load();
  };

  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  const load = async () => {
    showLoader();
    await getInferenceQualityPrompts(
      {
        ...filter,
        page: currentPage,
        limit: pageSize,
        name: searchValue ? searchValue : undefined,
        search: !!searchValue,
        order_by: `${order}${orderBy}`,
      },
      deploymentId as string
    );
    hideLoader();
  };

  useEffect(() => {
    if (!deploymentId) return;
    load();
  }, [currentPage, pageSize, searchValue, filter]);


  useEffect(() => {
    setPromptPage(matched?.key, matchedTitle)
    setTimeout(() => {
      load();
    }, 500);
  }, [deploymentId]);


  const goBack = () => {
    if (showPrompt) {
      setShowPrompt(false);
      return;
    }
    router.back();
  };

  const toPromptDetail = (data) => {
    setPromptDetail(data);
    setShowPrompt(true);
  };
  const onChange: DatePickerProps["onChange"] = (date, dateString) => {
    console.log(date, dateString);
  };

  interface DataType {
    score: string;
    created_at: string;
    prompt: string;
    response: string;
  }

  const columns: ColumnsType<DataType> = [
    {
      title: "Prompt Score",
      dataIndex: "score",
      key: "score",
      width: 135,
      render: (text) => (
        <Text_12_400_EEEEEE className="whitespace-nowrap">
          {text}
        </Text_12_400_EEEEEE>
      ),
      sorter: (a, b) => a.score.localeCompare(b.score),
      sortIcon: SortIcon,
    },
    {
      title: "Created On",
      dataIndex: "created_at",
      key: "created_at",
      width: 130,
      render: (text) => (
        <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>
      ),
      sorter: (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      sortIcon: SortIcon,
    },
    {
      title: "Prompt",
      dataIndex: "prompt",
      key: "prompt",
      width: 200,
      render: (text) => (
        <Text_12_400_EEEEEE className="whitespace-nowrap text-ellipsis overflow-hidden	w-[100%] max-w-[200px]">
          {text}
        </Text_12_400_EEEEEE>
      ),
      sorter: (a, b) => a.prompt.localeCompare(b.prompt),
      sortIcon: SortIcon,
    },
    {
      title: "Response",
      key: "response",
      dataIndex: "response",
      width: 200,
      render: (text) => (
        <Text_12_400_EEEEEE className="whitespace-nowrap text-ellipsis overflow-hidden	w-[100%] max-w-[200px]">
          {text}
        </Text_12_400_EEEEEE>
      ),
      sorter: (a, b) => a.response.localeCompare(b.response),
      sortIcon: SortIcon,
    },
  ];

  const content = (
    // bg-[#161616]
    <div className="mt-[.55rem] border border-[1px] border-[#1F1F1F] rounded-[6px] bg-[#161616] max-w-[296px]">
      <div className="border-b-[1px] border-b-[#1F1F1F] p-[1.4rem] flex items-start justify-start flex-col gap-y-[.5rem]">
        <Text_14_400_EEEEEE>Filter</Text_14_400_EEEEEE>
        <Text_12_400_757575>
          Apply the following filters to find worker of your choice.
        </Text_12_400_757575>
      </div>
      <div className="w-full flex flex-col gap-size-20 px-[1.4rem] pb-[1.5rem] pt-[1.9rem] max-h-[245px] overflow-y-auto">
        <CustomInput
          suffix={<span></span>}
          name="min_score"
          label="Prompt Score Min"
          placeholder="Enter Prompt Score Min"
          info="Enter the minimum score for the prompt"
          rules={[
            { required: false, message: "Please enter Prompt Score Min" },
          ]}
          value={tempFilter.min_score}
          onChange={(value) => {
            setTempFilter({
              ...tempFilter,
              min_score: value,
            });
          }}
          ClassNames="mt-[.4rem]"
        />
        <CustomInput
          suffix={<span></span>}
          name="max_score"
          label="Prompt Score Max"
          info="Enter the maximum score for the prompt"
          placeholder="Enter Prompt Score Max"
          rules={[
            { required: false, message: "Please enter Prompt Score Max" },
          ]}
          value={tempFilter.max_score}
          onChange={(value) => {
            setTempFilter({
              ...tempFilter,
              max_score: value,
            });
          }}
          ClassNames="mt-[.4rem]"
        />
        {/* <DatePicker
            format={"MM/DD/YYYY"}
            onChange={onChange}
            /> */}
        <CustomDatepicker
          name="created_at"
          label="Created On"
          placeholder="Enter date"
          rules={[{ required: false, message: "Please enter date" }]}
          ClassNames="mt-[.4rem]"
          value={tempFilter.created_at}
          onChange={(value) => {
            setTempFilter({
              ...tempFilter,
              created_at: value,
            });
          }}
        />

        <div className="flex items-center justify-between gap-2">
          <SecondaryButton
            type="button"
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
      </div>
    </div>
  );



  const HeaderContent = () => {
    return (
      <div className="flex justify-between items-center">
        {isMounted && router.isReady && (
          <div className="flex justify-start items-center">
            <BackButton onClick={goBack} />
            <CustomBreadcrumb
              data={[
                projectId ? "Projects" : "Clusters",
                `${selectedProject?.icon || clusterDetails?.cluster?.icon} ${selectedProject?.name || clusterDetails?.cluster?.name}`,
                `${clusterDetails?.name}`,
                `${matchedTitle}`,
              ]}
              urls={[
                `/${projectId ? 'projects' : 'clusters'}`,
                `/${projectId?'projects':'clusters'}/${projectId || clusterDetails?.cluster?.id}`,
                `/${projectId?'projects':'clusters'}/${projectId || clusterDetails?.cluster?.id}/deployments/${deploymentId || clusterDetails?.id}`,
                ``,
              ]}
            />

          </div>
        )}
      </div>
    );
  };

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <DashBoardLayout headerItems={<HeaderContent />}>
      <div className="boardPageView">
        <div className="boardPageTop pt-[1.7rem] flex items-center gap-4 justify-between flex-row !mb-[.4rem]">
          <div className="w-full ">
            <Text_26_600_EEEEEE className="leading-[100%]">
              {pageTitle} Prompt list
            </Text_26_600_EEEEEE>
            <Text_12_400_757575 className="mt-[.2rem]">
              Below are the {pageTitle} prompt list of{" "}
              {clusterDetails?.cluster?.name}
            </Text_12_400_757575>
          </div>
          {/* <div className="flex-row flex gap-2">
              <button type="button" onClick={() => { }}>
                <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 14" fill="none">
                  <path fillRule="evenodd" clipRule="evenodd" d="M5.13327 0.898438C4.85713 0.898438 4.63327 1.1223 4.63327 1.39844C4.63327 1.67458 4.85713 1.89844 5.13327 1.89844H8.8666C9.14274 1.89844 9.3666 1.67458 9.3666 1.39844C9.3666 1.1223 9.14274 0.898438 8.8666 0.898438H5.13327ZM2.7666 3.2651C2.7666 2.98896 2.99046 2.7651 3.2666 2.7651H10.7333C11.0094 2.7651 11.2333 2.98896 11.2333 3.2651C11.2333 3.54125 11.0094 3.7651 10.7333 3.7651H10.2661C10.2664 3.77617 10.2666 3.78728 10.2666 3.79844V11.1318C10.2666 11.6841 9.81889 12.1318 9.2666 12.1318H4.73327C4.18098 12.1318 3.73327 11.6841 3.73327 11.1318V3.79844C3.73327 3.78728 3.73345 3.77617 3.73381 3.7651H3.2666C2.99046 3.7651 2.7666 3.54125 2.7666 3.2651ZM9.2666 3.79844L4.73327 3.79844V11.1318L9.2666 11.1318V3.79844Z" fill="#B3B3B3" />
                </svg>
              </button>
              <button type="button" onClick={() => { }}>
                <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 16 16" fill="none">
                  <path fillRule="evenodd" clipRule="evenodd" d="M7.54429 0.695312C7.12079 0.695312 6.7537 0.988495 6.66007 1.40152L6.40611 2.5217C6.00184 2.63926 5.61619 2.80026 5.2546 2.9992L4.28286 2.38663C3.9246 2.16079 3.45772 2.21305 3.15826 2.51251L2.51176 3.15901C2.2123 3.45847 2.16004 3.92536 2.38588 4.28362L2.99866 5.25571C2.7999 5.6172 2.63904 6.00273 2.52159 6.40685L1.40152 6.66078C0.988495 6.75442 0.695312 7.12151 0.695312 7.54501V8.4593C0.695312 8.8828 0.988495 9.24989 1.40152 9.34353L2.52172 9.59748C2.63924 10.0017 2.80019 10.3873 2.99906 10.7489L2.38638 11.7208C2.16054 12.0791 2.2128 12.546 2.51226 12.8454L3.15876 13.4919C3.45822 13.7914 3.9251 13.8437 4.28336 13.6178L5.25535 13.0051C5.61672 13.2039 6.00212 13.3647 6.40611 13.4822L6.66007 14.6024C6.7537 15.0154 7.12079 15.3086 7.54429 15.3086H8.45858C8.88208 15.3086 9.24917 15.0154 9.34281 14.6024L9.59667 13.4826C10.001 13.3651 10.3867 13.2042 10.7484 13.0054L11.7203 13.618C12.0786 13.8439 12.5454 13.7916 12.8449 13.4922L13.4914 12.8457C13.7909 12.5462 13.8431 12.0793 13.6173 11.7211L13.0048 10.7495C13.2039 10.3877 13.3649 10.0019 13.4825 9.59741L14.6024 9.34353C15.0154 9.24989 15.3086 8.8828 15.3086 8.4593V7.54501C15.3086 7.12151 15.0154 6.75442 14.6024 6.66078L13.4826 6.40693C13.3651 6.00256 13.2041 5.61681 13.0052 5.25514L13.6178 4.2834C13.8436 3.92514 13.7914 3.45826 13.4919 3.15879L12.8454 2.5123C12.5459 2.21283 12.0791 2.16058 11.7208 2.38642L10.7491 2.99894C10.3873 2.79989 10.0013 2.63883 9.59667 2.52128L9.34281 1.40152C9.24917 0.988495 8.88208 0.695312 8.45858 0.695312H7.54429ZM5.25052 4.0684C5.81234 3.67467 6.46238 3.39825 7.16508 3.27467L7.54429 1.60198H8.45858L8.83774 3.27443C9.5408 3.39785 10.1912 3.67428 10.7533 4.06811L12.2043 3.15341L12.8508 3.7999L11.9361 5.25098C12.3298 5.8129 12.6061 6.46306 12.7295 7.16587L14.4019 7.54501V8.4593L12.7295 8.83846C12.6059 9.54137 12.3295 10.1916 11.9356 10.7536L12.8503 12.2046L12.2038 12.8511L10.7526 11.9362C10.1907 12.3298 9.54053 12.6061 8.83774 12.7295L8.45858 14.4019H7.54429L7.16508 12.7292C6.46265 12.6057 5.81285 12.3294 5.25119 11.936L3.79987 12.8508L3.15337 12.2043L4.06823 10.7531C3.67459 10.1912 3.39825 9.54121 3.27475 8.83853L1.60198 8.4593V7.54501L3.27468 7.1658C3.39809 6.46322 3.6743 5.81328 4.06778 5.25148L3.15287 3.80012L3.79937 3.15362L5.25052 4.0684ZM9.62721 8.00064C9.62721 8.89897 8.89897 9.62721 8.00064 9.62721C7.1023 9.62721 6.37406 8.89897 6.37406 8.00064C6.37406 7.1023 7.1023 6.37406 8.00064 6.37406C8.89897 6.37406 9.62721 7.1023 9.62721 8.00064ZM10.5872 8.00064C10.5872 9.42916 9.42916 10.5872 8.00064 10.5872C6.57211 10.5872 5.41406 9.42916 5.41406 8.00064C5.41406 6.57211 6.57211 5.41406 8.00064 5.41406C9.42916 5.41406 10.5872 6.57211 10.5872 8.00064Z" fill="#B3B3B3" />
                </svg>
              </button>
            </div> */}
        </div>
        {!showPrompt ? (
          <div className="deploymentDetailsTable tablePadding pb-[60px] CommonCustomPagination">
            <Table<DataType>
              className="min-h-[60vh]"
              columns={columns}
              // pagination={false}
              pagination={{
                className: "small-pagination",
                current: currentPage,
                pageSize: pageSize,
                total: totalRecords,
                onChange: handlePageChange,
                showSizeChanger: true,
                pageSizeOptions: ["5", "10", "20", "50"],
              }}
              dataSource={inferenceQualityPrompts?.items}
              bordered={false}
              footer={null}
              virtual
              onRow={(record, rowIndex) => {
                return {
                  onClick: async (event) => {
                    toPromptDetail(record);
                  },
                };
              }}
              showSorterTooltip={false}
              title={() => (
                <div className="flex justify-between items-center px-[0.75rem] py-[.5rem] pb-[1rem] pt-[1.2rem]">
                  <div className="flex justify-start items-center gap-[.4rem]"></div>
                  <div className="flex items-center justify-end gap-x-[.5rem]">
                    <SearchHeaderInput
                      searchValue={searchValue}
                      setSearchValue={(value) => { setSearchValue(value) }}
                    />
                    <div className=" filterPopup">
                      <ConfigProvider
                        theme={{
                          token: {
                            sizePopupArrow: 0,
                          },
                        }}
                        getPopupContainer={(trigger) =>
                          (trigger.parentNode as HTMLElement) || document.body
                        }
                      >
                        <Popover
                          open={filterOpen}
                          onOpenChange={handleOpenChange}
                          content={content}
                          title=""
                          trigger="click"
                          placement="bottomRight"
                        >
                          <MixerHorizontalIcon
                            style={{ width: "0.875rem", height: "0.875rem" }}
                            className=""
                          />
                        </Popover>
                      </ConfigProvider>
                    </div>
                  </div>
                </div>
              )}
            />
          </div>
        ) : (
          <div className="border-t-[1px] border-t-[#1F1F1F] mt-[1rem] tablePadding pb-[90px]">
            <div className="flex justify-start items-center mt-[1.4rem]">
              <Tags
                name={`Prompt Score ${promptDetail?.score}`}
                color="#D1B854"
              />
            </div>
            <div className="mt-[1rem] flex justify-between items-start">
              <div className="w-[48%]">
                <Text_14_600_EEEEEE className="ml-[.1rem]">
                  Prompt
                </Text_14_600_EEEEEE>
                <div className="prompt-content-div mt-[.8rem] bg-[#121212] rounded-[8px] relative p-[1rem] flex-grow min-h-[7rem]">
                  <CustomPopover
                    title={copyText}
                    contentClassNames="py-[.3rem]"
                  >
                    <div
                      className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center absolute right-[.5rem] top-[.5rem] cursor-pointer hover:bg-[#1F1F1F]"
                      onClick={() => handleCopy(textToCopy1)}
                    >
                      <Image
                        preview={false}
                        src="/images/drawer/Copy.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </div>
                  </CustomPopover>
                  <Ibm_12_500_EEEEEE className="leading-[1rem] max-w-[96%]">
                    {textToCopy1}
                  </Ibm_12_500_EEEEEE>
                </div>
              </div>
              <div className="w-[48%]">
                <Text_14_600_EEEEEE className="ml-[.1rem]">
                  Response
                </Text_14_600_EEEEEE>
                <div className="prompt-content-div mt-[.8rem] bg-[#121212] rounded-[8px] relative  p-[1rem] flex-grow min-h-[7rem]">
                  <CustomPopover
                    title={copyText}
                    contentClassNames="py-[.3rem]"
                  >
                    <div
                      className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center absolute right-[.5rem] top-[.5rem] cursor-pointer hover:bg-[#1F1F1F]"
                      onClick={() => handleCopy(textToCopy2)}
                    >
                      <Image
                        preview={false}
                        src="/images/drawer/Copy.png"
                        alt="info"
                        style={{ width: ".75rem", height: ".75rem" }}
                      />
                    </div>
                  </CustomPopover>
                  <Ibm_12_500_EEEEEE className="leading-[1rem] max-w-[96%]">
                    {textToCopy2}
                  </Ibm_12_500_EEEEEE>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashBoardLayout>
  );
};

export default HarmfulnessPromptList;
