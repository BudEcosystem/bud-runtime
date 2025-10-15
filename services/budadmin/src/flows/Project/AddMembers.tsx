import { successToast } from "@/components/toast";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectInfoCard from "@/components/ui/bud/dataEntry/ProjectInfoCard";
import ProjectUsersInput from "@/components/ui/bud/dataEntry/ProjectUsersInput";
import { Text_12_400_EEEEEE } from "@/components/ui/text";
import { DownOutlined } from "@ant-design/icons";
import { Select, Image, Dropdown, Space, MenuProps } from "antd";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { InviteUser, ProjectMember, useProjects } from "src/hooks/useProjects";
import CustomDropDown from "../components/CustomDropDown";

function UserItem({
  name,
  color,
  permissions,
  id,
  project_role,
}: ProjectMember) {
  const {
    removeMembers,
    selectedProject,
    getMembers,
    updatePermissions,
    projectMembers,
  } = useProjects();

  const managePermission = permissions?.find(
    (permission) => permission.name === "endpoint:manage",
  ).has_permission;
  const viewPermission = permissions?.find(
    (permission) => permission.name === "endpoint:view",
  ).has_permission;
  const isOwner = project_role === "owner";
  const isParticipant = project_role === "participant";

  const items: MenuProps["items"] = [
    {
      label: "Manage",
      key: "project:manage",
      onClick: async () => {
        const result = await updatePermissions(selectedProject?.id, id, [
          {
            name: "endpoint:manage",
            has_permission: true,
          },
          {
            name: "endpoint:view",
            has_permission: true,
          },
        ]);
        if (result) {
          await getMembers(selectedProject?.id);
        }
      },
    },
    {
      label: "View",
      key: "project:view",
      onClick: async () => {
        const result = await updatePermissions(selectedProject?.id, id, [
          {
            name: "endpoint:manage",
            has_permission: false,
          },
          {
            name: "endpoint:view",
            has_permission: true,
          },
        ]);
        if (result) {
          await getMembers(selectedProject?.id);
        }
      },
    },
    {
      type: "divider",
    },
    {
      label: "Remove",
      key: "3",
      onClick: async () => {
        const result = await removeMembers(selectedProject?.id, [id]);
        if (result) {
          await getMembers(selectedProject?.id);
        }
      },
    },
  ];

  const DropdownButtonContent = ({
    isOwner,
    managePermission,
    viewPermission,
  }) => {
    if (isOwner) {
      return <Text_12_400_EEEEEE>Owner</Text_12_400_EEEEEE>;
    }
    if (managePermission) {
      return <Text_12_400_EEEEEE>Manage</Text_12_400_EEEEEE>;
    }
    if (viewPermission) {
      return <Text_12_400_EEEEEE>View</Text_12_400_EEEEEE>;
    }
    return <Text_12_400_EEEEEE>No Permission</Text_12_400_EEEEEE>;
  };

  useEffect(() => {
    console.log("projectMembers", projectMembers);
  }, [projectMembers]);

  return (
    <div className="flex justify-between items-center">
      <div className="flex justify-start items-center">
        <div className="w-[0.875rem] h-[0.875rem] mr-[.4rem] flex justify-center items-center rounded-[100%] verflow-hidden bg-[#EC9462]">
          <Image
            preview={false}
            src="/images/drawer/memoji.png"
            alt="memoji"
            className="w-full h-full rounded-full"
            style={{
              padding: "1px",
              width: ".75rem",
              height: ".75rem",
            }}
          />
        </div>
        <Text_12_400_EEEEEE>{name}</Text_12_400_EEEEEE>
      </div>
      <div>
        <CustomDropDown
          isDisabled={isOwner}
          items={isOwner ? [] : items}
          menuItemColor="#EEEEEE"
          text={name}
          Placement="topRight"
          buttonContent={
            <Space>
              <DropdownButtonContent
                isOwner={isOwner}
                managePermission={managePermission}
                viewPermission={viewPermission}
              />
              {/* <DownOutlined className="w-[0.6em]"/> */}
              <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
                <Image
                  preview={false}
                  src="/images/drawer/down.png"
                  alt="info"
                  style={{ width: "0.5rem" }}
                />
              </div>
            </Space>
          }
        />
      </div>
    </div>
  );
}

export default function AddMembers() {
  const {
    selectedProject,
    getProjects,
    inviteMembers,
    getProject,
    projectMembers,
    getMembers,
  } = useProjects();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { submittable, form, values } = useContext(BudFormContext);
  const [users, setUsers] = React.useState<InviteUser[]>([]);
  const [selectedRole, setSelectedRole] = useState<any>();

  useEffect(() => {
    if (values?.users) {
      setUsers(
        values?.users
          ?.map((item) => ({
            user_id: item?.id,
            email: item?.id ? undefined : item?.email || item.label,
            scopes: item.scopes,
          }))
          ?.filter(Boolean) || [],
      );
    }
  }, [values]);

  useEffect(() => {
    if (users.length > 0 && selectedRole?.length > 0) {
      const updatedUsers = [...users];
      updatedUsers[0].scopes = [selectedRole];
      setUsers(updatedUsers);
    }
  }, [selectedRole]);

  useEffect(() => {
    getMembers(selectedProject?.id);
    console.log("projectMembers", projectMembers);
  }, []);

  return (
    <BudForm
      data={{
        users: [],
      }}
      onNext={(values) => {
        inviteMembers(selectedProject?.id, { users }).then(() => {
          getProjects(1, 10);
          getProject(selectedProject?.id);
          // closeDrawer();
          form.setFieldsValue({ users: [] });
        });
      }}
      // backText="Skip"
      nextText="Send Invite"
      // onBack={() => {
      //   openDrawerWithStep('project-success');
      // }}
      disableNext={!submittable}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <ProjectInfoCard />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Team Members"
            description="Invite team members to collaborate on this project"
            classNames="border-[0] border-b-[.5px]"
          />
          <DrawerCard classNames="pb-[0]">
            <ProjectUsersInput
              name="users"
              placeholder="Enter team member’s email or search by name"
              classNames="mb-[0]"
              rules={[
                {
                  required: true,
                  message: "Please add users",
                },
              ]}
              onChangeScope={(selectedScope) => {
                setSelectedRole(selectedScope);
              }}
            />
          </DrawerCard>
          <DrawerTitleCard
            title="Project Permission"
            description="Set access for individual projects"
            classNames="border-b-[0] border-b-[.5px] !pt-[.8rem]"
          />
          <div className="px-[1.4rem] pt-[.25rem] pb-[1.5rem]">
            <div className="rounded-[8px] px-[.9rem] py-[.95rem] bg-[#FFFFFF08] flex flex-col gap-[.95rem]">
              {projectMembers.map((member, index) => (
                <UserItem key={index} {...member} />
              ))}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
