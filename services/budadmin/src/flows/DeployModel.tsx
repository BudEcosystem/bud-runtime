import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import React, { useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useProjects } from "src/hooks/useProjects";
import { useDeployModel } from "src/stores/useDeployModel";
import { StepComponentsType } from ".";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { useRouter } from "next/router";

export default function DeployModel() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(1000);
  const [models, setModels] = React.useState([]);

  const { loading, fetchModels } = useModels();
  const [search, setSearch] = React.useState("");
  const { selectedProjectId } = useProjects();
  const {
    selectedModel,
    currentWorkflow,
    createWorkflow,
    updateModel,
    setSelectedModel,
    cancelModelDeployment,
  } = useDeployModel();
  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step } =
    useDrawer();
  const router = useRouter();
  const projectId = router.query.projectId as string;
  useEffect(() => {
    fetchModels({
      page,
      limit,
      table_source: "model",
      exclude_adapters: true,
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
      onNext={async () => {
        let response;
        if (!currentWorkflow) {
          response = await createWorkflow(selectedProjectId);
        } else {
          response = await updateModel();
        }
        if (!response) {
          return;
        }

        // TODO Check
        if (selectedModel?.provider_type === "cloud_model") {
          return openDrawerWithStep("deploy-model-credential-select");
        }

        openDrawerWithStep("deploy-model-template");
      }}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Model Zoo"
            description="Select the model and let’s start deploying "
          />
          <DeployModelSelect
            models={models}
            filteredModels={filteredModels}
            setSelectedModel={setSelectedModel}
            selectedModel={selectedModel}
          >
            <ModelFilter
              search={search}
              setSearch={setSearch}
              buttonLabel="+&nbsp;New&nbsp;Model"
              onButtonClick={() => {
                cancelModelDeployment(currentWorkflow?.workflow_id, projectId);
                setSelectedModel(null);
                setPreviousStep(step.id as StepComponentsType);
                openDrawer("add-model");
              }}
            />
          </DeployModelSelect>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
