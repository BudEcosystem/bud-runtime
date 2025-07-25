import { Avatar, Image } from "antd";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useLoader } from "src/context/appContext";
import { Text_16_600_FFFFFF, Text_18_600_EEEEEE } from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useUser } from "src/stores/useUser";
import CustomInput from "src/flows/components/CustomInput";
import { removeUnderScoreAndCapatalise } from "@/lib/utils";


const Profile = () => {
  const { user } = useUser();
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { openDrawer } = useDrawer();


  return (
    <div className='pb-[60px] pt-[.5rem] relative CommonCustomPagination'>
      <div className="flex flex items-center justify-between w-full">
        <Text_16_600_FFFFFF className="">Your Profile Information</Text_16_600_FFFFFF>
        <PrimaryButton
          className="bg-[#1E1E2F] text-[#FFFFFF] border border-[#1E1E2F] rounded-[0.5rem] px-[1.5rem] py-[0.5rem] hover:bg-[#1E1E2F] hover:text-[#FFFFFF]"
          text="Edit Profile"
          onClick={() => {
            openDrawer("edit-profile")
          }}
        />
      </div>
      <div className="ml-[.05rem]">
        <div className="flex items-center justify-start gap-[1rem] w-full mt-[1.6rem]">
          <div className="">
            <Avatar
              shape="square"
              className="w-[2.25rem] h-[2.25rem]"
              src={
                <Image
                  preview={false}
                  src="/images/drawer/memoji.png"
                  alt="memoji"
                  className="w-full h-full rounded-full"
                  style={{
                    padding: "1px"
                  }}
                />
              }
              style={{
                backgroundColor: user?.color || '#965CDE',
              }}
            />
          </div>
          <div>
            <Text_18_600_EEEEEE className="mr-2 truncate max-w-[100%] overflow-hidden capitalize">
              {user?.name}
            </Text_18_600_EEEEEE>
          </div>
        </div>
        <div className="mt-[1.9rem] max-w-[50%] w-[39.6%] flex flex-col gap-[1.3rem]">
          <CustomInput
            name="name"
            label="Name"
            placeholder=""
            rules={[]}
            value={user?.name}
            readOnly
            onChange={(e) => {
              // handleChange('name', e.target.value)
            }}
          />
          <CustomInput
            name="email"
            label="Email"
            placeholder=""
            rules={[]}
            value={user?.email}
            readOnly
            onChange={(e) => {
              // handleChange('name', e.target.value)
            }}
          />
          <CustomInput
            name="role"
            label="User Role"
            placeholder=""
            rules={[]}
            value={removeUnderScoreAndCapatalise(user?.role)}
            readOnly
            onChange={(e) => {
              // handleChange('name', e.target.value)
            }}
          />
        </div>
      </div>
    </div>
  );
}

export default Profile;