import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import React, { useContext, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Model, useModels } from "src/hooks/useModels";
import { useDeployModel } from "src/stores/useDeployModel";
import { BranchType } from "src/flows/ViewModel/Advanced/Advanced";
import { Text_12_300_EEEEEE } from "../../text";
import { PermissionEnum, useUser } from "src/stores/useUser";

type ExpandedItemProps = {
  selectedBranch: BranchType;
  model: Model;
};

export default function DerivedModelList() {
  const {
    openDrawerWithStep,
    expandedDrawerProps,
    closeExpandedStep,
    openDrawer,
  } = useDrawer();
  const props = expandedDrawerProps as ExpandedItemProps;

  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const { selectedProvider, reset } = useDeployModel();
  const [models, setModels] = React.useState([]);
  const { isExpandedViewOpen } = useContext(BudFormContext);

  const { loading, fetchModels } = useModels();

  const [search, setSearch] = React.useState("");
  const [showAllTags, setShowAllTags] = React.useState(false);
  const { hasPermission } = useUser();
  const { selectedModel, setSelectedModel, currentWorkflow, updateCloudModel } =
    useDeployModel();

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      setSelectedModel(currentWorkflow.workflow_steps.model);
    }
  }, [currentWorkflow]);

  useEffect(() => {
    fetchModels({
      page,
      limit,
      table_source: "model",
      // table_source: "cloud_model",
      source: selectedProvider?.type,
      base_model: props.model.uri,
      base_model_relation: props.selectedBranch.key,
    }).then((data) => {
      setModels(data);
    });
  }, [page, limit, selectedProvider, props.model, props.selectedBranch]);

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
            title={`Models Derived from ${props.model?.name}`}
            description={`Following are the models coming under ${props.model?.name}`}
          />
          <DeployModelSelect
            models={models}
            hideSelect
            filteredModels={filteredModels}
            setSelectedModel={() => {}}
            selectedModel={null}
            hideSeeMore
            emptyComponent={
              <Text_12_300_EEEEEE>
                There is no derived models added for this base model
              </Text_12_300_EEEEEE>
            }
          >
            <ModelFilter
              selectedTags={[props.selectedBranch]}
              setSelectedTags={() => {
                closeExpandedStep();
              }}
              search={search}
              setSearch={setSearch}
              buttonPermission={hasPermission(PermissionEnum.ModelManage)}
              buttonLabel={
                props.selectedBranch.name == "Quantizations"
                  ? `Add ${props.selectedBranch.name}`
                  : ""
              }
              onButtonClick={() => {
                if (props.selectedBranch.name == "Quantizations") {
                  reset();
                  openDrawer("add-quantization");
                }
              }}
            />
          </DeployModelSelect>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
