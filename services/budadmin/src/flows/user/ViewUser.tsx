import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useProprietaryCredentials } from "src/stores/useProprietaryCredentials";
import { Checkbox, Image } from "antd";

import BudStepAlert from "src/flows/components/BudStepAlert";
import { successToast } from "@/components/toast";
import Tags from "../components/DrawerTags";
import CustomDropDown from "../components/CustomDropDown";
import { useUsers } from "src/hooks/useUsers";
import { useProjects } from "src/hooks/useProjects";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { capitalize } from "@/lib/utils";
import { useLoader } from "src/context/appContext";

const defaultFilter = {
  name: "",
  email: "",
  role: "",
  status: "",
};

export default function ViewUser() {
  const { isLoading } = useLoader();
  const { openDrawerWithStep } = useDrawer();
  const [showConfirm, setShowConfirm] = useState(false);
  const { refresh } = useProprietaryCredentials();
  const { closeDrawer } = useDrawer();
  const [disabled, setDisabled] = useState(false);
  const { userDetails, userPermissions, deleteUser } = useUsers();
  const { globalProjects, getGlobalProjects } = useProjects();
  const [projectList, setProjectList] = useState<any>([]);

  // for pagination
  const [currentUserDetails, setCurrentUserDetails] = useState<{
    id?: string;
    name?: string;
    email?: string;
    role?: string;
    status?: string;
  }>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const totalItems = 100;
  const [filter, setFilter] = useState<{
    name?: string;
    email?: string;
    role?: string;
    status?: string;
  }>(defaultFilter);

  useEffect(() => {
    setCurrentUserDetails(userDetails);
  }, [userDetails]);

  useEffect(() => {
    getGlobalProjects(1, 1000);
  }, []);

  useEffect(() => {
    let prjt = globalProjects?.map((item) => {
      // const matchingPermissions = userPermissions.project_scopes.length && userPermissions.project_scopes?.find(p => {
      //   console.log(p)
      //   p.id === item.project.id;
      // });
      const matchingPermissions = userPermissions?.project_scopes?.find(
        (p) => p.id === item.project.id,
      );

      return {
        ...item,
        permissions: matchingPermissions ? matchingPermissions.permissions : [],
      };
    });
    setProjectList(prjt);
  }, [userPermissions]);

  const tagsData = [
    { name: "user@gmail.com", color: "#D1B854" },
    { name: "Developer", color: "#D1B854" },
    { name: "Active", color: "#3EC564" },
  ];

  const firstLineText = `Are you sure you want to delete this user?`;
  const secondLineText = `You are about to delete ${currentUserDetails?.["name"]}`;

  const primaryTableData = [
    {
      name: "Model",
      view: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "model:view",
      )?.has_permission,
      manage: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "model:manage",
      )?.has_permission,
    },
    {
      name: "Cluster",
      view: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "cluster:view",
      )?.has_permission,
      manage: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "cluster:manage",
      )?.has_permission,
    },
    {
      name: "User",
      view: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "user:view",
      )?.has_permission,
      manage: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "user:manage",
      )?.has_permission,
    },
    {
      name: "Benchmarks",
      view: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "benchmark:view",
      )?.has_permission,
      manage: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "benchmark:manage",
      )?.has_permission,
    },
    {
      name: "Projects",
      view: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "project:view",
      )?.has_permission,
      manage: userPermissions?.global_scopes?.find(
        (scope) => scope.name === "project:manage",
      )?.has_permission,
    },
  ];

  const expandData = [
    { name: "Project 1" },
    { name: "Project 2" },
    { name: "Project 3" },
  ];

  const ExpandableTable = ({ data }: { data?: any }) => {
    const [expandedRow, setExpandedRow] = useState<boolean>(false);
    const [checkedState, setCheckedState] = useState<{
      [key: number]: boolean;
    }>({});

    const showDetail = (index: number) => {
      setExpandedRow(!expandedRow); // Toggle the row
    };

    const handleCheckboxChange = (index: any) => {
      setCheckedState((prev) => ({
        ...prev,
        [index]: !prev[index], // Toggle the checkbox state for the row
      }));
    };

    return (
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
            <div className="border-t-[1px] border-t-[#1F1F1F]" key={index}>
              <div className="flex items-center px-[.75rem]">
                <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[60%] flex items-start">
                  <Text_12_600_EEEEEE>{item.name}</Text_12_600_EEEEEE>
                  {item.name == "Projects" && (
                    <div
                      className="ml-[.5rem]"
                      onClick={(event) => {
                        event.stopPropagation();
                        showDetail(index);
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
                  )}
                </div>
                <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[16.5%]">
                  <Checkbox
                    checked={item.view}
                    // checked={item.view || item.name == 'User'}
                    className="AntCheckbox greayCheck text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                    disabled={disabled}
                    onChange={() => handleCheckboxChange(index)}
                  />
                </div>
                <div className="min-h-[2.75rem] pt-[0.788rem]">
                  <Checkbox
                    checked={item.manage}
                    className="AntCheckbox greayCheck text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                    disabled={disabled}
                    onChange={() => handleCheckboxChange(index + "x")}
                  />
                </div>
              </div>
              {item.name == "Projects" && (
                <div className={`${expandedRow ? "block" : "hidden"}`}>
                  <SecondTable />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const SecondTable = ({ data }: { data?: any }) => {
    const [checkedState, setCheckedState] = useState<{
      [key: number]: boolean;
    }>({});
    const handleCheckboxChange = (index: any) => {
      setCheckedState((prev) => ({
        ...prev,
        [index]: !prev[index], // Toggle the checkbox state for the row
      }));
    };
    return (
      <div className="table mt-[0rem] w-full">
        <div className="tBody">
          {projectList.map((item, index) => (
            <div className="" key={index}>
              <div className="flex items-center px-[1.5rem]">
                {/* <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[29.7%] flex items-start"> */}
                <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[60.5%] flex items-start">
                  <Text_12_600_EEEEEE>{item.project.name}</Text_12_600_EEEEEE>
                </div>
                <div className="min-h-[2.75rem] pt-[0.788rem] min-w-[17.6%]">
                  <Checkbox
                    checked={item.permissions[0]?.has_permission || false}
                    className="AntCheckbox greayCheck text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                    disabled={disabled}
                    onChange={() => handleCheckboxChange(index)}
                  />
                </div>
                <div className="min-h-[2.75rem] pt-[0.788rem]">
                  <Checkbox
                    checked={item.permissions[1]?.has_permission || false}
                    className="AntCheckbox greayCheck text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                    disabled={disabled}
                    onChange={() => handleCheckboxChange(index + "x")}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <BudForm data={{}} drawerLoading={isLoading}>
      <BudWraperBox classNames="mt-[2.2rem]">
        {showConfirm && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title={firstLineText}
              description={secondLineText}
              confirmText="Delete User"
              cancelText="Cancel"
              confirmAction={async () => {
                const result = await deleteUser(currentUserDetails?.id);
                if (result) {
                  successToast("User deleted successfully");
                  await refresh();
                  closeDrawer();
                }
                setShowConfirm(false);
                closeDrawer();
              }}
              cancelAction={() => {
                setShowConfirm(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <BudDrawerLayout>
          <div className="flex flex-col items-start justify-start w-full px-[1.4rem] py-[1.05rem] pb-[1.4rem] border-b-[.5px] border-b-[#1F1F1F]">
            <div className="w-full flex justify-between items-start ">
              <Text_14_400_EEEEEE className="mb-[0.35rem]">
                {currentUserDetails?.name}
              </Text_14_400_EEEEEE>
              <div className="mr-[.1rem] mt-[.2rem]">
                <CustomDropDown
                  parentClassNames="oneDrop"
                  buttonContent={
                    <div className="px-[.3rem] my-[0] py-[0.02rem]">
                      <Image
                        preview={false}
                        src="/images/drawer/threeDots.png"
                        alt="info"
                        style={{ width: "0.1125rem", height: ".6rem" }}
                      />
                    </div>
                  }
                  items={[
                    {
                      key: "1",
                      label: <Text_12_400_EEEEEE>Edit</Text_12_400_EEEEEE>,
                      onClick: () => openDrawerWithStep("edit-user"),
                    },
                    {
                      key: "1",
                      label: <Text_12_400_EEEEEE>Delete</Text_12_400_EEEEEE>,
                      onClick: () => {
                        setShowConfirm(true);
                      },
                    },
                    {
                      key: "3",
                      label: (
                        <Text_12_400_EEEEEE className="text-nowrap">
                          Reset Password
                        </Text_12_400_EEEEEE>
                      ),
                      onClick: () => {
                        openDrawerWithStep("reset-password");
                      },
                    },
                  ]}
                />
              </div>
            </div>
            <div className="flex items-center justify-start flex-wrap	gap-[.4rem]">
              {/* {tagsData.map((item, index) => (
                <Tags key={index} name={item.name} color={item.color} classNames="py-[.3rem]" />
              ))} */}
              <Tags
                name={currentUserDetails?.email}
                color="#D1B854"
                classNames="py-[.3rem]"
              />
              <Tags
                name={capitalize(currentUserDetails?.role)}
                color="#D1B854"
                classNames="py-[.3rem]"
              />
              <Tags
                name={capitalize(currentUserDetails?.status)}
                color={
                  endpointStatusMapping[capitalize(currentUserDetails?.status)]
                }
                classNames="py-[.3rem]"
              />
            </div>
          </div>
          <div className="px-[1.45rem]">
            <div className="flex flex-col justify-start items-start  py-[.6rem] gap-[.25rem]">
              <Text_14_400_EEEEEE>Permissions</Text_14_400_EEEEEE>
              <Text_12_400_757575>
                Selected user permissions for each module
              </Text_12_400_757575>
            </div>
            <div className="pb-[1.6rem]">
              <ExpandableTable />
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
