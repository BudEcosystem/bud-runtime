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
import { useBudPipeline, BudPipelineItem } from "src/stores/useBudPipeline";
import { successToast, errorToast } from "@/components/toast";

export default function EditPipeline() {
  const { updateWorkflow } = useBudPipeline();
  const { closeDrawer, drawerProps } = useDrawer();
  const { form, submittable } = useContext(BudFormContext);
  const [isSaving, setIsSaving] = useState(false);

  // Get the pipeline data from drawer props
  const pipeline: BudPipelineItem | undefined = drawerProps?.pipeline;

  if (!pipeline) {
    return null;
  }

  return (
    <BudForm
      data={{
        name: pipeline.name || "",
        description: pipeline.dag?.description || "",
      }}
      drawerLoading={isSaving}
      onNext={async (values) => {
        if (!submittable) {
          form.submit();
          return;
        }

        if (isSaving) {
          return;
        }

        setIsSaving(true);
        try {
          // Update the DAG with new name and description
          const updatedDag = {
            ...pipeline.dag,
            name: values.name,
            description: values.description,
          };

          const result = await updateWorkflow(pipeline.id, updatedDag);
          if (result) {
            successToast("Pipeline updated successfully");
            closeDrawer();
          } else {
            // Get error from store - updateWorkflow returns null on failure
            const storeError = useBudPipeline.getState().error;
            errorToast(storeError || "Failed to update pipeline");
          }
        } catch (err) {
          console.error("Error updating pipeline:", err);
          errorToast("Failed to update pipeline");
        } finally {
          setIsSaving(false);
        }
      }}
      nextText="Save Changes"
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Edit pipeline"
            description="Update the pipeline name and description"
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
