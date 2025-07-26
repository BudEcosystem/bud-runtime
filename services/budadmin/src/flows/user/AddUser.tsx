
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_300_EEEEEE, Text_12_400_757575, Text_12_400_B3B3B3, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Badge, Checkbox, ConfigProvider, Dropdown, Image, Select, Space, Table } from "antd";
import { errorToast, successToast } from "@/components/toast";
import Tags from "../components/DrawerTags";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "../components/TextInput";
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
  const [formData, setFormData] = React.useState<{ [key: string]: string }>();
  const [selectedPermissions, setSelectedPermissions] = useState<any>(Permissions);
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { openDrawerWithStep } = useDrawer();
  const { closeDrawer } = useDrawer();
  const { userDetails, addUser, createdUser, setCreatedUser } = useUsers();
  const [userRole, setUserRole] = useState(userDetails?.role || []);

  const handlePasswordChange = (password: string) => {
    setGeneratedPassword(password);
  };


  useEffect(() => {
    setFormData((prev) => ({ ...prev, role: userRole }))
  }, [userRole]);

  const primaryTableData = [
    {
      name: 'Model',
      view: Permissions?.find(scope => scope.name === 'model:view')?.has_permission,
      manage: Permissions?.find(scope => scope.name === 'model:manage')?.has_permission,
      key: 'model'
    },
    {
      name: 'Cluster',
      view: Permissions?.find(scope => scope.name === 'cluster:view')?.has_permission,
      manage: Permissions?.find(scope => scope.name === 'cluster:manage')?.has_permission,
      key: 'cluster'
    },
    {
      name: 'User',
      view: Permissions?.find(scope => scope.name === 'user:view')?.has_permission,
      manage: Permissions?.find(scope => scope.name === 'user:manage')?.has_permission,
      key: 'user'
    },
    {
      name: 'Projects',
      view: Permissions?.find(scope => scope.name === 'project:view')?.has_permission,
      manage: Permissions?.find(scope => scope.name === 'project:manage')?.has_permission,
      key: 'project'
    },
    {
      name: 'Benchmarks',
      view: Permissions?.find(scope => scope.name === 'benchmark:view')?.has_permission,
      manage: Permissions?.find(scope => scope.name === 'benchmark:manage')?.has_permission,
      key: 'benchmark'
    }
  ]


  const ExpandableTable = ({ data }: { data?: any }) => {
    const [expandedRow, setExpandedRow] = useState<number | null>(null);

    const handleCheckboxChange = (permissionName: string) => {
      console.log('permissionName', permissionName)
      setSelectedPermissions((prevPermissions) =>
        prevPermissions.map((perm) =>
          perm.name === permissionName
            ? { ...perm, has_permission: !perm.has_permission }
            : perm
        )
      );
    };

    useEffect(()=>{
      console.log('selectedPermissions', selectedPermissions)
    },[selectedPermissions])
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
                <div className={`min-h-[2.75rem]  min-w-[60%] flex justify-between items-center ${expandedRow === index && 'w-[100%]'}`}
                  style={{
                    minWidth: "31%"
                  }}
                >
                  <div className="flex items-center">
                    <Text_12_600_EEEEEE>{item.name}</Text_12_600_EEEEEE>
                  </div>
                </div>
                <>
                  <div className={`min-h-[2.75rem] pt-[0.788rem] min-w-[16.5%] `}>
                    <Checkbox
                      checked={selectedPermissions.find((p) => p.name === item.key + ':view')?.has_permission || false}
                      disabled={item.name !== 'User'}
                      className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                      onChange={() => handleCheckboxChange(item.key + ':view')}
                    />
                  </div>
                  <div className="min-h-[2.75rem] pt-[0.788rem]">
                    <Checkbox
                      checked={selectedPermissions.find((p) => p.name === item.key + ':manage')?.has_permission || false}
                      className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                      onChange={() => handleCheckboxChange(item.key + ':manage')}
                    />
                  </div>
                </>

              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }


  const handleSubmit = async() => {
    if (!formData.name || !formData.email || !formData.role) {
      errorToast('Please fill in all required fields');
      return;
    }
    const data = {
      ...formData,
      password: generatedPassword,
      permissions: selectedPermissions,
    };
    setCreatedUser(data)
    try {
      const response = await addUser(data); // Wait for API response
      if (response) {
        successToast('User added successfully');
        openDrawerWithStep('add-user-details');
      }
    } catch (error) {
      errorToast('Failed to add user');
    }
  };

  return (
    <BudForm
      data={{
      }}
      onNext={(formData) => {
        handleSubmit()

      }}
      nextText="Save"

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
            <TextInput
              name="name"
              label="Name"
              value={formData?.name || ''}
              onChange={(value) => setFormData((prev) => ({ ...prev, name: value }))}
              placeholder="Enter Name"
              rules={[{ required: true, message: "Please enter name" }]}
              ClassNames="mt-[.55rem]"
              formItemClassnames="pb-[.6rem] mb-[1.4rem]"
              infoText="Enter the user name"
              InputClasses="py-[.5rem]"
            />
            <TextInput
              name="email"
              label="Email"
              value={formData?.email || ''}
              onChange={(value) => setFormData((prev) => ({ ...prev, email: value }))}
              placeholder="Enter Email"
              rules={[
                { required: true, message: "Please enter email" },
                {
                  pattern: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
                  message: "Please enter a valid email address"
                }
              ]}
              ClassNames="mt-[0rem]"
              formItemClassnames="pb-[.6rem] mb-[1.4rem]"
              infoText="Enter the user email"
              InputClasses="py-[.5rem]"
              type="email"
            />
            <div
              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
            >
              <div className="w-full">
                <Text_12_300_EEEEEE className="absolute h-[3px] bg-[#0d0d0d] top-[0rem] left-[.75rem] px-[0.025rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap bg-[#0d0d0d] pl-[.35rem] pr-[.55rem]">
                  Role
                  <b className="text-[#FF4D4F]">*</b>
                  <CustomPopover title="This is the Role" >
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
                    suffixIcon={
                      <Image
                      src="/images/icons/dropD.png"
                      preview={false}
                      alt="info"
                      style={{ width: 'auto', height: 'auto' }}
                    />
                    }
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
                            setUserRole((prevRoles) => prevRoles.filter((role) => role !== value));
                          }}
                        />
                      );
                    }}
                  />
                </ConfigProvider>
              </div>
            </div>
          </DrawerCard>
          <div className="px-[1.45rem] pt-[1.45rem]">
            <div className='flex flex-col justify-start items-start  py-[.6rem] gap-[.25rem]'>
              <Text_14_400_EEEEEE>Permissions</Text_14_400_EEEEEE>
              <Text_12_400_757575>Select user permissions for each module</Text_12_400_757575>
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
