import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import React, { useEffect, useCallback } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useEndPoints } from "src/hooks/useEndPoint";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { useEvaluations } from "src/hooks/useEvaluations";
import { successToast, errorToast } from "@/components/toast";
import { Text_12_300_EEEEEE } from "@/components/ui/text";

export default function SelectModelForNewEvaluation() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(10);
  const [allEndpoints, setAllEndpoints] = React.useState([]);
  const [hasMore, setHasMore] = React.useState(true);
  const [isLoadingMore, setIsLoadingMore] = React.useState(false);

  const { loading, getEndPoints, endPoints, endPointsCount } = useEndPoints();
  const [search, setSearch] = React.useState("");
  const { openDrawerWithStep } = useDrawer();
  const { setSelectedModel, selectedModel } = usePerfomanceBenchmark();
  const { createWorkflow, currentWorkflow } = useEvaluations();

  // Initial load only - runs once on mount
  useEffect(() => {
    getEndPoints({
      page: 1,
      limit,
      name: undefined,
      order_by: "created_at",
      status: "running",
    });
  }, []); // Empty dependency array = runs once on mount

  // Fetch next page when page number changes (skip page 1 as it's handled above)
  useEffect(() => {
    if (page === 1) return; // Skip page 1, it's already loaded on mount

    const fetchNextPage = async () => {
      setIsLoadingMore(true);
      getEndPoints({
        page,
        limit,
        name: search || undefined,
        order_by: "created_at",
        status: "running",
      });
      setIsLoadingMore(false);
    };

    fetchNextPage();
  }, [page]);

  // Update local state when endpoints are fetched
  useEffect(() => {
    if (endPoints) {
      let newAllEndpoints: any[];
      // For pagination: append new data or replace based on page
      if (page === 1) {
        newAllEndpoints = endPoints;
        setAllEndpoints(endPoints);
      } else {
        newAllEndpoints = [...allEndpoints, ...endPoints];
        setAllEndpoints(newAllEndpoints);
      }

      // Check if there are more pages
      const hasMoreData =
        endPoints.length === limit && newAllEndpoints.length < endPointsCount;

      console.log('HasMore Debug:', {
        endPointsLength: endPoints.length,
        limit,
        totalEndpoints: newAllEndpoints.length,
        endPointsCount,
        hasMoreData
      });

      setHasMore(hasMoreData);
    }
  }, [endPoints, limit, endPointsCount]);

  // Handle search - debounced
  useEffect(() => {
    // Don't trigger on initial render (when search is empty)
    // if (page === 1 && allEndpoints.length === 0) {
    //   return;
    // }

    const delayDebounce = setTimeout(() => {
      setPage(1);
      setAllEndpoints([]);
      getEndPoints({
        page: 1,
        limit,
        name: search || undefined,
        order_by: "created_at",
        status: "running",
      });
    }, 500);

    return () => clearTimeout(delayDebounce);
  }, [search]);

  // Handle scroll to load more
  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const target = e.currentTarget;
      const scrollTop = target.scrollTop;
      const scrollHeight = target.scrollHeight;
      const clientHeight = target.clientHeight;

      // Calculate if we're near the bottom (within 100px)
      const isNearBottom = scrollTop + clientHeight >= scrollHeight - 100;

      console.log('Scroll Debug:', {
        scrollTop,
        scrollHeight,
        clientHeight,
        isNearBottom,
        hasMore,
        loading,
        isLoadingMore,
        currentPage: page,
        endpointsCount: allEndpoints.length
      });

      if (isNearBottom && hasMore && !loading && !isLoadingMore) {
        console.log('Loading next page...');
        setPage((prev) => prev + 1);
      }
    },
    [hasMore, loading, isLoadingMore, page, allEndpoints.length]
  );

  // Map endpoints to model format for compatibility with DeployModelSelect
  const mappedModels = allEndpoints?.map((endpoint) => ({
    id: endpoint.id,
    name: endpoint.name,
    status: endpoint.status,
    created_at: endpoint.created_at,
    model: endpoint.model,
    cluster: endpoint.cluster,
    description: endpoint.model.description,
    // Add other fields that might be needed by DeployModelSelect
    tags: endpoint.model?.tags || [],
    model_size: endpoint.model?.model_size || "",
  })) as any;

  const filteredModels = mappedModels || [];

  return (
    <BudForm
      data={{}}
      disableNext={!selectedModel?.id}
      backText="Back"
      onNext={async () => {
        try {
          // Check if we have the required data
          if (!selectedModel?.id) {
            errorToast("Please select a deployment");
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

          // Prepare payload for step 2 with endpoint_id
          const payload = {
            step_number: 2,
            workflow_id: currentWorkflow.workflow_id,
            stage_data: {
              endpoint_id: selectedModel.id,
            },
          };

          // Call the API
          await createWorkflow(experimentId, payload);

          // Navigate to next step
          openDrawerWithStep("select-traits");
        } catch (error) {
          console.error("Failed to update evaluation workflow:", error);
          errorToast("Failed to select deployment");
        }
      }}
      nextText="Next"
    >
      <BudWraperBox onScroll={handleScroll}>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Model Zoo"
            description="Select a deployment from the zoo to evaluate its performance and capabilities"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DeployModelSelect
            models={mappedModels}
            filteredModels={filteredModels}
            setSelectedModel={setSelectedModel}
            selectedModel={selectedModel}
            hideSeeMore
            emptyComponent={
              loading || isLoadingMore ? (
                <div className="flex justify-center items-center py-4">
                  <span className="text-[#757575] text-sm">Loading...</span>
                </div>
              ) : (
                <Text_12_300_EEEEEE className="pl-5">
                  No deployments found. Please add and deploy a model to evaluate.
                </Text_12_300_EEEEEE>
              )}
          >
            <ModelFilter search={search} setSearch={setSearch} />
          </DeployModelSelect>
          {isLoadingMore && (
            <div className="flex justify-center items-center py-4">
              <span className="text-[#757575] text-sm">Loading more...</span>
            </div>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
