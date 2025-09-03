import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_757575, Text_14_400_EEEEEE, Text_20_400_EEEEEE, Text_24_400_EEEEEE } from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { successToast } from "@/components/toast";
import { useUsers } from "src/hooks/useUsers";
import { useLoader } from "src/context/appContext";
import { AppRequest } from "src/pages/api/requests";
import TextInput from "../components/TextInput";

export default function UserUsageDrawer() {
  const { isLoading, showLoader, hideLoader } = useLoader();
  const { closeDrawer } = useDrawer();
  const { userDetails, getUserUsage } = useUsers();

  // State for usage data from API
  const [usageData, setUsageData] = useState({
    usedToken: 0,
    cost: 0,
    billingPlan: "Free",
    tokenQuota: 0,
    costQuota: 0,
    billingEndDate: "",
    billingPlanId: "" // Store the billing plan ID for updates
  });

  useEffect(() => {
    // Load user usage data when component mounts or userDetails changes
    if (userDetails?.id) {
      loadUserUsageData();
    }
  }, [userDetails?.id]);

  const loadUserUsageData = async () => {
    if (!userDetails?.id) {
      console.error("No user ID available");
      return;
    }

    try {
      showLoader();
      // Call the API to get user usage data
      const data = await getUserUsage(userDetails.id);

      // Log the raw data for debugging
      console.log("Raw usage data from API:", data);

      // Update the state with the fetched data from the nested structure
      // The actual usage data is in data.usage
      if (data) {
        const formattedDate = data.billing_period_end
          ? new Date(data.billing_period_end).toLocaleDateString('en-GB', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric'
            })
          : "";

        setUsageData({
          usedToken: data.usage?.tokens_used || 0,
          cost: data.usage?.cost_used || 0,
          billingPlan: data.plan_name || "Free",
          tokenQuota: data.usage?.tokens_quota || 0,
          costQuota: data.usage?.cost_quota || 0,
          billingEndDate: formattedDate,
          billingPlanId: data.billing_plan_id || "" // Store the billing plan ID
        });

        console.log("Mapped usage data:", {
          usedToken: data.usage?.tokens_used,
          cost: data.usage?.cost_used,
          billingPlan: data.plan_name,
          tokenQuota: data.usage?.tokens_quota,
          costQuota: data.usage?.cost_quota,
          billingEndDate: formattedDate,
          billingPlanId: data.billing_plan_id
        });
      }

      hideLoader();
    } catch (error) {
      hideLoader();
      console.error("Failed to load user usage data:", error);
      // Set default values on error
      setUsageData({
        usedToken: 0,
        cost: 0,
        billingPlan: "Free",
        tokenQuota: 0,
        costQuota: 0,
        billingEndDate: "",
        billingPlanId: ""
      });
    }
  };

  return (
    <BudForm
      data={{}}
      drawerLoading={isLoading}
      onBack={() => closeDrawer()}
      nextText="Save"
      onNext={async (values) => {
        try {
          showLoader();

          // The values parameter contains the form data directly
          // Prepare payload for the PUT /billing/plan API
          const payload = {
            user_id: userDetails?.id,
            billing_plan_id: usageData.billingPlanId,
            custom_token_quota: values['Custom Token Quota'] ? parseInt(values['Custom Token Quota']) : null,
            custom_cost_quota: values['Custom Usage Quota'] ? parseInt(values['Custom Usage Quota']) : null
          };

          console.log("Updating billing plan with custom quotas:", payload);

          // Call PUT API to update billing plan with custom quotas
          if (userDetails?.id && usageData.billingPlanId) {
            await AppRequest.Put(`/billing/plan`, payload);
            console.log("Successfully updated billing plan with custom quotas");
            // Reload the usage data to reflect the changes
            await loadUserUsageData();
          } else {
            console.error("Missing user ID or billing plan ID");
          }

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
                  placeholder="Enter Token Quota (optional)"
                  infoText="Leave empty to use default quota"
                  rules={[]}
                  ClassNames="mt-[.4rem]"
                  InputClasses="py-[.5rem]"
                />
              </div>

              {/* Custom Usage Quota */}
              <div className="relative">
                <TextInput
                  name="Custom Usage Quota"
                  label="Custom Cost Quota"
                  placeholder="Enter Cost Quota (optional)"
                  infoText="Leave empty to use default quota"
                  rules={[]}
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
