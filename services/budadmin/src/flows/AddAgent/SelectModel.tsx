import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { errorToast } from "@/components/toast";
import { usePromptsAgents } from "@/stores/usePromptsAgents";

export default function SelectModel() {
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(1000);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState<any>(null);
  const [search, setSearch] = useState("");

  const { loading, fetchModels } = useModels();
  const { openDrawerWithStep, closeDrawer } = useDrawer();

  // Get project data from localStorage (stored in SelectProject)
  const getSelectedProject = () => {
    const projectData = localStorage.getItem("addAgent_selectedProject");
    return projectData ? JSON.parse(projectData) : null;
  };

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

  const handleNext = async () => {
    if (!selectedModel) {
      errorToast("Please select a model");
      return;
    }

    try {
      // Store selected model for later use in the flow
      localStorage.setItem("addAgent_selectedModel", JSON.stringify(selectedModel));

      // Navigate to the agent configuration screen
      openDrawerWithStep("add-agent-configuration");

    } catch (error) {
      console.error("Failed to select model:", error);
      errorToast("Failed to select model");
    }
  };

  const handleBack = () => {
    openDrawerWithStep("add-agent-select-project");
  };

  return (
    <BudForm
      data={{}}
      disableNext={!selectedModel?.id}
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Models"
            description="Select model from model zoo"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
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
