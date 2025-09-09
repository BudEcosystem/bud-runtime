import React, { useState } from "react";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { useDrawer } from "@/hooks/useDrawer";
import { useBillingAlerts } from "@/hooks/useBillingAlerts";
import { successToast } from "@/components/toast";
import TextInput from "@/components/ui/bud/dataEntry/TextInput";
import CustomSelect from "@/components/ui/bud/dataEntry/CustomSelect";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";

export default function CreateBillingAlert() {
  const { closeDrawer } = useDrawer();
  const { alerts, createBillingAlert, getBillingAlerts } = useBillingAlerts();
  const [loading, setLoading] = useState(false);
  const [alertName, setAlertName] = useState("");
  const [alertType, setAlertType] = useState<"token_usage" | "cost_usage">(
    "cost_usage",
  );
  const [alertThreshold, setAlertThreshold] = useState(75);

  const handleCreate = async () => {
    if (!alertName.trim()) {
      return;
    }

    if (alertThreshold < 1 || alertThreshold > 100) {
      return;
    }

    try {
      setLoading(true);
      await createBillingAlert({
        name: alertName.trim(),
        alert_type: alertType,
        threshold_percent: alertThreshold,
      });
      successToast("Billing alert created successfully");
      await getBillingAlerts(); // Refresh the alerts list
      closeDrawer();
    } catch (error: any) {
      console.error("Error creating billing alert:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <BudForm
      backText="Cancel"
      nextText="Create Alert"
      disableNext={loading}
      onBack={() => closeDrawer()}
      onNext={handleCreate}
      data={{}}
      drawerLoading={loading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Billing Alert"
            description="Set up an alert to notify you when your usage reaches a certain threshold"
          />

          <DrawerCard>
            <div className="flex flex-col gap-2">
              {/* Alert Name */}
              <TextInput
                name="alertName"
                label="Alert Name"
                value={alertName}
                placeholder="Enter a name for this alert"
                rules={[
                  { required: true, message: "Alert name is required" },
                  {
                    validator: (_, value) => {
                      if (!value) return Promise.resolve();
                      const existingAlert = alerts.find(
                        (alert) =>
                          alert.name.toLowerCase() ===
                          value.trim().toLowerCase(),
                      );
                      if (existingAlert) {
                        return Promise.reject(
                          "An alert with this name already exists",
                        );
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
                onChange={setAlertName}
              />

              {/* Alert Type */}
              <div className="flex flex-col gap-2 mb-4">
                <CustomSelect
                  name="alertType"
                  label="Alert Type"
                  value={alertType}
                  onChange={(value) =>
                    setAlertType(value as "token_usage" | "cost_usage")
                  }
                  selectOptions={[
                    { value: "cost_usage", label: "Cost Usage Alert" },
                    { value: "token_usage", label: "Token Usage Alert" },
                  ]}
                  rules={[]}
                />
                <Text_12_400_B3B3B3>
                  {alertType === "cost_usage"
                    ? "Get notified when your spending reaches the threshold"
                    : "Get notified when your token usage reaches the threshold"}
                </Text_12_400_B3B3B3>
              </div>

              {/* Threshold */}
              <div className="flex flex-col gap-2">
                <TextInput
                  name="threshold"
                  label="Threshold (%)"
                  type="number"
                  value={alertThreshold.toString()}
                  placeholder="Enter threshold percentage (1-100)"
                  allowOnlyNumbers={true}
                  rules={[
                    { required: true, message: "Threshold is required" },
                    {
                      validator: (_, value) => {
                        const num = Number(value);
                        if (num < 1 || num > 100) {
                          return Promise.reject(
                            "Threshold must be between 1 and 100",
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  suffix={<span className="text-[#757575] text-xs">%</span>}
                  onChange={(value) => {
                    let numValue = Number(value);
                    if (numValue > 100) numValue = 100;
                    if (numValue < 0) numValue = 0;
                    setAlertThreshold(numValue);
                  }}
                />
                <Text_12_400_B3B3B3>
                  You&apos;ll be notified when usage reaches {alertThreshold}%
                  of your quota
                </Text_12_400_B3B3B3>
              </div>

              {/* Info Box */}
              <div className="mt-4 p-4 bg-[#EEEEEE] dark:bg-[#1A1A1A] border border-[#2A2A2A] rounded-lg">
                <div className="flex items-start gap-3">
                  <span className="text-[#965CDE] text-lg">ℹ️</span>
                  <div className="flex flex-col gap-1">
                    <Text_14_400_EEEEEE>How alerts work</Text_14_400_EEEEEE>
                    <Text_12_400_B3B3B3>
                      • Alerts are checked periodically throughout your billing
                      cycle
                    </Text_12_400_B3B3B3>
                    <Text_12_400_B3B3B3>
                      • You&apos;ll receive notifications via email when
                      thresholds are reached
                    </Text_12_400_B3B3B3>
                    <Text_12_400_B3B3B3>
                      • Each alert triggers only once per billing period
                    </Text_12_400_B3B3B3>
                    <Text_12_400_B3B3B3>
                      • You can enable/disable alerts at any time
                    </Text_12_400_B3B3B3>
                  </div>
                </div>
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
