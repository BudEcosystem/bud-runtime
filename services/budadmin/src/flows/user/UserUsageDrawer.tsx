import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_757575, Text_14_400_EEEEEE, Text_20_400_EEEEEE, Text_24_400_EEEEEE } from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { successToast } from "@/components/toast";
import { useUsers } from "src/hooks/useUsers";
import { useLoader } from "src/context/appContext";
// import { AppRequest } from "src/pages/api/requests";
import TextInput from "../components/TextInput";

export default function UserUsageDrawer() {
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { closeDrawer } = useDrawer();
  const { userDetails } = useUsers();
  // const [customTokenQuota, setCustomTokenQuota] = useState("");
  // const [customUsageQuota, setCustomUsageQuota] = useState("");

  // Mock data - replace with actual API data
  const [usageData] = useState({
    usedToken: 126,
    cost: 512,
    billingPlan: "Free",
    tokenQuota: 512,
    costQuota: 512,
    billingEndDate: "30/02/2025"
  });

  useEffect(() => {
    // Load user usage data when component mounts
    loadUserUsageData();
  }, [userDetails]);

  const loadUserUsageData = async () => {
    try {
      showLoader();
      // TODO: Replace with actual API call to get user usage data
      // const response = await AppRequest.Get(`/users/${userDetails?.id}/usage`);
      // setUsageData(response.data);
      hideLoader();
    } catch (error) {
      hideLoader();
      console.error("Failed to load user usage data:", error);
    }
  };

  // const handleSave = async () => {
  //   try {
  //     showLoader();
  //     // TODO: Replace with actual API call to update quotas
  //     const payload = {
  //       token_quota: customTokenQuota || usageData.tokenQuota,
  //       usage_quota: customUsageQuota || usageData.costQuota
  //     };
  //     // await AppRequest.Post(`/users/${userDetails?.id}/usage`, payload);
  //     console.log("Saving quotas:", payload);

  //     successToast("Usage quotas updated successfully");
  //     closeDrawer();
  //     hideLoader();
  //   } catch (error) {
  //     hideLoader();
  //     console.error("Failed to update quotas:", error);
  //   }
  // };

  return (
    <BudForm
      data={{}}
      drawerLoading={isLoading}
      nextText="Save"
      onNext={async () => {
        try {
          showLoader();
          // TODO: Replace with actual API call to update quotas
          // const formValues = form.getFieldsValue();
          // const payload = {
          //   token_quota: formValues['Custom Token Quota'],
          //   usage_quota: formValues['Custom Usage Quota']
          // };
          // await AppRequest.Post(`/users/${userDetails?.id}/usage`, payload);

          successToast("Usage quotas updated successfully");
          closeDrawer();
          hideLoader();
        } catch (error) {
          hideLoader();
          console.error("Failed to update quotas:", error);
        }
      }}
    >
      <BudWraperBox classNames="mt-[2.2rem]">
        <BudDrawerLayout>
          {/* Header Section */}
          <div className="flex flex-col items-start justify-start w-full px-[1.4rem] py-[1.05rem] pb-[1.4rem] border-b-[.5px] border-b-[#1F1F1F]">
            <Text_14_400_EEEEEE className="mb-[0.35rem]">
              Usage Values
            </Text_14_400_EEEEEE>
            <Text_12_400_757575>Description for usage values...</Text_12_400_757575>
          </div>

          {/* Content Section */}
          <div className="px-[1.45rem] py-6">
            {/* Usage Statistics Grid */}
            <div className="grid grid-cols-3 gap-2 mb-2">
              {/* Used Token */}
              <div className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg p-4">
                <Text_14_400_EEEEEE className="mb-3 block">
                  Used Token
                  <div className="w-[1.6491rem] h-[0.1832rem] bg-[#6B46C1] mt-[.1rem]"></div>
                </Text_14_400_EEEEEE>
                <Text_24_400_EEEEEE className="text-2xl">
                  {usageData.usedToken}
                </Text_24_400_EEEEEE>
              </div>

              {/* Cost */}
              <div className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg p-4">
                <Text_14_400_EEEEEE className="mb-3 block">
                  Cost
                  <div className="w-[1.6491rem] h-[0.1832rem] bg-[#6B46C1] mt-[.1rem]"></div>
                </Text_14_400_EEEEEE>
                <Text_24_400_EEEEEE className="text-2xl">
                  {usageData.cost} $
                </Text_24_400_EEEEEE>
              </div>

              {/* Billing Plan */}
              <div className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg p-4">
                <Text_14_400_EEEEEE className="mb-3 block">
                  Billing Plan
                  <div className="w-[1.6491rem] h-[0.1832rem] bg-[#6B46C1] mt-[.1rem]"></div>
                </Text_14_400_EEEEEE>
                <Text_24_400_EEEEEE className="text-2xl">
                  {usageData.billingPlan}
                </Text_24_400_EEEEEE>
              </div>
            </div>

            {/* Quota Information Grid */}
            <div className="grid grid-cols-3 gap-2 mb-8">
              {/* Token Quota */}
              <div className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg p-4">
                <div className="mb-3">
                  <Text_14_400_EEEEEE className="pb-1">
                    Token Quota
                    <div className="w-[1.6491rem] h-[0.1832rem] bg-[#6B46C1] mt-[.1rem]"></div>
                  </Text_14_400_EEEEEE>
                </div>
                <Text_24_400_EEEEEE className="text-2xl">
                  {usageData.tokenQuota}
                </Text_24_400_EEEEEE>
              </div>

              {/* Cost Quota */}
              <div className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg p-4">
                <div className="mb-3">
                  <Text_14_400_EEEEEE className="pb-1">
                    Cost Quota
                    <div className="w-[1.6491rem] h-[0.1832rem] bg-[#6B46C1] mt-[.1rem]"></div>
                  </Text_14_400_EEEEEE>
                </div>
                <Text_24_400_EEEEEE className="text-2xl">
                  {usageData.costQuota} $
                </Text_24_400_EEEEEE>
              </div>

              {/* Billing End Date */}
              <div className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg p-4">
                <div className="mb-3">
                  <Text_14_400_EEEEEE className="pb-1">
                    Billing End Date
                    <div className="w-[1.6491rem] h-[0.1832rem] bg-[#6B46C1] mt-[.1rem]"></div>
                  </Text_14_400_EEEEEE>
                </div>
                <Text_20_400_EEEEEE className="text-2xl">
                  {usageData.billingEndDate}
                </Text_20_400_EEEEEE>
              </div>
            </div>

            {/* Custom Quota Inputs */}
            <div className="space-y-5 mb-8">
              {/* Custom Token Quota */}
              <div className="relative">
                <TextInput
                  name="Custom Token Quota"
                  label="Custom Token Quota"
                  placeholder="Enter Token Quota"
                  infoText="Custom Token Quota"
                  rules={[
                    { required: true, message: "Please enter custom token quota" },
                  ]}
                  ClassNames="mt-[.4rem]"
                  InputClasses="py-[.5rem]"
                />
              </div>

              {/* Custom Usage Quota */}
              <div className="relative">
                <TextInput
                  name="Custom Usage Quota"
                  label="Custom Usage Quota"
                  placeholder="Enter Usage Quota"
                  infoText="Custom Usage Quota"
                  rules={[
                    { required: true, message: "Please enter custom usage quota" },
                  ]}
                  ClassNames="mt-[.4rem]"
                  InputClasses="py-[.5rem]"
                />
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
