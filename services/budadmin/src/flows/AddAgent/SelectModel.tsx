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
import { useAddAgent } from "@/stores/useAddAgent";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

export default function SelectModel() {
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(1000);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState<any>(null);
  const [search, setSearch] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { loading, fetchModels } = useModels();
  const { openDrawerWithStep, closeDrawer } = useDrawer();

  // Use the Add Agent store for workflow management
  const {
    currentWorkflow,
    selectedProject,
    setSelectedModel: setStoreSelectedModel,
    getWorkflow
  } = useAddAgent();

  // Load workflow on component mount if it exists
  useEffect(() => {
    if (currentWorkflow?.workflow_id) {
      getWorkflow(currentWorkflow.workflow_id);
    }
  }, [currentWorkflow?.workflow_id, getWorkflow]);

  useEffect(() => {
    fetchModels({
      page,
      limit,
      table_source: "model",
    }).then((data) => {
      setModels(data);
    });
  }, [page, limit, fetchModels]);

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

    if (!currentWorkflow?.workflow_id) {
      errorToast("Workflow not initialized. Please start from the beginning.");
      return;
    }

    setIsSubmitting(true);

    try {
      // Store in the Add Agent store
      setStoreSelectedModel(selectedModel);

      // Prepare the workflow API payload
      const payload: any = {
        workflow_id: currentWorkflow.workflow_id,
        step_number: 3,
        model_id: selectedModel.id,
        model_name: selectedModel.name
      };

      // If there's an endpoint from a previous model deployment or from workflow_steps, include it
      // Otherwise, this might create a new endpoint
      if (currentWorkflow.workflow_steps?.endpoint?.id) {
        payload.endpoint_id = currentWorkflow.workflow_steps.endpoint.id;
      } else if ((currentWorkflow as any).endpoint_id) {
        payload.endpoint_id = (currentWorkflow as any).endpoint_id;
      }

      // Call the workflow API for step 3
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        payload,
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": selectedProject?.id || currentWorkflow.workflow_steps?.project?.id
          }
        }
      );

      if (response?.data) {
        // Update the workflow in the store
        await getWorkflow(currentWorkflow.workflow_id);

        // Navigate to the agent configuration screen
        openDrawerWithStep("add-agent-configuration");
      } else {
        errorToast("Failed to select model");
      }

    } catch (error) {
      console.error("Failed to select model:", error);
      errorToast("Failed to select model");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBack = () => {
    openDrawerWithStep("add-agent-select-project");
  };

  return (
    <BudForm
      data={{}}
      disableNext={!selectedModel?.id || isSubmitting || loading}
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
