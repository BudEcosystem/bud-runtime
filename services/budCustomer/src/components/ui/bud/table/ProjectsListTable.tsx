import SearchHeaderInput from "@/flows/components/SearchHeaderInput";
import { Text_12_300_EEEEEE, Text_12_400_757575, Text_12_400_EEEEEE, Text_14_300_EEEEEE, Text_14_400_EEEEEE, Text_16_600_FFFFFF } from "../../text";
import { PrimaryButton, SecondaryButton } from "../form/Buttons";
import { Icon } from "@iconify/react";
import CustomPopover from "@/flows/components/customPopover";
import { ConfigProvider, Image, Popover, Select, Table } from "antd";
import React, { useCallback, useEffect, useState } from "react";
import { formatDate } from "@/utils/formatDate";
import { useDrawer } from "@/hooks/useDrawer";
import { Credentials, useCredentials } from "@/stores/useCredentials";
import { useProjects } from "@/hooks/useProjects";
import { Plus } from "lucide-react";
import { useLoader } from "@/context/appContext";
// inside table   ProjectTableList.tsx
const defaultFilter = {
  name: "",
}

interface DataType {
  key?: string;
  name?: string;
  provider?: string;
  deployments?: string;
  activeDeployments?: string;
  expiry?: string;
  last_used_at?: string;
  max_budget?: string;
  project?: string;
}


function SortIcon({ sortOrder }: { sortOrder: string | null }) {
  return sortOrder ? sortOrder === 'descend' ?
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z" fill="#B3B3B3" />
    </svg>
    : <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z" fill="#B3B3B3" />
    </svg>
    : null;
}

const ProjectsListTable = () => {
  const { isLoading, showLoader, hideLoader } = useLoader();
  const [filter, setFilter] = useState<
    {
      name?: string;
    }
  >(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [tempFilter, setTempFilter] = useState<any>();
  const { openDrawer } = useDrawer();
  const { getCredentials, totalCredentials, credentials, setSelectedCredential } = useCredentials();
  const [searchValue, setSearchValue] = useState('');
  const [order, setOrder] = useState<'-' | ''>('-');
  const [orderBy, setOrderBy] = useState<string>('last_used_at');
  const { projects, getProjects } = useProjects();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [closeFilter, setCloseFilter] = useState(false);

  useEffect(() => {
    getProjects(1, 100);
  }, []);
  useEffect(() => {
    console.log('projects', projects);
  }, [projects]);
  const handleOpenChange = (open: boolean) => {
    setFilterOpen(open);
    // setTempFilter(filter);
  };

  const resetFilter = () => {
    setTempFilter({ ...tempFilter, project: undefined });
    setCloseFilter(true);
    setFilterOpen(false)
  }
  useEffect(() => {
    if (closeFilter) {
      applyFilter();
    }
  }, [closeFilter])

  const applyFilter = () => {
    const timer = setTimeout(() => {
      getCredentials({
        ...filter,
        page: currentPage,
        limit: pageSize,
        name: searchValue ? searchValue : undefined,
        search: !!searchValue,
        order_by: `${order}${orderBy}`,
        project_id: tempFilter.project
      });
      setCloseFilter(false);
      setFilterOpen(false)
    }, 100);
    return () => clearTimeout(timer);
  }

  const load = useCallback(async () => {
    showLoader();
    getCredentials({
      ...filter,
      page: currentPage,
      limit: pageSize,
      name: searchValue ? searchValue : undefined,
      search: !!searchValue,
      order_by: `${order}${orderBy}`,
      project_id: tempFilter?.project
    });
    hideLoader();
  }, [currentPage, pageSize, getCredentials, searchValue, searchValue]);

  useEffect(() => {
    // debounce
    const timer = setTimeout(() => {
      load();
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, order, orderBy, filter, currentPage, pageSize]);

  const handlePageChange = (currentPage: number, pageSize: number) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };

  return (
    <div className='pb-[60px] pt-[.4rem] CommonCustomPagination'>
      <Table<Credentials>
        onChange={(pagination, filters, sorter, extra) => {
          const singleSorter = Array.isArray(sorter) ? sorter[0] : sorter;
          if (singleSorter && singleSorter.order && singleSorter.field) {
            setOrder(singleSorter.order === 'ascend' ? '' : '-')
            setOrderBy(singleSorter.field as string)
          }
        }}
        columns={[
          {
            title: 'Credential name',
            dataIndex: 'name',
            key: 'name',
            width: 150,
            render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
            sorter: (a, b) => a.name.localeCompare(b.name),
            sortIcon: SortIcon,
          },
          {
            title: 'Project Name',
            dataIndex: 'project',
            key: 'project',
            width: 150,
            render: (text) => <Text_12_400_EEEEEE>{text.name}</Text_12_400_EEEEEE>,
            sorter: (a, b) => String(a.project || '').localeCompare(String(b.project || '')),
            sortIcon: SortIcon,
          },
          {
            title: 'Date of Expiry',
            dataIndex: 'expiry',
            key: 'expiry',
            width: 150,
            render: (text) => <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>,
            sorter: (a, b) => new Date(a.expiry).getTime() - new Date(b.expiry).getTime(),
            sortIcon: SortIcon,
          },
          {
            title: 'Last Used',
            dataIndex: 'last_used_at',
            key: 'last_used_at',
            width: 150,
            render: (text) => <Text_12_400_EEEEEE>{text ? formatDate(text) : '-'}</Text_12_400_EEEEEE>,
            sorter: (a, b) => new Date(a.last_used_at).getTime() - new Date(b.last_used_at).getTime(),
            sortIcon: SortIcon,
            defaultSortOrder: 'descend'
          },
          {
            title: 'Max Budget',
            dataIndex: 'max_budget',
            key: 'max_budget',
            width: 150,
            render: (text) => <div className='select-none flex items-center'>
              <Text_12_300_EEEEEE className='flex-auto truncate max-w-[90%]' style={{ marginLeft: 10 }}>{text ? `$${text}` : '-'}</Text_12_300_EEEEEE>
            </div>,
            sorter: (a, b) =>
              String(a.max_budget || '').localeCompare(String(b.max_budget || '')),
            sortIcon: SortIcon,
          }
        ]}
        // pagination={false}
        pagination={{
          className: 'small-pagination',
          current: currentPage,
          pageSize: pageSize,
          total: totalCredentials ?? 0,
          onChange: handlePageChange,
          showSizeChanger: true,
          pageSizeOptions: ['5', '10', '20', '50'],
        }}
        dataSource={credentials}
        bordered={false}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async event => {
              const data = record as Credentials
              setSelectedCredential(data);
              openDrawer('view-project-credentials')
            }
          }
        }}
        showSorterTooltip={false}
        title={() => (
          <div className='flex justify-between items-center px-[0.75rem] py-[1rem]'>
            <Text_16_600_FFFFFF className='text-[#EEEEEE]'  >
              Credentials Per Project
            </Text_16_600_FFFFFF>
            <div className='flex items-center justify-between'>
              <SearchHeaderInput
                placeholder="Search by name"
                value={searchValue}
                onChange={setSearchValue}
              />
              <Popover
                color="#161616"
                arrow={false}
                className="!ml-[0.95rem] !mr-[.6rem]"
                open={filterOpen} onOpenChange={handleOpenChange}
                placement={'bottomRight'}
                content={
                  <div
                    className="bg-[#161616] shadow-none  border border-[#1F1F1F] rounded-[6px] width-296">
                    <div className="p-[1.45rem] pb-[1.4rem] pt-[1.2rem] flex items-start justify-start flex-col border-b-[1px] border-b-[#1F1F1F]">
                      <Text_14_400_EEEEEE>Filter</Text_14_400_EEEEEE>
                      <Text_12_400_757575 className="leading-[1.07rem] mt-[.38rem]">Apply the following filters to find worker of your choice.</Text_12_400_757575>
                    </div>
                    <div className="w-full flex flex-col gap-size-20 px-[1.45rem]  pb-[1.4rem] pt-[1.9rem]">
                      <div
                        className={`rounded-[6px] relative !bg-[transparent] !w-[100%]`}
                      >
                        <div className="w-full">
                          <Text_12_300_EEEEEE className="absolute bg-[#161616] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                            Project
                            <CustomPopover title="This is the Project" >
                              <Image
                                src="/images/info.png"
                                preview={false}
                                alt="info"
                                style={{ width: '.75rem', height: '.75rem' }}
                              />
                            </CustomPopover>
                          </Text_12_300_EEEEEE>
                        </div>
                        <div className="custom-select-two w-full rounded-[6px] relative">
                          <ConfigProvider
                            theme={{
                              token: {
                                colorTextPlaceholder: '#808080',
                                boxShadowSecondary: 'none',
                              },
                            }}
                          >
                            <Select
                              variant="borderless"
                              placeholder="Select Project"
                              style={{
                                backgroundColor: "transparent",
                                color: "#EEEEEE",
                                border: "0.5px solid #757575",
                                width: "100%",
                              }}
                              value={tempFilter?.project}
                              size="large"
                              className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
                              options={projects?.map((provider) => ({
                                label: provider.project.name,
                                value: provider.project.id,
                              })) || []}
                              onChange={(value) => {
                                setTempFilter({ ...tempFilter, project: value });
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
                          onClick={applyFilter}
                          classNames="!px-[.8rem] tracking-[.02rem]"
                        >
                          Apply
                        </PrimaryButton>
                      </div>
                    </div>

                  </div>
                }
                trigger={['click']} >
                <label
                  className="group h-[1.7rem] text-[#FFFFFF] mx-2 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                  onClick={() => { }}
                >
                  <Icon
                    icon="material-symbols:tune"
                    style={{ width: '0.875rem', height: '0.875rem' }}
                    className="text-[#B3B3B3] group-hover:text-[#FFFFFF]"
                  />
                </label>
              </Popover>
              <PrimaryButton
                onClick={() => {
                  openDrawer("add-new-key")
                }}
              >
                <div className='flex items-center justify-center ext-[0.8125rem]'>
                  <Plus className="w-[.85rem]" />&nbsp;Create New Key
                </div>
              </PrimaryButton>
            </div>
          </div>
        )}
      />
    </div>
  );
}

export default ProjectsListTable;
