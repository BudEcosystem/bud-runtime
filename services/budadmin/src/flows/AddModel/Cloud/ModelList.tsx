import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import React, { useContext, useEffect, useRef, useCallback } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useDeployModel } from "src/stores/useDeployModel";

const PAGE_SIZE = 50;

export default function ModelList() {
  const { openDrawerWithStep } = useDrawer();

  const pageRef = useRef(1);

  const { selectedProvider, modalityType } = useDeployModel();
  const [models, setModels] = React.useState([]);
  const [hasMore, setHasMore] = React.useState(true);
  const [isLoadingMore, setIsLoadingMore] = React.useState(false);
  const lastScrollTop = useRef(0);
  const { isExpandedViewOpen } = useContext(BudFormContext);

  const { loading, fetchModels } = useModels();

  const [search, setSearch] = React.useState("");
  const [showAllTags, setShowAllTags] = React.useState(false);
  const { selectedModel, setSelectedModel, currentWorkflow, updateCloudModel } =
    useDeployModel();

  const getFilterParams = useCallback(() => {
    const endpoints =
      modalityType?.endpoints && modalityType.endpoints.length > 0
        ? modalityType.endpoints
        : undefined;
    const modalities =
      !endpoints &&
      modalityType?.modalities &&
      modalityType.modalities.length > 0
        ? modalityType.modalities
        : undefined;

    return {
      table_source: "cloud_model" as const,
      source: selectedProvider?.type,
      modality: modalities,
      supported_endpoints: endpoints,
    };
  }, [
    selectedProvider?.type,
    modalityType?.modalities,
    modalityType?.endpoints,
  ]);

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      setSelectedModel(currentWorkflow.workflow_steps.model);
    }
  }, [currentWorkflow]);

  useEffect(() => {
    if (!selectedProvider?.type) {
      setModels([]);
      setHasMore(false);
      return;
    }

    pageRef.current = 1;
    setHasMore(true);

    fetchModels({
      page: 1,
      limit: PAGE_SIZE,
      ...getFilterParams(),
    }).then((data) => {
      const items = data || [];
      setModels(items);
      setHasMore(items.length >= PAGE_SIZE);
    });
  }, [
    selectedProvider?.type,
    modalityType?.modalities,
    modalityType?.endpoints,
    fetchModels,
    getFilterParams,
  ]);

  const loadMore = useCallback(() => {
    if (isLoadingMore || !hasMore || loading) return;

    setIsLoadingMore(true);
    const nextPage = pageRef.current + 1;

    fetchModels({
      page: nextPage,
      limit: PAGE_SIZE,
      ...getFilterParams(),
    })
      .then((data) => {
        const items = data || [];
        if (items.length > 0) {
          setModels((prev) => [...prev, ...items]);
          pageRef.current = nextPage;
        }
        setHasMore(items.length >= PAGE_SIZE);
      })
      .finally(() => {
        setIsLoadingMore(false);
      });
  }, [isLoadingMore, hasMore, loading, fetchModels, getFilterParams]);

  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const target = e.currentTarget;
      const { scrollTop, scrollHeight, clientHeight } = target;

      if (scrollTop <= lastScrollTop.current) {
        lastScrollTop.current = scrollTop;
        return;
      }
      lastScrollTop.current = scrollTop;

      const isNearBottom = scrollTop + clientHeight >= scrollHeight - 100;
      if (isNearBottom) {
        loadMore();
      }
    },
    [loadMore],
  );

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
      <BudWraperBox onScroll={handleScroll}>
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
            isLoadingMore={isLoadingMore}
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
