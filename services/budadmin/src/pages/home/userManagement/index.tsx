/* eslint-disable react/no-unescaped-entities */
"use client";

import { MixerHorizontalIcon, PlusIcon } from "@radix-ui/react-icons";

import { useCallback, useEffect, useRef, useState } from "react";
import React from "react";
import DashBoardLayout from "../layout";
import { AppRequest } from "./../../api/requests";
import { successToast } from "./../../../components/toast";


import { useLoader } from "src/context/appContext";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { Button, Popover, Table, TableProps, Image, ConfigProvider, Select } from "antd";
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_12_400_757575 } from "@/components/ui/text";
import NoDataFount from "@/components/ui/noDataFount";
import { PrimaryButton, SecondaryButton } from "@/components/ui/bud/form/Buttons";
import PageHeader from "@/components/ui/pageHeader";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import CustomPopover from "src/flows/components/customPopover";
import { UserRoles, UserStatus, useUsers } from "src/hooks/useUsers";
import { useDrawer } from "src/hooks/useDrawer";
import NoAccess from "@/components/ui/noAccess";
// type PaginationPrevious = ... & React.ComponentProps<"button">
// testing
interface FormData {
  name: string;
  author: string;
  modality: string;
  type: string;
  source: string;
  uri: string;
  // hf_token: string;
  id: string;
  [key: string]: string;
}

interface User {
  name: string;
  email: string;
  role: string;
  status: string;
  id: string;
  color: string;
  user_type?: string;
  action?: any;
}

const defaultFilter = {
  name: "",
  email: "",
  role: "",
  status: "",
}

export default function UserManagement() {
  const [isMounted, setIsMounted] = useState(false);
  const { hasPermission } = useUser();

  const { isLoading, showLoader, hideLoader } = useLoader();

  // for pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const totalItems = 100;

  // Separate states for admin and client users
  const [activeTab, setActiveTab] = useState<'client' | 'admin'>('admin');
  const [adminCurrentPage, setAdminCurrentPage] = useState(1);
  const [clientCurrentPage, setClientCurrentPage] = useState(1);

  const { users, totalUsers, getUsers, getUsersDetails, userDetails, getUsersPermissions, userPermissions } = useUsers();
  const [tempFilter, setTempFilter] = useState<any>({});
  const [filter, setFilter] = useState<
    {
      name?: string;
      email?: string;
      role?: string;
      status?: string;
    }
  >(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [filterReset, setFilterReset] = useState(false);
  const { openDrawer } = useDrawer();

  type ColumnsType<T extends object> = TableProps<T>['columns'];
  type TablePagination<T extends object> = NonNullable<Exclude<TableProps<T>['pagination'], boolean>>;
  type TablePaginationPosition<T extends object> = NonNullable<
    TablePagination<T>['position']
  >[number];

  const handleOpenChange = (open) => {
    setFilterOpen(open);
    // setTempFilter(filter);
  };

  const resetFilter = () => {
    setCurrentPage(1);
    setFilterReset(true);
    setTempFilter(defaultFilter);
    setFilter(defaultFilter);
  };
  const applyFilter = () => {
    setFilterReset(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    load(tempFilter);
    setFilterOpen(false);
  };

  const load = useCallback(async (filter) => {
    if (hasPermission(PermissionEnum.UserManage)) {
      showLoader();
      const params = {
        page: activeTab === 'admin' ? adminCurrentPage : clientCurrentPage,
        limit: pageSize,
        name: filter.name,
        email: filter.email,
        role: filter.role,
        status: filter.status,
        order_by: '-created_at',
        user_type: activeTab,
      };
      await getUsers(params);
      hideLoader();
    }
  }, [activeTab, adminCurrentPage, clientCurrentPage, pageSize, getUsers, hasPermission, showLoader, hideLoader]);

  useEffect(() => {
    if (isMounted) {
      setTimeout(() => {
        load(filter);
      }, 1000);
    }
    // load(filter);
  }, [activeTab, adminCurrentPage, clientCurrentPage, pageSize, getUsers, isMounted, filter, load]);

  useEffect(() => {
    if (filterReset) {
      applyFilter()
    }
  }, [filterReset, applyFilter]);



  useEffect(() => {
    // debounce
    const timer = setTimeout(() => {
      load(filter);
      setCurrentPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [filter, load]);


  function SortIcon({ sortOrder }: { sortOrder: string }) {
    return sortOrder ? sortOrder === 'descend' ?
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
        <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z" fill="#B3B3B3" />
      </svg>
      : <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
        <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z" fill="#B3B3B3" />
      </svg>
      : null;
  }

  const openUserPermissions = async (data) => {
    const user = await getUsersDetails(data.id);
    if (user) {
      openDrawer('view-user');
    }
    getUsersPermissions(data.id)
  };

  const columns: ColumnsType<User> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{text}</Text_12_400_EEEEEE>,
      sorter: (a, b) => a.name.localeCompare(b.name),
      sortIcon: SortIcon,
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{text}</Text_12_400_EEEEEE>,
      sorter: (a, b) => a.email.localeCompare(b.email),
      sortIcon: SortIcon,
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (text) => <Text_12_400_EEEEEE className='whitespace-nowrap'>{capitalize(text)}</Text_12_400_EEEEEE>,
      sorter: (a, b) => a.role.localeCompare(b.role),
      sortIcon: SortIcon,
    },
    {
      title: 'Status',
      key: 'status',
      dataIndex: 'status',
      render: (text) => <div className="flex">
        <ProjectTags
          name={capitalize(text)}
          color={endpointStatusMapping[capitalize(text)]}
          textClass="text-[.75rem] py-[.22rem]"
          tagClass="py-[0rem]"
        />
      </div>,
      sorter: (a, b) => a.status.localeCompare(b.status),
      sortIcon: SortIcon,
    },
  ];

  const handlePageChange = (currentPage, pageSize) => {
    if (activeTab === 'admin') {
      setAdminCurrentPage(currentPage);
    } else {
      setClientCurrentPage(currentPage);
    }
    setPageSize(pageSize);
  };

  const getCurrentPage = () => {
    return activeTab === 'admin' ? adminCurrentPage : clientCurrentPage;
  };

  useEffect(() => {
    setIsMounted(true)
  }, []);

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardPageTop">

          <PageHeader
            headding="User Management"
            ButtonIcon={PlusIcon}
            buttonLabel={hasPermission(PermissionEnum.UserManage) ? "Add User" : ""}
            buttonAction={() => {
              openDrawer('add-user');
            }}
            rightComponent={hasPermission(PermissionEnum.UserManage) &&
              <>
                <SearchHeaderInput placeholder="Search by name or email" searchValue={
                  filter.name || filter.email || ""
                }
                  setSearchValue={(value) => {
                    setFilter({ ...filter, email: value, name: value });
                  }} />

                <Popover
                  placement="bottomRight"
                  arrow={false}
                  open={filterOpen}
                  onOpenChange={handleOpenChange}
                  content={
                    <div
                      className="bg-[#111113] shadow-none  border border-[#1F1F1F] rounded-[6px] width-348">
                      <div className="p-[1.5rem] flex items-start justify-start flex-col">
                        <div className="text-[#FFFFFF] text-14 font-400">
                          Filter
                        </div>
                        <div className="text-12 font-400 text-[#757575]">Apply the following filters to find users of your choice.</div>
                      </div>
                      <div className="height-1 bg-[#1F1F1F] mb-[1.5rem] w-full"></div>
                      <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">
                        <div
                          className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                        >
                          <div className="w-full">
                            <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                              Role
                              <CustomPopover title="Select user role" >
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
                              <CustomPopover title="Select user status" >
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
                                },
                                components: {
                                  Select: {
                                    // multipleItemHeightSM: 16
                                  }
                                }
                              }}
                            >
                              <Select
                                placeholder="Select Status"
                                style={{
                                  backgroundColor: "transparent",
                                  color: "#EEEEEE",
                                  border: "0.5px solid #757575",
                                  width: "100%"
                                }}
                                size="large"
                                value={tempFilter.status || undefined}
                                className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.5rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]  outline-none"
                                options={UserStatus?.map((item, index) => ({
                                  label: item.label,
                                  value: item.value,
                                }))}
                                onChange={(value) => {
                                  setTempFilter({ ...tempFilter, status: value });
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
                    className="group h-[1.7rem] text-[#FFFFFF] mr-[.7rem] ml-[.8rem] flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                    onClick={() => { }}
                  >
                    <MixerHorizontalIcon
                      style={{ width: '0.875rem', height: '0.875rem' }}
                      className="text-[#B3B3B3] group-hover:text-[#FFFFFF]"
                    />
                  </label>
                </Popover>
              </>
            }
          />
        </div>
        {hasPermission(PermissionEnum.UserManage) ?
          <div className="pt-4 px-[3.5rem]">
            {/* Tab Navigation */}
            <div className="flex mb-4 border-b border-[#1F1F1F]">

              <button
                onClick={() => setActiveTab('admin')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === 'admin'
                    ? 'text-[#EEEEEE] border-b-2 border-[#EEEEEE]'
                    : 'text-[#757575] hover:text-[#EEEEEE]'
                }`}
              >
                Admin Users
              </button>
              <button
                onClick={() => setActiveTab('client')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === 'client'
                    ? 'text-[#EEEEEE] border-b-2 border-[#EEEEEE]'
                    : 'text-[#757575] hover:text-[#EEEEEE]'
                }`}
              >
                Client Users
              </button>

            </div>

            {/* User Count Display */}
            <div className="mb-4 ">
              <Text_12_400_757575>
                Showing {totalUsers} {activeTab === 'admin' ? 'Admin' : 'Client'} Users
              </Text_12_400_757575>
            </div>

            {/* Users Table */}
            <div className=" userTable relative CommonCustomPagination">
              <Table<User>
                columns={columns}
                rowKey="id"
                pagination={{
                  className: 'small-pagination',
                  current: getCurrentPage(),
                  pageSize: pageSize,
                  total: totalUsers,
                  onChange: handlePageChange,
                  showSizeChanger: true,
                  pageSizeOptions: ['5', '10', '20', '50'],
                }}
                dataSource={users}
                bordered={false}
                footer={null}
                virtual
                onRow={(record, rowIndex) => {
                  return {
                    onClick: async event => {
                      event.stopPropagation();
                      if (hasPermission(PermissionEnum.UserManage) && record.status == "active") {
                        // For client users, open the usage drawer
                        if (activeTab === 'client') {
                          const user = await getUsersDetails(record.id);
                          if (user) {
                            openDrawer('user-usage');
                          }
                        } else {
                          // For admin users, open the permissions drawer
                          openUserPermissions(record);
                        }
                      }
                    }
                  }
                }}
                showSorterTooltip={false}
                locale={{
                  emptyText: (
                    <NoDataFount
                      classNames="h-[20vh]"
                      textMessage={`No ${activeTab === 'admin' ? 'Admin' : 'Client'} Users`}
                    />
                  ),
                }}
              />
            </div>
          </div>
          : <>
            <NoAccess textMessage="You do not have access to view user management, please ask admin to give you access to manage users." />
          </>
        }
      </div>
    </DashBoardLayout>
  );
}
