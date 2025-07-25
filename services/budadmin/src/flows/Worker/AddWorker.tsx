import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext } from "react";
import TextInput from "../components/TextInput";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import AddWorkerInfoCard from "../components/AddWorkerInfoCard";
import { errorToast } from "@/components/toast";
import { useEndPoints } from "src/hooks/useEndPoint";
import { Form, Image, Input } from "antd";
import { Text_12_300_EEEEEE } from "@/components/ui/text";
import CustomPopover from "../components/customPopover";
import { useRouter } from "next/router";

export default function AddWorker() {
  const { submittable, form } = useContext(BudFormContext);
  const [formData, setFormData] = React.useState<FormData>(new FormData());
  const { getWorkflow, workerDetails, createWorkerFlow } = useDeployModel();
  const { clusterDetails } = useEndPoints();
  const { openDrawerWithStep } = useDrawer();
  const router = useRouter();
  const projectId = router.query.projectId as string;
  
  return (
    <BudForm
      data={{
        additonal_concurrency: '1',
      }}
      disableNext={!submittable}
      onNext={async (values) => {
        if (!submittable) {
          form.submit();
          return;
        };
        const result = await createWorkerFlow(clusterDetails.id, values.additonal_concurrency, projectId);
        if (result) {
          await getWorkflow(result.workflow_id);
          openDrawerWithStep("add-worker-cluster-config-status");
        }
      }}
    >
      <BudWraperBox classNames="mt-[1.6rem]">
        <AddWorkerInfoCard />
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Worker Configuration"
            description="Enter the additional concurrency to identify the required hardware"
          />
          <DrawerCard classNames="pb-0 mt-[.2rem]">

            <Form.Item
              name={"additonal_concurrency"} hasFeedback
              rules={[
                {
                  required: true,
                  min: 1,
                  message: "Please enter additional concurrency required",
                },
                {
                  min: 1,
                  message: "Concurrent requests should be greater than 0",
                }
              ]}
              className={`flex items-start rounded-[6px] relative !bg-[transparent] mb-[0]`}
            >
              <div className="w-full">
                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                  Additional Concurrency
                  <CustomPopover title="The number of additional requests you want the model to handle at the same time.">
                    <Image
                      preview={false}
                      src="/images/info.png"
                      alt="info"
                      style={{ width: '.75rem', height: '.75rem' }}
                    />
                  </CustomPopover>
                </Text_12_300_EEEEEE>
              </div>
              <Input
                type="number"
                placeholder="Enter value"
                style={{
                  backgroundColor: "transparent",
                  color: "#EEEEEE",
                  border: "0.5px solid #757575",
                }}
                min={1}
                value={form.getFieldValue("additonal_concurrency")}
                onChange={(e) => {
                  if (e.target.value.startsWith("0") && e.target.value.length > 1) {
                    e.target.value = e.target.value.slice(1);
                  }
                  if (e.target.value.length > 3) {
                    errorToast("Concurrent requests should be less than 1000");
                    return;
                  }
                  if (e.target.value.length === 1 && e.target.value === "0") {
                    e.target.value = "";
                  }

                  form.setFieldsValue({ additonal_concurrency: e.target.value });
                  form.validateFields(['additonal_concurrency']);
                }}
                size="large"
                className="drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
              />
            </Form.Item>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
