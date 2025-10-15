import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectInfoCard from "@/components/ui/bud/dataEntry/ProjectInfoCard";
import ProjectUsersInput from "@/components/ui/bud/dataEntry/ProjectUsersInput";
import React, { useContext, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { InviteUser, useProjects } from "src/hooks/useProjects";

export default function InviteMembers() {
  const [users, setUsers] = React.useState<InviteUser[]>([]);
  const { selectedProjectId, getProjects, inviteMembers } = useProjects();
  const { openDrawerWithStep } = useDrawer();
  const { submittable, values } = useContext(BudFormContext);

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

  return (
    <BudForm
      data={{
        users: [],
      }}
      onNext={(values) => {
        inviteMembers(selectedProjectId, { users })
          .then(() => {
            getProjects(1, 10);
          })
          .finally(() => {
            openDrawerWithStep("invite-success");
          });
      }}
      backText="Skip"
      nextText="Send Invite"
      onBack={() => {
        openDrawerWithStep("project-success");
      }}
      disableNext={!submittable}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <ProjectInfoCard />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Team Members"
            description="Add team members by entering their mail id"
            classNames="border-[0] border-b-[.5px]"
          />
          <DrawerCard>
            <ProjectUsersInput
              name="users"
              placeholder="Enter Email Id"
              rules={[
                {
                  required: true,
                  message: "Please add users",
                },
              ]}
              userType="admin"
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
