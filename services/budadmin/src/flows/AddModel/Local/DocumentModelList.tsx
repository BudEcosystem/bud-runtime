import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { Model, useModels } from "src/hooks/useModels";

const modalityLabels: Record<string, string> = {
  text_input: "text input",
  text_output: "text output",
  image_input: "image input",
  image_output: "image output",
  audio_input: "audio input",
  audio_output: "audio output",
};

const formatModalityLabels = (modalities: string[] | undefined) => {
  if (!modalities?.length) {
    return [];
  }

  return modalities.map((modality) => {
    const label = modalityLabels[modality] ?? modality.replace(/_/g, " ");
    return label.replace(/\b\w/g, (char) => char.toUpperCase());
  });
};

const formatEndpointLabels = (endpoints: string[] | undefined) => {
  if (!endpoints?.length) {
    return [];
  }

  return endpoints.map((endpoint) => {
    const slug = endpoint.split("/").filter(Boolean).pop() || endpoint;
    return slug
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  });
};

export default function DocumentModelList() {
  const { openDrawerWithStep } = useDrawer();
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const {
    selectedModel,
    setSelectedModel,
    currentWorkflow,
    setLocalModelDetails,
    setCameFromDocumentList,
    modalityType,
  } = useDeployModel();
  const { fetchModels, loading } = useModels();

  const [models, setModels] = useState<Model[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      setSelectedModel(currentWorkflow.workflow_steps.model);
    }
  }, [currentWorkflow, setSelectedModel]);

  useEffect(() => {
    let isMounted = true;

    const loadModels = async () => {
      const preferredEndpoints = modalityType?.endpoints && modalityType.endpoints.length > 0
        ? modalityType.endpoints
        : undefined;
      const preferredModalities = !preferredEndpoints && modalityType?.modalities && modalityType.modalities.length > 0
        ? modalityType.modalities
        : undefined;
      try {
        const data = await fetchModels({
          page: 1,
          limit: 100,
          table_source: "cloud_model",
          source: "huggingface",
          modality: preferredModalities,
          supported_endpoints: preferredEndpoints,
        });

        if (!isMounted) {
          return;
        }

        const documentModels = (data ?? []).filter((model) => model?.provider?.type === "huggingface");
        setModels(documentModels);
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setModels([]);
      }
    };

    loadModels();

    return () => {
      isMounted = false;
    };
  }, [fetchModels, modalityType?.modalities, modalityType?.endpoints]);

  useEffect(() => {
    if (!selectedModel) {
      return;
    }

    if (!models.some((model) => model.id === selectedModel.id)) {
      setSelectedModel(null);
    }
  }, [models, selectedModel, setSelectedModel]);

  const filteredModels = models.filter((model) => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return true;
    }

    return (
      model.name?.toLowerCase().includes(query) ||
      model.uri?.toLowerCase().includes(query) ||
      model.description?.toLowerCase().includes(query) ||
      model.tags?.some((tag) => tag.name?.toLowerCase().includes(query))
    );
  });

  const handleModelSelect = (model: Model) => {
    setSelectedModel(model);
    // Pre-fill the local model details - prefer URI over display name
    const fallbackName = model.uri || model.name;
    setLocalModelDetails({
      name: fallbackName,
      uri: model.uri || fallbackName,
      author: model.author || "",
      tags: model.tags || [],
      icon: model.icon || "",
    });
  };

  const handleAddCustom = () => {
    setSelectedModel(null);
    setLocalModelDetails({
      name: "",
      uri: "",
      author: "",
      tags: [],
      icon: "",
    });
    setCameFromDocumentList(true);
    openDrawerWithStep("add-local-model");
  };

  const handleNext = async () => {
    if (selectedModel) {
      // Pre-populate the local model details with selected cloud model
      const fallbackName = selectedModel.uri || selectedModel.name;
      setLocalModelDetails({
        name: fallbackName,
        uri: selectedModel.uri || fallbackName,
        author: selectedModel.author || "",
        tags: selectedModel.tags || [],
        icon: selectedModel.icon || "",
      });
      setCameFromDocumentList(true);
      // Go to the Enter Model Information step with pre-filled data
      openDrawerWithStep("add-local-model");
    }
  };

  return (
    <BudForm
      data={{}}
      onBack={() => {
        openDrawerWithStep("model-source");
      }}
      disableNext={!selectedModel?.id || isExpandedViewOpen}
      onNext={handleNext}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select a Document Model"
            description="Choose from our curated list of document processing models from Hugging Face or add your own custom model"
          />
          <DeployModelSelect
            models={models}
            filteredModels={filteredModels}
            setSelectedModel={handleModelSelect}
            selectedModel={selectedModel}
            hideSeeMore
            emptyComponent={(
              <div className="text-[#757575] text-[.75rem] text-center px-[1rem]">
                {loading && !models.length
                  ? "Loading Hugging Face document models..."
                  : !models.length
                    ? (() => {
                        const modalityRequirement = formatModalityLabels(modalityType?.modalities).join(", ");
                        const endpointRequirement = formatEndpointLabels(modalityType?.endpoints).join(", ");
                        if (modalityRequirement && endpointRequirement) {
                          return `No Hugging Face document models support modalities: ${modalityRequirement} and endpoints: ${endpointRequirement}.`;
                        }
                        if (modalityRequirement) {
                          return `No Hugging Face document models support modalities: ${modalityRequirement}.`;
                        }
                        if (endpointRequirement) {
                          return `No Hugging Face document models expose endpoints: ${endpointRequirement}.`;
                        }
                        return "No Hugging Face document models are available right now.";
                      })()
                    : search.trim()
                      ? "No models matched your search. Try different keywords or add a custom model."
                      : "No Hugging Face document models matched your filters. Try a different configuration or add a custom model."}
              </div>
            )}
          >
            <ModelFilter
              search={search}
              setSearch={setSearch}
              buttonLabel="+&nbsp;Custom&nbsp;Model"
              onButtonClick={handleAddCustom}
            />
          </DeployModelSelect>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
