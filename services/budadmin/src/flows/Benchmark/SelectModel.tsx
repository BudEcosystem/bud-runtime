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

export default function SelectModel() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(1000);
  const [models, setModels] = React.useState([]);

  const { loading, fetchModels } = useModels();
  const [search, setSearch] = React.useState("");
  const { openDrawerWithStep } = useDrawer();
  const { setSelectedModel, selectedModel, stepFive } =
    usePerfomanceBenchmark();

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
    // Exclude cloud models from benchmark listing
    if (model.provider_type === "cloud_model") {
      return false;
    }
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
      // disableNext={!selectedModel?.id}
      // onNext={async () => {
      //   openDrawerWithStep("Benchmark-Configuration");
      // }}
      onBack={async () => {
        openDrawerWithStep("Select-Nodes");
      }}
      backText="Back"
      onNext={() => {
        stepFive().then((result) => {
          if (result) {
            console.log("result", result.data.workflow_steps.provider_type);
            if (result.data.workflow_steps.provider_type === "cloud_model") {
              openDrawerWithStep("model_benchmark-credential-select");
            } else {
              openDrawerWithStep("Select-Configuration");
            }
          }
        });
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
