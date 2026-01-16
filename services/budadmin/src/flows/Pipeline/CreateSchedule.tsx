import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import BudSwitch from "@/components/ui/bud/dataEntry/BudSwitch";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import { Text_12_400_757575 } from "@/components/ui/text";
import { Form, message } from "antd";
import React, { useContext, useMemo, useState } from "react";
import CustomSelect from "src/flows/components/CustomSelect";
import TextInput from "src/flows/components/TextInput";
import { useDrawer } from "src/hooks/useDrawer";
import { useBudPipeline, ScheduleConfig } from "src/stores/useBudPipeline";

const scheduleTypeDescriptions: Record<string, string> = {
  cron: "Run on a cron schedule (e.g. 0 9 * * 1-5).",
  interval: "Run on a fixed interval (e.g. @every 1h).",
  one_time: "Run only once at the configured time (ISO 8601).",
};

const CreateSchedule = () => {
  const { form, submittable } = useContext(BudFormContext);
  const { drawerProps, closeDrawer } = useDrawer();
  const { createSchedule, getSchedules } = useBudPipeline();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const workflowId = drawerProps?.workflowId as string | undefined;

  const initialValues = useMemo(
    () => ({
      name: "",
      type: "cron",
      expression: "",
      run_at: "",
      timezone: "UTC",
      description: "",
      enabled: true,
    }),
    []
  );

  const handleSubmit = async (values: any) => {
    if (!workflowId) return;
    setIsSubmitting(true);
    const schedule: ScheduleConfig = {
      type: values.type,
      timezone: values.timezone || "UTC",
    };

    if (values.type === "one_time") {
      schedule.run_at = values.run_at;
    } else {
      schedule.expression = values.expression;
    }

    const result = await createSchedule({
      workflow_id: workflowId,
      name: values.name,
      schedule,
      params: {},
      enabled: values.enabled ?? true,
      description: values.description,
    });

    if (result) {
      message.success("Schedule created successfully");
      await getSchedules(workflowId);
      closeDrawer();
    } else {
      message.error("Failed to create schedule");
    }
    setIsSubmitting(false);
  };

  return (
    <BudForm
      data={initialValues}
      drawerLoading={isSubmitting}
      onBack={() => closeDrawer()}
      backText="Cancel"
      nextText="Create Schedule"
      disableNext={!submittable}
      onNext={async () => {
        if (!submittable) {
          form.submit();
          return;
        }
        const values = await form.validateFields();
        await handleSubmit(values);
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Schedule"
            description="Set up a recurring trigger to run this pipeline automatically."
          />
          <div className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
            <TextInput
              name="name"
              label="Schedule Name"
              placeholder="Daily Health Check"
              infoText="Give this schedule a clear name."
              rules={[{ required: true, message: "Name is required" }]}
              formItemClassnames="mb-0"
            />

            <Form.Item
              name="type"
              rules={[{ required: true, message: "Schedule type is required" }]}
              className="mb-0"
              hasFeedback
            >
              <CustomSelect
                name="type"
                label="Schedule Type"
                info="Select how often this schedule runs."
                placeholder="Select type"
                selectOptions={[
                  { label: "Cron Expression", value: "cron" },
                  { label: "Fixed Interval", value: "interval" },
                  { label: "One-Time", value: "one_time" },
                ]}
              />
            </Form.Item>

            <Form.Item noStyle shouldUpdate={(prev, curr) => prev.type !== curr.type}>
              {({ getFieldValue }) => {
                const type = getFieldValue("type");
                if (type === "cron") {
                  return (
                    <TextInput
                      name="expression"
                      label="Cron Expression"
                      placeholder="0 9 * * 1-5"
                      infoText="Example: 0 9 * * 1-5 (9 AM on weekdays)"
                      rules={[{ required: true, message: "Cron expression is required" }]}
                      formItemClassnames="mb-0"
                    />
                  );
                }
                if (type === "interval") {
                  return (
                    <TextInput
                      name="expression"
                      label="Interval"
                      placeholder="@every 1h"
                      infoText="Example: @every 1h, @every 30m, @every 24h"
                      rules={[{ required: true, message: "Interval is required" }]}
                      formItemClassnames="mb-0"
                    />
                  );
                }
                if (type === "one_time") {
                  return (
                    <TextInput
                      name="run_at"
                      label="Run At"
                      placeholder="2024-05-01T09:00:00Z"
                      infoText="Use ISO 8601 format (UTC recommended)."
                      rules={[{ required: true, message: "Run time is required" }]}
                      formItemClassnames="mb-0"
                    />
                  );
                }
                return null;
              }}
            </Form.Item>

            <Form.Item noStyle shouldUpdate={(prev, curr) => prev.type !== curr.type}>
              {({ getFieldValue }) => (
                <Text_12_400_757575 className="-mt-2">
                  {scheduleTypeDescriptions[getFieldValue("type")] || ""}
                </Text_12_400_757575>
              )}
            </Form.Item>

            <Form.Item name="timezone" className="mb-0">
              <CustomSelect
                name="timezone"
                label="Timezone"
                info="Select the timezone for this schedule."
                placeholder="UTC"
                selectOptions={[
                  { label: "UTC", value: "UTC" },
                  { label: "US Eastern", value: "America/New_York" },
                  { label: "US Pacific", value: "America/Los_Angeles" },
                  { label: "London", value: "Europe/London" },
                  { label: "Tokyo", value: "Asia/Tokyo" },
                ]}
              />
            </Form.Item>

            <TextAreaInput
              name="description"
              label="Description"
              info="Optional notes for this schedule."
              placeholder="What this schedule does..."
              rules={[]}
              formItemClassnames="mb-0"
            />

            <BudSwitch
              name="enabled"
              label="Enabled"
              infoText="Enable this schedule to run automatically."
              placeholder="Enable schedule"
              defaultValue={initialValues.enabled}
              formItemClassnames="mb-0"
            />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default CreateSchedule;
