import SearchHeaderInput from "@/flows/components/SearchHeaderInput";
import { Text_12_300_EEEEEE, Text_12_400_757575, Text_12_400_EEEEEE, Text_14_400_EEEEEE, Text_16_600_FFFFFF } from "../../text";
import { PrimaryButton, SecondaryButton } from "../form/Buttons";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import CustomPopover from "@/flows/components/customPopover";
import { ConfigProvider, Image, Popover, Select, Table } from "antd";
import type { TableProps } from 'antd';
import React, { useCallback, useEffect, useState } from "react";
import { assetBaseUrl } from "@/components/environment";
import { formatDate } from "@/utils/formatDate";
import { useDrawer } from "@/hooks/useDrawer";
import { Credentials, useProprietaryCredentials } from "@/stores/useProprietaryCredentials";
import { useCloudProviders } from "@/hooks/useCloudProviders";
import { Plus } from 'lucide-react';
import { useLoader } from "@/context/authContext";

const defaultFilter = {
  name: undefined as string | undefined,
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


const capitalize = (str: string) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();


type ColumnsType<T extends object> = TableProps<T>['columns'];
type TablePagination<T extends object> = NonNullable<Exclude<TableProps<T>['pagination'], boolean>>;
type TablePaginationPosition<T extends object> = NonNullable<
  TablePagination<T>['position']
>[number];

const CredentialsListTable = () => {
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { openDrawer } = useDrawer();
  const [searchValue, setSearchValue] = useState('');
  const { credentials, getCredentials, totalCredentials, setSelectedCredential, selectedCredential, getProviderInfo, getProprietaryCredentialDetails, selectedProvider } = useProprietaryCredentials();
  const [order, setOrder] = useState<'-' | ''>('-');
  const [orderBy, setOrderBy] = useState<string>('created_at');
  const [filterOpen, setFilterOpen] = useState<boolean>(false);
  const [tempFilter, setTempFilter] = useState(defaultFilter);
  const [filter, setFilter] = useState(defaultFilter);
  const { getProviders, providers } = useCloudProviders();
  const [clearFilter, setClearFilter] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const handleOpenChange = (open: boolean) => {
    setFilterOpen(open);
  }

  useEffect(() => {
    getProviders();
  }, [getProviders]);
  useEffect(() => {
    console.log("searchValue", searchValue);
  }, [searchValue]);

  const load = useCallback(async () => {
    showLoader();
    getCredentials({
      ...filter,
      page: currentPage,
      limit: pageSize,
      name: searchValue ? searchValue : undefined,
      search: !!searchValue,
      order_by: `${order}${orderBy}`,
      type: tempFilter?.name
    });
    hideLoader();
  }, [currentPage, pageSize, getCredentials, searchValue]);


  useEffect(() => {
    // debounce
    const timer = setTimeout(() => {
      load();
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, order, orderBy, filter, currentPage, pageSize]);

  const resetFilter = () => {
    setTempFilter(defaultFilter);
    setClearFilter(true);
    setFilter(defaultFilter);
  }

  useEffect(() => {
    if (clearFilter) {
      applyFilter();
    }
  }, [clearFilter])

  const applyFilter = () => {
    if (tempFilter.name) {
      const timer = setTimeout(() => {
        getCredentials({
          ...filter,
          page: currentPage,
          limit: pageSize,
          name: searchValue ? searchValue : undefined,
          search: !!searchValue,
          order_by: `${order}${orderBy}`,
          type: tempFilter?.name
        });
      }, 500);
      setFilterOpen(false)
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        getCredentials({
          ...filter,
          page: currentPage,
          limit: pageSize,
          name: searchValue ? searchValue : undefined,
          search: !!searchValue,
          order_by: `${order}${orderBy}`,
        });
      }, 500);
      setFilterOpen(false);
      setClearFilter(false);
      return () => clearTimeout(timer);
    }

  }
  const handlePageChange = (currentPage: number, pageSize: number) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };

  return (
    <div className='pb-[60px] pt-[.4rem] relative CommonCustomPagination'>
      <Table<Credentials>
        onChange={(pagination, filters, sorter, extra) => {
          if (!Array.isArray(sorter) && sorter.field) {
            setOrder(sorter.order === 'ascend' ? '' : '-')
            setOrderBy(sorter.field as string)
          }
        }}
        columns={[
          {
            title: 'Credential Name',
            dataIndex: 'name',
            key: 'name',
            width: 150,
            render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
            sorter: (a, b) => a.name.localeCompare(b.name),
            sortOrder: orderBy === 'name' ? order === '-' ? 'descend' : 'ascend' : undefined,
            sortIcon: SortIcon,
            onHeaderCell: () => ({
              className: "always-show-sorter",
            }),
          },
          {
            title: 'Provider Name',
            dataIndex: 'provider_icon',
            key: 'provider_icon',
            width: 150,
            render: (_, record: Credentials) => <div className='select-none flex items-center'>
              <div className='w-[0.875rem] h-[0.875rem]'>
                <Image src={`${assetBaseUrl}${record.provider_icon}`}
                  preview={false}
                  style={{ width: '0.875rem' }}
                />
              </div>
              <Text_12_300_EEEEEE className='flex-auto truncate max-w-[90%]' style={{ marginLeft: 10 }}>{record.type}</Text_12_300_EEEEEE>
            </div>,
            sorter: (a, b) => a.type.localeCompare(b.type),
            sortOrder: orderBy === 'provider_icon' ? order === '-' ? 'descend' : 'ascend' : undefined,
            sortIcon: SortIcon,
          },
          {
            title: 'Total Number of Deployments',
            dataIndex: 'num_of_endpoints',
            key: 'num_of_endpoints',
            width: 150,
            render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
            sorter: (a, b) => a.num_of_endpoints - b.num_of_endpoints,
            sortOrder: orderBy === 'num_of_endpoints' ? order === '-' ? 'descend' : 'ascend' : undefined,
            sortIcon: SortIcon,
          },
          {
            title: 'Created On',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (text) => <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>,
            sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
            sortOrder: orderBy === 'created_at' ? order === '-' ? 'descend' : 'ascend' : undefined,
            sortIcon: SortIcon,
            defaultSortOrder: 'ascend'

          }
        ]}

        // pagination={false}
        pagination={{
          className: 'small-pagination',
          current: currentPage,
          pageSize: pageSize,
          total: totalCredentials,
          onChange: handlePageChange,
          showSizeChanger: true,
          pageSizeOptions: ['5', '10', '20', '50'],
        }}
        dataSource={credentials}
        bordered={false}
        footer={() => null}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async event => {
              const data = record as Credentials
              await getProprietaryCredentialDetails(record.id)
              setSelectedCredential(data);
              openDrawer("view-credentials")
            }
          }
        }}
        showSorterTooltip={false}
        title={() => (
          <div className='flex justify-between items-center px-[0.75rem] py-[1rem]'>
            <Text_16_600_FFFFFF className='text-[#EEEEEE]'  >
              Credential List
            </Text_16_600_FFFFFF>
            <div className='flex items-center justify-between'>
              <SearchHeaderInput
                placeholder={'Search by name'}
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
                    className="shadow-none bg-[#161616] border border-[#1F1F1F] rounded-[6px] width-296">
                    <div className="p-[1.45rem] pb-[1.4rem] pt-[1.2rem] flex items-start justify-start flex-col border-b-[1px] border-b-[#1F1F1F]">
                      <Text_14_400_EEEEEE>Filter</Text_14_400_EEEEEE>
                      <Text_12_400_757575 className="leading-[1.07rem] mt-[.38rem]">Apply the following filters to find worker of your choice.</Text_12_400_757575>
                    </div>
                    <div className="w-full flex flex-col gap-size-20 px-[1.45rem] pb-[1.4rem] pt-[1.9rem]">
                      <div
                        className={`rounded-[6px] relative !bg-[transparent] !w-[100%]`}
                      >
                        <div className="w-full">
                          <Text_12_300_EEEEEE className="absolute bg-[#161616] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap px-[.3rem]">
                            Provider
                            <CustomPopover title="This is the Provider" >
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
                              placeholder="Select Provider"
                              style={{
                                backgroundColor: "transparent",
                                color: "#EEEEEE",
                                border: "0.5px solid #757575",
                                width: "100%",
                              }}
                              value={tempFilter?.name}
                              size="large"
                              className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
                              options={providers?.map((provider) => ({
                                label: provider.name,
                                value: provider.id,
                              })) || []}
                              onChange={(value) => {
                                const selectedProvider = providers.find((provider) => provider.id === value);
                                setTempFilter({ ...tempFilter, name: selectedProvider?.type });
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
                  <MixerHorizontalIcon
                    style={{ width: '0.875rem', height: '0.875rem' }}
                    className="text-[#B3B3B3] group-hover:text-[#FFFFFF]"
                  // className="mr-2"
                  />
                </label>
              </Popover>
              <PrimaryButton
                onClick={() => {
                  // reset();
                  openDrawer("add-credentials")
                }}
              >
                <div className='flex items-center justify-center text-[0.8125rem]'>
                  <Plus className="w-[.85rem]" />&nbsp;Add Credentials
                </div>
              </PrimaryButton>
            </div>
          </div>
        )}
      />
    </div>
  );
}

export default CredentialsListTable;