import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import React, { useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { useEvaluations } from "src/hooks/useEvaluations";
import { successToast, errorToast } from "@/components/toast";

export default function SelectModelForNewEvaluation() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(1000);
  const [models, setModels] = React.useState([]);

  const { loading, fetchModels } = useModels();
  const [search, setSearch] = React.useState("");
  const { openDrawerWithStep, drawerProps } = useDrawer();
  const { setSelectedModel, selectedModel, stepFive } =
    usePerfomanceBenchmark();
  const { createWorkflow, currentWorkflow } = useEvaluations();

  useEffect(() => {
    fetchModels({
      page,
      limit,
      table_source: "model",
    }).then((data) => {
      setModels(data);
    });
  }, [page]);

  const filteredModels = models?.filter((model) => {
    return (
      model.name?.toLowerCase().includes(search.toLowerCase()) ||
      model.tags?.some((task) =>
        task?.name?.toLowerCase().includes(search.toLowerCase()),
      ) ||
      `${model.model_size}`.includes(search.toLowerCase())
    );
  });

  return (
    <BudForm
      data={{}}
      disableNext={!selectedModel?.id}
      onBack={async () => {
        openDrawerWithStep("new-evaluation");
      }}
      backText="Back"
      onNext={async () => {
        try {
          console.log("currentWorkflow:", currentWorkflow);
          // Check if we have the required data
          if (!selectedModel?.id) {
            errorToast("Please select a model");
            return;
          }

          if (!currentWorkflow?.workflow_id) {
            errorToast("Workflow not found. Please start over.");
            return;
          }

          // Get experiment ID from workflow or drawer props
          const experimentId =
            currentWorkflow?.workflow_steps?.experiment_id;

          if (!experimentId) {
            errorToast("Experiment ID not found");
            return;
          }

          // Prepare payload for step 2
          const payload = {
            step_number: 2,
            workflow_id: currentWorkflow.workflow_id,
            stage_data: {
              model_id: selectedModel.id,
            },
          };

          // Call the API
          const response = await createWorkflow(
            experimentId,
            payload,
          );

          // Navigate to next step
          openDrawerWithStep("select-traits");
        } catch (error) {
          console.error("Failed to update evaluation workflow:", error);
          errorToast("Failed to select model");
        }
      }}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Model Zoo"
            description="Select the model and let’s start deploying "
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DeployModelSelect
            models={models}
            filteredModels={filteredModels}
            setSelectedModel={setSelectedModel}
            selectedModel={selectedModel}
          >
            <ModelFilter search={search} setSearch={setSearch} />
          </DeployModelSelect>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
