import { Avatar, Image } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useLoader } from "src/context/appContext";
import { Text_12_400_EEEEEE, Text_14_400_EEEEEE, Text_16_600_FFFFFF, Text_18_600_EEEEEE } from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useUser } from "src/stores/useUser";
import CustomInput from "src/flows/components/CustomInput";
import { removeUnderScoreAndCapatalise } from "@/lib/utils";
import InlineSwitch from "@/components/ui/InlineSwitch";


const Notifications = () => {
  const { user } = useUser();
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { openDrawer } = useDrawer();
  const [inAppNotification, setInAppNotification] = useState(false);
  const [emailNotification, setEmailNotification] = useState(false);


  return (
    <div className='pb-[60px] pt-[.5rem] relative CommonCustomPagination'>
      <div className="flex flex items-center justify-between w-full">
        <Text_16_600_FFFFFF className="">Notification Details</Text_16_600_FFFFFF>
        {/* <PrimaryButton
          className="bg-[#1E1E2F] text-[#FFFFFF] border border-[#1E1E2F] rounded-[0.5rem] px-[1.5rem] py-[0.5rem] hover:bg-[#1E1E2F] hover:text-[#FFFFFF]"
          text="Edit Profile"
          onClick={() => {
            openDrawer("edit-profile")
          }}
        /> */}
      </div>
      <div className="ml-[.05rem]">
        <div className="flex flex-col items-start justify-start gap-[1.2rem] w-full mt-[1.5rem]">
          <div className="flex justify-start items-center gap-[1rem]">
            <InlineSwitch
              value={inAppNotification}
              defaultValue={false}
              onChange={(value) => {
                setInAppNotification(value);
              }
              }
            />
            <div className="flex flex-col gap-[.3rem]">
              <Text_14_400_EEEEEE className="">
                In App Notifications
              </Text_14_400_EEEEEE>
              <Text_12_400_EEEEEE>
                Description for In App Notifications Description for In App Notification
              </Text_12_400_EEEEEE>
            </div>
          </div>
          <div className="flex justify-start items-center gap-[1rem]">
            <InlineSwitch
              value={emailNotification}
              defaultValue={false}
              onChange={(value) => {
                setEmailNotification(value);
              }
              }
            />
            <div className="flex flex-col gap-[.3rem]">
              <Text_14_400_EEEEEE className="">
              Email Notifications
              </Text_14_400_EEEEEE>
              <Text_12_400_EEEEEE>
              Description for Email Notifications Description for Email..
              </Text_12_400_EEEEEE>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Notifications;
