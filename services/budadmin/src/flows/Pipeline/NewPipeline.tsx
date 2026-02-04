import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useBudPipeline, DAGDefinition } from "src/stores/useBudPipeline";
import { useRouter } from "next/router";
import { successToast, errorToast } from "@/components/toast";

export default function NewPipeline() {
  const router = useRouter();
  const { createWorkflow, error } = useBudPipeline();
  const { closeDrawer } = useDrawer();
  const { form, submittable } = useContext(BudFormContext);
  const [isCreating, setIsCreating] = useState(false);

  return (
    <BudForm
      data={{
        name: "",
        icon: "🔄",
        description: "",
      }}
      drawerLoading={isCreating}
      onNext={async (values) => {
        if (!submittable) {
          form.submit();
          return;
        }

        if (isCreating) {
          return;
        }

        setIsCreating(true);
        try {
          // Create a minimal DAG with the basic info
          const dag: DAGDefinition = {
            name: values.name,
            description: values.description,
            parameters: [],
            steps: [],
            outputs: {},
          };

          const result = await createWorkflow(dag);
          if (result) {
            successToast("Pipeline draft created");
            closeDrawer();
            // Redirect to the detail page for visual editing
            router.push(`/pipelines/${result.id}`);
          } else {
            // Get error from store - createWorkflow returns null on failure
            const storeError = useBudPipeline.getState().error;
            errorToast(storeError || "Failed to create pipeline");
          }
        } catch (err) {
          console.error("Error creating pipeline:", err);
          errorToast("Failed to create pipeline");
        } finally {
          setIsCreating(false);
        }
      }}
      nextText="Create Draft"
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create a new pipeline"
            description="Define the basic info for your pipeline"
          />
          <DrawerCard classNames="pb-0">
            <ProjectNameInput
              placeholder="Enter Pipeline Name"
              isEdit={true}
            />
            <TextAreaInput
              name="description"
              label="Description"
              info="Describe what this pipeline does"
              placeholder="Brief description of the pipeline purpose and steps"
              rules={[]}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
