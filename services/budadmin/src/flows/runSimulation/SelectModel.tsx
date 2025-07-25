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
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { StepComponentsType } from "..";

export default function SelectModelForEvaluation() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const [models, setModels] = React.useState([]);

  const {
    loading,
    fetchModels
  } = useModels();
  const [search, setSearch] = React.useState("");
  const { selectedProjectId } = useProjects();
  const { selectedModel, currentWorkflow, createWorkflow, updateModel, setSelectedModel } = useDeployModel();
  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step } = useDrawer();

  useEffect(() => {
    fetchModels({
      page, limit,
      table_source: "model"
    }).then((data) => {
      setModels(data);
    });
  }, [page]);

  const filteredModels = models?.filter((model) => {
    return model.name?.toLowerCase().includes(search.toLowerCase()) || model.tags?.some((task) => task?.name?.toLowerCase().includes(search.toLowerCase())) || `${model.model_size}`.includes(search.toLowerCase());
  });


  return (
    <BudForm
      data={{}}
      onBack={async () => {
        openDrawerWithStep('additional-settingse')
      }}
      onNext={async ()=> {
        openDrawerWithStep('model-quantisation')
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
              // filterClick={() => { }}
            />
          </DeployModelSelect>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
