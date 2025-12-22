import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  CredentialDetailEndpoint,
  useProprietaryCredentials,
} from "src/stores/useProprietaryCredentials";
import {
  Badge,
  Checkbox,
  ConfigProvider,
  Dropdown,
  Image,
  Select,
  Space,
  Table,
} from "antd";
import { debounce } from "lodash";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { errorToast, successToast } from "@/components/toast";
import Tags from "../components/DrawerTags";
import NoDataFount from "@/components/ui/noDataFount";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "../components/TextInput";
import CustomPopover from "../components/customPopover";
import SearchHeaderInput from "../components/SearchHeaderInput";
import { useUsers } from "src/hooks/useUsers";
import { InviteUser, useProjects } from "src/hooks/useProjects";
import { useLoader } from "src/context/appContext";

function SortIcon({ sortOrder }: { sortOrder: string }) {
  return sortOrder ? (
    sortOrder === "descend" ? (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z"
          fill="#B3B3B3"
        />
      </svg>
    ) : (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z"
          fill="#B3B3B3"
        />
      </svg>
    )
  ) : null;
}

const defaultFilter = {
  name: "",
  email: "",
  role: "",
  status: "",
};

export default function EditUser() {
  const [searchValue, setSearchValue] = useState("");
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { openDrawerWithStep } = useDrawer();
  const [showConfirm, setShowConfirm] = useState(false);
  const { credentialDetails, deleteProprietaryCredential, refresh } =
    useProprietaryCredentials();
  const { closeDrawer } = useDrawer();
  const [checked, setChecked] = useState(false);
  const [disabled, setDisabled] = useState(false);
  const {
    users,
    getUsers,
    getUsersDetails,
    userDetails,
    getUsersPermissions,
    userPermissions,
    updateUser,
    setUsersPermissions,
  } = useUsers();
  const {
    globalProjects,
    getGlobalProjects,
    getProject,
    totalProjects,
    totalPages,
    inviteMembers,
  } = useProjects();
  const [projectList, setProjectList] = useState<any>([]);
  const [userRole, setUserRole] = useState(userDetails?.role || []);
  const [viewAll, setViewAll] = useState(false);
  const [manageAll, setManageAll] = useState(false);
  const [userPayload, setUserPayload] = useState<any>();
  const [localPermissions, setLocalPermissions] = useState<any>(null);
  // for pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const totalItems = 100;
  const [filter, setFilter] = useState<{
    name?: string;
    email?: string;
    role?: string;
    status?: string;
  }>(defaultFilter);

  const [expandedRow, setExpandedRow] = useState<boolean>(false);
  const showDetail = () => {
    setExpandedRow(!expandedRow); // Toggle the row
  };

  // Create stable debounced function
  const debouncedSearch = useMemo(
    () =>
      debounce((value: string) => {
        getGlobalProjects(1, 1000, value);
      }, 500),
    [getGlobalProjects],
  );

  // Stable handler that won't cause re-renders
  const handleSearch = useCallback(
    (value: string) => {
      setSearchValue(value);
      debouncedSearch(value);
    },
    [debouncedSearch],
  );

  // Clean up debounce on unmount
  useEffect(() => {
    return () => {
      debouncedSearch.cancel();
    };
  }, [debouncedSearch]);

  const load = useCallback(
    async (filter) => {
      showLoader();
      await getUsers({
        page: currentPage,
        limit: pageSize,
        name: filter.name,
        email: filter.email,
        role: filter.role,
        status: filter.status,
      });
      hideLoader();
    },
    [currentPage, pageSize, getUsers],
  );

  useEffect(() => {
    console.log("filter", filter);
    load(filter);
  }, [currentPage, pageSize, getUsers]);

  const toggleChecked = () => {
    setChecked(!checked);
  };

  const toggleDisable = () => {
    setDisabled(!disabled);
  };

  const manageUpdate = async () => {
    try {
      await updateUser(userDetails.id, userPayload);
      successToast("User updated successfully!"); // Show success toast
      load(filter);
      closeDrawer();
    } catch (error) {
      errorToast("Failed to update user. Please try again."); // Show error toast if update fails
    }
  };

  useEffect(() => {
    setUserPayload((prev) => ({ ...prev, role: userRole }));
  }, [userRole]);

  useEffect(() => {
    if (userPermissions) {
      setLocalPermissions(userPermissions);
    }
  }, [userPermissions]);

  const tagsData = [
    { name: "user@gmail.com", color: "#D1B854" },
    { name: "Developer", color: "#D1B854" },
    { name: "Active", color: "#3EC564" },
  ];

  const firstLineText = `Are you sure you want to delete this proprietary credential?`;
  const secondLineText = `You are about to delete ${credentialDetails?.["name"]}`;

  const primaryTableData = [
    {
      name: "Model",
      view:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "model:view",
        )?.has_permission || false,
      manage:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "model:manage",
        )?.has_permission || false,
    },
    {
      name: "Cluster",
      view:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "cluster:view",
        )?.has_permission || false,
      manage:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "cluster:manage",
        )?.has_permission || false,
    },
    {
      name: "User",
      view:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "user:view",
        )?.has_permission || false,
      manage:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "user:manage",
        )?.has_permission || false,
    },
    {
      name: "Benchmark",
      view:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "benchmark:view",
        )?.has_permission || false,
      manage:
        localPermissions?.global_scopes?.find(
          (scope) => scope.name === "benchmark:manage",
        )?.has_permission || false,
    },
  ];

  const prepareProjectsList = () => {
    let prjt = globalProjects?.map((item) => {
      const matchingPermissions = userPermissions?.project_scopes?.find(
        (p) => p.id === item.project.id,
      );

      return {
        ...item,
        permissions: matchingPermissions ? matchingPermissions.permissions : [],
      };
    });
    if (userPermissions) {
      setProjectList(prjt);
    }
  };

  useEffect(() => {
    prepareProjectsList();
  }, [userPermissions, globalProjects]);

  const handleCheckboxChange = (name: any, check: boolean, type?: string) => {
    console.log(primaryTableData);
    const currentPermission = localPermissions?.global_scopes || [];
    let updatedPermissions;
    if (type == "view") {
      updatedPermissions = currentPermission.map((scope) =>
        scope.name === name + ":view"
          ? { ...scope, has_permission: check }
          : scope.name === name + ":manage" && !check
            ? { ...scope, has_permission: false } // If unchecking view, also uncheck manage
            : scope,
      );
    } else {
      updatedPermissions = currentPermission.map((scope) =>
        scope.name === name + ":manage"
          ? { ...scope, has_permission: check }
          : scope.name === name + ":view" && check
            ? { ...scope, has_permission: true } // If checking manage, also check view
            : scope,
      );
    }

    // Update local state immediately
    setLocalPermissions({
      ...localPermissions,
      global_scopes: updatedPermissions,
    });

    // Then make API call
    setUsersPermissions(userDetails.id, updatedPermissions);
  };

  const SecondTable = ({ data }: { data?: any }) => {
    const [checkedState, setCheckedState] = useState<{
      [key: number]: { view: boolean; manage: boolean };
    }>({});
    const { updatePermissions } = useProjects();
    const [users, setUsers] = React.useState<InviteUser[]>([]);
    const { userDetails } = useUsers();

    useEffect(() => {
      const initialCheckedState = projectList.reduce(
        (acc, item, index) => {
          acc[index] = {
            view: item.permissions[0]?.has_permission || false,
            manage: item.permissions[1]?.has_permission || false,
          };
          return acc;
        },
        {} as { [key: number]: { view: boolean; manage: boolean } },
      );

      setCheckedState(initialCheckedState);
    }, []);

    const handleCheckboxChange = (index: number, type: "view" | "manage") => {
      setCheckedState((prev) => {
        console.log("prev", prev);
        console.log("handleCheckboxChange", index, type);
        const newState = { ...prev };

        if (type === "view") {
          newState[index] = {
            view: !prev[index]?.view,
            manage: prev[index]?.view ? prev[index]?.manage : false,
          };
        } else if (type === "manage") {
          newState[index] = {
            view: true,
            manage: !prev[index]?.manage,
          };
        }

        return newState;
      });
    };

    return (
      <div className="table mt-[0rem] w-full">
        <div className="tBody">
          {projectList.length > 0 ? (
            <>
              {projectList.map((item, index) => (
                <div className="" key={index}>
                  <div className="flex items-center px-[1.5rem]">
                    <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[60.5%] flex items-start">
                      <Text_12_600_EEEEEE>
                        {item.project.name}
                      </Text_12_600_EEEEEE>
                    </div>
                    <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[17.6%]">
                      <Checkbox
                        checked={checkedState[index]?.view || false || viewAll}
                        disabled={checkedState[index]?.view}
                        className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                        onChange={() => {
                          if (!checkedState[index]?.view) {
                            inviteMembers(
                              item.project?.id,
                              {
                                users: [
                                  {
                                    user_id: userDetails?.id,
                                    scopes: ["endpoint:view"],
                                  },
                                ],
                              },
                              false,
                            ).then(() => {
                              successToast("Permissions updated successfully");
                              getGlobalProjects(1, 1000);
                              getUsersPermissions(userDetails.id);
                            });
                          }
                        }}
                      />
                    </div>
                    <div className="min-h-[2.75rem] pt-[0.788rem]">
                      <Checkbox
                        checked={
                          checkedState[index]?.manage || false || manageAll
                        }
                        disabled={!checkedState[index]?.view}
                        className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                        onChange={() => {
                          updatePermissions(item?.project?.id, userDetails.id, [
                            {
                              name: "endpoint:manage",
                              has_permission: true,
                            },
                            {
                              name: "endpoint:view",
                              has_permission: true,
                            },
                          ]);
                          handleCheckboxChange(index, "manage");
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </>
          ) : (
            <NoDataFount classNames="h-[20vh]" textMessage={`No Projects`} />
          )}
        </div>
      </div>
    );
  };

  return (
    <BudForm
      data={{}}
      onNext={(values) => {
        if (userPayload) {
          manageUpdate();
        }
      }}
      nextText="Save"
      onBack={() => closeDrawer()}
      backText="Close"
    >
      <BudWraperBox classNames="mt-[2.2rem]">
        {showConfirm && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title={firstLineText}
              description={secondLineText}
              confirmText="Delete Credential"
              cancelText="Cancel"
              confirmAction={async () => {
                const result = await deleteProprietaryCredential(
                  credentialDetails.id,
                );
                if (result) {
                  successToast("Credential deleted successfully");
                  await refresh();
                  closeDrawer();
                }
                setShowConfirm(false);
              }}
              cancelAction={() => {
                setShowConfirm(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <BudDrawerLayout>
          <DrawerTitleCard
            title={userDetails.name}
            description="Edit user information below"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DrawerCard>
            <TextInput
              name="name"
              label="Name"
              onChange={(value) =>
                setUserPayload((prev) => ({ ...prev, name: value }))
              }
              placeholder="Enter Name"
              rules={[{ required: true, message: "Please enter name" }]}
              ClassNames="mt-[.55rem]"
              formItemClassnames="pb-[.6rem] mb-[1.4rem]"
              infoText="Enter the user name"
              InputClasses="py-[.5rem]"
            />
            <div
              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
            >
              <div className="w-full">
                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                  Role
                  <CustomPopover title="This is the Role">
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
                    components: {
                      Select: {
                        // multipleItemHeightSM: 16
                      },
                    },
                  }}
                >
                  <Select
                    placeholder="Select Role"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                      border: "0.5px solid #757575",
                      width: "100%",
                    }}
                    size="large"
                    className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] outline-none"
                    options={[
                      { label: "Admin", value: "admin" },
                      { label: "Developer", value: "developer" },
                      { label: "Tester", value: "tester" },
                      { label: "DevOps", value: "devops" },
                    ]}
                    value={userRole} // Controlled state
                    onChange={(value) => setUserRole(value)}
                    tagRender={(props) => {
                      const { label, value, closable, onClose } = props;
                      return (
                        <Tags
                          name={label}
                          color="#D1B854"
                          closable={closable}
                          classNames="text-center justify-center items-center my-[.4rem]"
                          onClose={() => {
                            setUserRole((prevRoles) =>
                              prevRoles.filter((role) => role !== value),
                            );
                          }}
                        />
                      );
                    }}
                  />
                  ;
                </ConfigProvider>
              </div>
            </div>
          </DrawerCard>
          <div className="px-[1.45rem] pt-[1.45rem]">
            <div className="flex flex-col justify-start items-start  py-[.6rem] gap-[.25rem]">
              <Text_14_400_EEEEEE>Permissions</Text_14_400_EEEEEE>
              <Text_12_400_757575>
                Select user permissions for each module
              </Text_12_400_757575>
            </div>
            <div className="pb-[1.6rem]">
              <div className="table mt-[.6rem] w-full border border-[#1F1F1F]">
                <div className="tHead flex items-center px-[.55rem] bg-[#121212]">
                  <div className="py-[0.688rem] min-w-[60%]">
                    <Text_12_600_EEEEEE>Access Level</Text_12_600_EEEEEE>
                  </div>
                  <div className="py-[0.688rem] min-w-[16.5%]">
                    <Text_12_400_EEEEEE>View</Text_12_400_EEEEEE>
                  </div>
                  <div className="py-[0.688rem]">
                    <Text_12_400_EEEEEE>Manage</Text_12_400_EEEEEE>
                  </div>
                </div>
                <div className="tBody">
                  {primaryTableData.map((item, index) => (
                    <div
                      className="border-t-[1px] border-t-[#1F1F1F]"
                      key={index}
                    >
                      <div className="flex items-center px-[.75rem]">
                        <div
                          className={`min-h-[2.75rem]  min-w-[60%] flex justify-between items-center '}`}
                          style={{
                            minWidth: "31%",
                          }}
                        >
                          <div className="flex items-center">
                            <Text_12_600_EEEEEE>{item.name}</Text_12_600_EEEEEE>
                          </div>
                        </div>

                        <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[16.5%]">
                          <Checkbox
                            checked={item.view}
                            className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                            disabled={
                              item.name !== "User" && item.name !== "Benchmark"
                            }
                            onChange={(e) => {
                              const isChecked = e.target.checked;
                              handleCheckboxChange(
                                item.name.toLocaleLowerCase(),
                                isChecked,
                                "view",
                              );
                            }}
                          />
                        </div>
                        <div className="min-h-[2.75rem] pt-[0.788rem]">
                          <Checkbox
                            checked={item.manage}
                            className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                            onChange={(e) => {
                              const isChecked = e.target.checked;
                              handleCheckboxChange(
                                item.name.toLocaleLowerCase(),
                                isChecked,
                              );
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                  {/* for projects permissions */}
                  <div className="border-t-[1px] border-t-[#1F1F1F]">
                    <div className="flex items-center px-[.75rem]">
                      <div
                        className={`min-h-[2.75rem]  min-w-[60%] flex justify-between items-center ${expandedRow && "w-[100%]"}`}
                        style={{
                          minWidth: "31%",
                        }}
                      >
                        <div className="flex items-center">
                          <Text_12_600_EEEEEE>Projects</Text_12_600_EEEEEE>
                          <div
                            className="ml-[.5rem] flex items-center"
                            onClick={(event) => {
                              event.stopPropagation();
                              showDetail();
                            }}
                          >
                            <Image
                              src="/images/drawer/ChevronUp.png"
                              preview={false}
                              alt="info"
                              style={{ width: "1rem", height: "1rem" }}
                              className={`origin-center transform transition-transform duration-300 ${
                                expandedRow ? "rotate-0" : "rotate-180"
                              }`}
                            />
                          </div>
                        </div>
                      </div>
                      {expandedRow && (
                        <div className="flex justify-end items-center min-w-[40%]">
                          {/* <div className="flex justify-between items-center min-w-[50%]">
                    <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[16.5%]">
                      <Checkbox
                        checked={viewAll}
                        className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                        onChange={() => setViewAll(!viewAll)}
                      />
                    </div>
                    <div className="min-h-[2.75rem] pt-[0.788rem]">
                      <Checkbox
                        checked={manageAll}
                        className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                        onChange={() => setManageAll(!manageAll)}
                      />
                    </div>
                  </div> */}
                          <SearchHeaderInput
                            placeholder="Search projects"
                            searchValue={searchValue}
                            setSearchValue={handleSearch}
                            expanded={true}
                          />
                        </div>
                      )}
                      {!expandedRow && (
                        <>
                          <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[16.5%]">
                            <Checkbox
                              checked={
                                localPermissions?.global_scopes?.find(
                                  (scope) => scope.name === "project:view",
                                )?.has_permission || false
                              }
                              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                              onChange={null}
                              disabled
                            />
                          </div>
                          <div className="min-h-[2.75rem] pt-[0.788rem]">
                            <Checkbox
                              checked={
                                localPermissions?.global_scopes?.find(
                                  (scope) => scope.name === "project:manage",
                                )?.has_permission || false
                              }
                              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                              onChange={(e) => {
                                const isChecked = e.target.checked;
                                handleCheckboxChange("project", isChecked);
                              }}
                            />
                          </div>
                        </>
                      )}
                    </div>
                    <div className={`${expandedRow ? "block" : "hidden"}`}>
                      <SecondTable />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
