
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_300_EEEEEE, Text_12_400_757575, Text_12_400_B3B3B3, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import React, { useCallback, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";

import BudStepAlert from "src/flows/components/BudStepAlert";
import { errorToast, successToast } from "@/components/toast";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "../components/TextInput";
import { useUsers } from "src/hooks/useUsers";
import { InviteUser, useProjects } from "src/hooks/useProjects";
import { useLoader } from "src/context/appContext";

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

interface DataType {
  key?: React.Key;
  accessLevel: string;
  view: string;
  manage: string;
}

interface ExpandedDataType {
  key: React.Key;
  date: string;
  name: string;
  upgradeNum: string;
}

const defaultFilter = {
  name: "",
  email: "",
  role: "",
  status: "",
}

export default function ResetPassword() {
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { userDetails, updateUser } = useUsers();

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  const manageUpdate = async () => {
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    try {
      await updateUser(userDetails.id, { password: newPassword, name: userDetails.name });
      successToast("Password updated successfully!");
      closeDrawer();
    } catch (error) {
      errorToast("Failed to update password. Please try again.");
    }
  };

  return (
    <BudForm
      data={{
      }}
      onNext={() => manageUpdate()}
      nextText="Reset"
      onBack={() => closeDrawer()}
      backText="Close"
    >
      <BudWraperBox classNames="mt-[2.2rem]">
        <BudDrawerLayout>
          <DrawerTitleCard
            title={userDetails.name}
            description="Reset your password"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DrawerCard>
            <TextInput
              name="newpassword"
              label="New Password"
              value={newPassword}
              onChange={setNewPassword}
              placeholder="Enter new password"
              rules={[{ required: true, message: "Please enter a new password" }]}
              ClassNames="mt-[.55rem]"
              formItemClassnames="pb-[.6rem] mb-[1.4rem]"
              infoText="Enter the new password"
              InputClasses="py-[.5rem]"
              type="password"
            />

            <TextInput
              name="confirmPassword"
              label="Confirm Password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              placeholder="Confirm new password"
              rules={[{ required: true, message: "Please confirm your password" }]}
              ClassNames="mt-[.55rem]"
              formItemClassnames="pb-[.6rem] mb-[1.4rem]"
              infoText="Re-enter the new password"
              InputClasses="py-[.5rem]"
              type="password"
            />

            {error && <Text_12_400_B3B3B3 className="text-red-500">{error}</Text_12_400_B3B3B3>}
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
