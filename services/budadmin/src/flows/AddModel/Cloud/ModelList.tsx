import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import React, { useContext, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useDeployModel } from "src/stores/useDeployModel";

export default function ModelList() {
  const { openDrawerWithStep } = useDrawer();

  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);

  const { selectedProvider, modalityType } = useDeployModel();
  const [models, setModels] = React.useState([]);
  const { isExpandedViewOpen } = useContext(BudFormContext);

  const { loading, fetchModels } = useModels();

  const [search, setSearch] = React.useState("");
  const [showAllTags, setShowAllTags] = React.useState(false);
  const { selectedModel, setSelectedModel, currentWorkflow, updateCloudModel } =
    useDeployModel();

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      setSelectedModel(currentWorkflow.workflow_steps.model);
    }
  }, [currentWorkflow]);

  useEffect(() => {
    const endpoints = modalityType?.endpoints && modalityType.endpoints.length > 0
      ? modalityType.endpoints
      : undefined;
    const modalities = !endpoints && modalityType?.modalities && modalityType.modalities.length > 0
      ? modalityType.modalities
      : undefined;

    if (!selectedProvider?.type) {
      setModels([]);
      return;
    }

    fetchModels({
      page,
      limit,
      table_source: "cloud_model",
      source: selectedProvider?.type,
      modality: modalities,
      supported_endpoints: endpoints,
    }).then((data) => {
      setModels(data);
    });
  }, [selectedProvider?.type, modalityType?.modalities, modalityType?.endpoints, page, limit, fetchModels]);

  useEffect(() => {
    if (!selectedModel) {
      return;
    }

    if (!models.some((model) => model.id === selectedModel.id)) {
      setSelectedModel(null);
    }
  }, [models, selectedModel, setSelectedModel]);

  const filteredModels = models?.filter((model) => {
    return (
      model.name?.toLowerCase().includes(search.toLowerCase()) ||
      model.tags?.some((task) =>
        task.name?.toLowerCase().includes(search.toLowerCase()),
      ) ||
      `${model.model_size}`.includes(search.toLowerCase())
    );
  });

  return (
    <BudForm
      data={{}}
      onBack={() => {
        openDrawerWithStep("cloud-providers");
      }}
      disableNext={!selectedModel?.id || isExpandedViewOpen}
      onNext={async () => {
        if (!currentWorkflow) {
          return openDrawerWithStep("model-source");
        } else {
          const result = await updateCloudModel();
          if (result) {
            openDrawerWithStep("add-model");
          }
        }
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={`Select a Model from ${selectedProvider?.name}`}
            description={`Pick a cloud model from the list below to add to your model repository and if you can't find one, add a new cloud model by ${selectedProvider?.name}`}
          />
          <DeployModelSelect
            models={models}
            filteredModels={filteredModels}
            setSelectedModel={setSelectedModel}
            selectedModel={selectedModel}
            hideSeeMore
          >
            <ModelFilter
              search={search}
              setSearch={setSearch}
              buttonLabel="+&nbsp;Cloud&nbsp;Model"
              onButtonClick={() => {
                setSelectedModel(null);
                openDrawerWithStep("add-model");
              }}
            />
          </DeployModelSelect>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
