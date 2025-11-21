import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { use, useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "src/flows/components/TextInput";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import {
  ModelNameInput,
  NameIconInput,
} from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { isValidModelName } from "@/lib/utils";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import { useRouter } from "next/router";
import { useEvaluations } from "src/hooks/useEvaluations";
import { successToast, errorToast } from "@/components/toast";

export default function NewEvaluation() {
  const { openDrawerWithStep, drawerProps } = useDrawer();
  const { values, form } = useContext(BudFormContext);
  const router = useRouter();
  const { createWorkflow } = useEvaluations();

  // Get experiment ID from drawer props
  const experimentId = drawerProps?.experimentId as string;

  useEffect(()=> {
    form.resetFields();
  }, [])
  return (
    <BudForm
      data={""}
      onNext={async (values) => {
        try {
          // Check if experimentId is available
          if (!experimentId) {
            errorToast("Experiment ID not found");
            return;
          }

          // Prepare payload for step 1
          const payload = {
            step_number: 1,
            stage_data: {
              name: values.EvaluationName.toLowerCase(),
              description: values.Description,
            },
          };

          // Call the API
          await createWorkflow(experimentId, payload);

          // Navigate to next step
          openDrawerWithStep("select-model-new-evaluation");
        } catch (error) {
          console.error("Failed to create evaluation workflow:", error);
          errorToast("Failed to create evaluation workflow");
        }
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={"New Evaluation"}
            description="Create a new evaluation to assess and measure your model's performance within this experiment"
          />
          <DrawerCard classNames="">
            <TextInput
              name="EvaluationName"
              label={"Evaluation Name"}
              placeholder={"Enter evaluation name"}
              rules={[
                { required: true, message: "Please enter evaluation name" },
              ]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[.45rem]"
              infoText={"Enter Requests count"}
            />
            <TextAreaInput
              name="Description"
              label="Description"
              required
              info="Enter description"
              placeholder="Enter description"
              rules={[{ required: true, message: "Enter description" }]}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
