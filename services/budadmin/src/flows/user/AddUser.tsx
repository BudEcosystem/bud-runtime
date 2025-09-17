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
import React, { useCallback, useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
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
import { errorToast, successToast } from "@/components/toast";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "../components/TextInput";
import SelectInput from "../components/SelectInput";
import CustomPopover from "../components/customPopover";
import SearchHeaderInput from "../components/SearchHeaderInput";
import { useUsers } from "src/hooks/useUsers";
import { useLoader } from "src/context/appContext";
import PasswordGenerator from "src/utils/randomPasswordGenerator";
import { DownOutlined } from "@ant-design/icons";

const Permissions = [
  {
    name: "model:view",
    has_permission: true,
  },
  {
    name: "model:manage",
    has_permission: false,
  },
  {
    name: "project:view",
    has_permission: true,
  },
  {
    name: "project:manage",
    has_permission: false,
  },
  {
    name: "cluster:view",
    has_permission: true,
  },
  {
    name: "cluster:manage",
    has_permission: false,
  },
  {
    name: "benchmark:view",
    has_permission: true,
  },
  {
    name: "benchmark:manage",
    has_permission: false,
  },
  {
    name: "user:view",
    has_permission: false,
  },
  {
    name: "user:manage",
    has_permission: false,
  },
];

export default function AddUser() {
  const [generatedPassword, setGeneratedPassword] = useState("");
  const [selectedPermissions, setSelectedPermissions] =
    useState<any>(Permissions);
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { openDrawerWithStep } = useDrawer();
  const { closeDrawer } = useDrawer();
  const { userDetails, addUser, createdUser, setCreatedUser } = useUsers();
  const [userRole, setUserRole] = useState(userDetails?.role || "developer");
  const [userType, setUserType] = useState("client");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handlePasswordChange = (password: string) => {
    setGeneratedPassword(password);
  };

  // Initialize password on component mount
  useEffect(() => {
    if (!generatedPassword) {
      const defaultPassword = Math.random().toString(36).slice(-8) + "A1!";
      setGeneratedPassword(defaultPassword);
    }
  }, []);

  const primaryTableData = [
    {
      name: "Model",
      view: Permissions?.find((scope) => scope.name === "model:view")
        ?.has_permission,
      manage: Permissions?.find((scope) => scope.name === "model:manage")
        ?.has_permission,
      key: "model",
    },
    {
      name: "Cluster",
      view: Permissions?.find((scope) => scope.name === "cluster:view")
        ?.has_permission,
      manage: Permissions?.find((scope) => scope.name === "cluster:manage")
        ?.has_permission,
      key: "cluster",
    },
    {
      name: "User",
      view: Permissions?.find((scope) => scope.name === "user:view")
        ?.has_permission,
      manage: Permissions?.find((scope) => scope.name === "user:manage")
        ?.has_permission,
      key: "user",
    },
    {
      name: "Projects",
      view: Permissions?.find((scope) => scope.name === "project:view")
        ?.has_permission,
      manage: Permissions?.find((scope) => scope.name === "project:manage")
        ?.has_permission,
      key: "project",
    },
    {
      name: "Benchmarks",
      view: Permissions?.find((scope) => scope.name === "benchmark:view")
        ?.has_permission,
      manage: Permissions?.find((scope) => scope.name === "benchmark:manage")
        ?.has_permission,
      key: "benchmark",
    },
  ];

  const handleCheckboxChange = React.useCallback((permissionName: string) => {
    setSelectedPermissions((prevPermissions) =>
      prevPermissions.map((perm) =>
        perm.name === permissionName
          ? { ...perm, has_permission: !perm.has_permission }
          : perm,
      ),
    );
  }, []);

  const ExpandableTable = React.memo(function ExpandableTable({
    selectedPermissions,
    handleCheckboxChange,
    primaryTableData,
  }: {
    selectedPermissions: any;
    handleCheckboxChange: (permissionName: string) => void;
    primaryTableData: any[];
  }) {
    const [expandedRow, setExpandedRow] = useState<number | null>(null);
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
                <div
                  className={`min-h-[2.75rem]  min-w-[60%] flex justify-between items-center ${expandedRow === index && "w-[100%]"}`}
                  style={{
                    minWidth: "31%",
                  }}
                >
                  <div className="flex items-center">
                    <Text_12_600_EEEEEE>{item.name}</Text_12_600_EEEEEE>
                  </div>
                </div>
                <>
                  <div
                    className={`min-h-[2.75rem] pt-[0.788rem] min-w-[16.5%] `}
                  >
                    <Checkbox
                      checked={
                        selectedPermissions.find(
                          (p) => p.name === item.key + ":view",
                        )?.has_permission || false
                      }
                      disabled={item.name !== "User"}
                      className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                      onChange={() => handleCheckboxChange(item.key + ":view")}
                    />
                  </div>
                  <div className="min-h-[2.75rem] pt-[0.788rem]">
                    <Checkbox
                      checked={
                        selectedPermissions.find(
                          (p) => p.name === item.key + ":manage",
                        )?.has_permission || false
                      }
                      className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                      onChange={() =>
                        handleCheckboxChange(item.key + ":manage")
                      }
                    />
                  </div>
                </>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  });

  const handleSubmit = async (formValues: any) => {
    // Prevent multiple submissions
    if (isSubmitting) return;

    setIsSubmitting(true);

    // Generate a default password if none exists
    if (!generatedPassword) {
      const defaultPassword = Math.random().toString(36).slice(-8) + "A1!";
      setGeneratedPassword(defaultPassword);
    }

    // Use the form values for role and user_type if they exist, otherwise fall back to state
    const data = {
      ...formValues,
      role: formValues.role || userRole || "developer",
      password: generatedPassword || Math.random().toString(36).slice(-8) + "A1!",
      permissions: (formValues.user_type || userType) === "admin" ? selectedPermissions : [],
      user_type: formValues.user_type || userType || "client",
    };
    setCreatedUser(data);
    try {
      const response = await addUser(data); // Wait for API response
      if (response) {
        successToast("User added successfully");
        openDrawerWithStep("add-user-details");
      }
    } catch (error) {
      errorToast("Failed to add user");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <BudForm
      data={{
        role: userRole || "developer",
        user_type: userType || "client",
      }}
      onNext={(formData) => {
        handleSubmit(formData);
      }}
      nextText={isSubmitting ? "Saving..." : "Save"}
      disableNext={isSubmitting}
    >
      <BudWraperBox classNames="mt-[2.2rem]">
        <BudDrawerLayout>
          <div className="py-2 hidden">
            <div className="text-xs text-[#787B83] font-normal	">
              Auto generated password
            </div>
            <PasswordGenerator onPasswordChange={handlePasswordChange} />
          </div>
          <DrawerTitleCard
            title="Add User"
            description="Add user information below"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DrawerCard>
            <div key="name-input">
              <TextInput
                name="name"
                label="Name"
                placeholder="Enter Name"
                rules={[{ required: true, message: "Please enter name" }]}
                ClassNames="mt-[.55rem]"
                formItemClassnames="pb-[.6rem] mb-[1.4rem]"
                infoText="Enter the user name"
                InputClasses="py-[.5rem]"
              />
            </div>
            <div key="email-input">
              <TextInput
                name="email"
                label="Email"
                placeholder="Enter Email"
                rules={[
                  { required: true, message: "Please enter email" },
                  {
                    pattern: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
                    message: "Please enter a valid email address",
                  },
                ]}
                ClassNames="mt-[0rem]"
                formItemClassnames="pb-[.6rem] mb-[1.4rem]"
                infoText="Enter the user email"
                InputClasses="py-[.5rem]"
                type="email"
              />
            </div>
            <SelectInput
              name="role"
              label="Role"
              placeholder="Select Role"
              rules={[{ required: true, message: "Please select a role" }]}
              infoText="This is the Role"
              options={[
                { label: "Admin", value: "admin" },
                { label: "Developer", value: "developer" },
                { label: "Tester", value: "tester" },
                { label: "DevOps", value: "devops" },
              ]}
              onChange={(value) => setUserRole(value)}
            />
            <SelectInput
              name="user_type"
              label="User Type"
              placeholder="Select User Type"
              rules={[{ required: true, message: "Please select user type" }]}
              infoText="Select user type (Admin or Client)"
              formItemClassnames="mt-[1.4rem]"
              options={[
                { label: "Client", value: "client" },
                { label: "Admin", value: "admin" },
              ]}
              onChange={(value) => setUserType(value)}
            />
          </DrawerCard>
          {userType == "admin" && (
            <div className="px-[1.45rem] pt-[1.45rem]">
              <div className="flex flex-col justify-start items-start  py-[.6rem] gap-[.25rem]">
                <Text_14_400_EEEEEE>Permissions</Text_14_400_EEEEEE>
                <Text_12_400_757575>
                  Select user permissions for each module
                </Text_12_400_757575>
              </div>

              <div className="pb-[1.6rem]">
                <ExpandableTable
                  selectedPermissions={selectedPermissions}
                  handleCheckboxChange={handleCheckboxChange}
                  primaryTableData={primaryTableData}
                />
              </div>
            </div>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
