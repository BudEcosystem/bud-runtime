import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_44474D,
  Text_10_400_757575,
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_400_787B83,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_13_300_FFFFFF,
  Text_14_300_EEEEEE,
  Text_14_400_EEEEEE,
  Text_15_600_EEEEEE,
} from "@/components/ui/text";
import React, { useCallback, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Badge, Checkbox, Dropdown, Image, Space, Table } from "antd";

import { successToast } from "@/components/toast";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import CustomPopover from "../components/customPopover";
import { useUsers } from "src/hooks/useUsers";

export default function AddUserDetails() {
  const { closeDrawer } = useDrawer();

  const [copyText, setCopiedText] = useState<string>("Copy");
  const { createdUser } = useUsers();

  useEffect(() => {
    console.log("createdUser", createdUser);
  }, [createdUser]);

  const findAccess = (type: any) => {
    const hasManage = createdUser?.permissions?.find(
      (p: any) => p.name === type + ":manage",
    )?.has_permission;
    const hasView = createdUser?.permissions?.find(
      (p: any) => p.name === type + ":view",
    )?.has_permission;

    if (hasManage) return "Manage";
    if (hasView) return "View";
    return "Nill";
  };

  const textToCopy = `Admin has invited you to Bud Inference Engine

  Username: ${createdUser?.email}
  Role: ${createdUser?.role}

  New Password: ${createdUser?.password}

  Access Levels:-
  Model: ${findAccess("model")}
  Cluster: ${findAccess("cluster")}
  User: ${findAccess("user")}
  Project Creation: ${findAccess("project")}

  Click this link to login: https://bud.studio`;

  useEffect(() => {
    setTimeout(() => {
      setCopiedText("Copy");
    }, 3000);
  }, [copyText]);

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

  return (
    <BudForm
      data={{}}
      onNext={() => {
        closeDrawer();
      }}
      nextText="Close"
    >
      <BudWraperBox classNames="mt-[2.2rem]">
        <BudDrawerLayout>
          <DrawerTitleCard
            title="New User Invite"
            description="Copy the message below and send it to the user."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DrawerCard>
            <div className="rounded-[8px] relative bg-[#FFFFFF08] mt-[1.5rem] w-full px-[.9rem] py-[1rem]">
              <div className="flex justify-between items-center mb-[1rem]">
                <Text_12_400_757575>
                  Admin has invited you to Bud Inference Engine
                </Text_12_400_757575>
                <div>
                  <CustomPopover title={copyText} contentClassNames="">
                    <div
                      className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center cursor-pointer hover:bg-[#1F1F1F]"
                      onClick={() => handleCopy(textToCopy)}
                    >
                      <Image
                        preview={false}
                        src="/images/drawer/Copy.png"
                        alt="info"
                        style={{ height: ".75rem" }}
                      />
                    </div>
                  </CustomPopover>
                </div>
              </div>
              <div>
                <div className="mt-3 flex gap-[.6rem]">
                  <Text_12_400_787B83>Username:</Text_12_400_787B83>
                  <Text_13_300_FFFFFF>{createdUser?.email}</Text_13_300_FFFFFF>
                </div>
                <div className="mt-3 flex gap-[.6rem]">
                  <Text_12_400_787B83>New Password:</Text_12_400_787B83>
                  <Text_13_300_FFFFFF>
                    {createdUser?.password}
                  </Text_13_300_FFFFFF>
                </div>
                <div className="mt-3">
                  <Text_12_400_B3B3B3 className="pb-2">
                    Access Levels:-
                  </Text_12_400_B3B3B3>
                  <div className="mt-3 flex gap-[.6rem]">
                    <Text_12_400_787B83>Model:</Text_12_400_787B83>
                    <Text_13_300_FFFFFF>
                      {findAccess("model")}
                    </Text_13_300_FFFFFF>
                  </div>
                  <div className="mt-3 flex gap-[.6rem]">
                    <Text_12_400_787B83>Cluster:</Text_12_400_787B83>
                    <Text_13_300_FFFFFF>
                      {findAccess("cluster")}
                    </Text_13_300_FFFFFF>
                  </div>
                  <div className="mt-3 flex gap-[.6rem]">
                    <Text_12_400_787B83>User:</Text_12_400_787B83>
                    <Text_13_300_FFFFFF>
                      {findAccess("user")}
                    </Text_13_300_FFFFFF>
                  </div>
                  <div className="mt-3 flex gap-[.6rem]">
                    <Text_12_400_787B83>Benchmark:</Text_12_400_787B83>
                    <Text_13_300_FFFFFF>
                      {findAccess("benchmark")}
                    </Text_13_300_FFFFFF>
                  </div>
                  <div className="mt-3 flex gap-[.6rem]">
                    <Text_12_400_787B83>Project:</Text_12_400_787B83>
                    <Text_13_300_FFFFFF>
                      {findAccess("project")}
                    </Text_13_300_FFFFFF>
                  </div>
                </div>
                {/* <div className="mt-3 flex gap-[.6rem]">
                  <Text_12_400_B3B3B3>
                    Click this link login:{" "}
                  </Text_12_400_B3B3B3>
                  <Text_13_300_FFFFFF>
                    <a>https://bud.studio</a>
                  </Text_13_300_FFFFFF>
                </div> */}
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
