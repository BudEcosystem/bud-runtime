/**
 * ModelPickerPanel - Expanded side drawer for selecting a model.
 *
 * Opened from ConfigureDeployment when the user clicks a deploy_model
 * component field. Shows a searchable list of models filtered by capability.
 * Uses the same ModelListCard component as the deploy model flow.
 *
 * Props are passed via `expandedDrawerProps` (useDrawer store):
 *   - componentName: string
 *   - modelCapability?: string
 *   - onSelect: (model: Model) => void
 */

import React, { useCallback, useEffect, useState } from "react";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_10_400_B3B3B3 } from "@/components/ui/text";
import { ModelListCard } from "@/components/ui/bud/deploymentDrawer/ModelListCard";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useModels, Model } from "src/hooks/useModels";
import { useDrawer } from "src/hooks/useDrawer";

// ---------------------------------------------------------------------------
// ModelPickerPanel
// ---------------------------------------------------------------------------

type ModelPickerProps = {
  componentName: string;
  displayName?: string;
  modelCapability?: string;
  selectedModelId?: string;
  onSelect: (model: Model) => void;
};

export default function ModelPickerPanel() {
  const { expandedDrawerProps, closeExpandedStep } = useDrawer();
  const props = expandedDrawerProps as ModelPickerProps | null;

  const { fetchModels, loading } = useModels();
  const [search, setSearch] = useState("");
  const [allModels, setAllModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);

  const componentName = props?.componentName || "";
  const modelCapability = props?.modelCapability;
  const displayName = props?.displayName || componentName;
  const selectedModelId = props?.selectedModelId;

  const loadModels = useCallback(async () => {
    const params: any = {
      page: 1,
      limit: 1000,
      table_source: "model" as const,
      exclude_adapters: true,
    };
    const results = await fetchModels(params);
    if (results) setAllModels(results);
  }, [fetchModels]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  // Client-side filtering by search text and capability
  const filteredModels = allModels.filter((model) => {
    // Filter by capability if specified
    if (modelCapability) {
      const endpoint = (model.supported_endpoints as any)?.[modelCapability];
      if (!endpoint?.enabled) return false;
    }
    // Filter by search text
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      model.name?.toLowerCase().includes(q) ||
      model.tags?.some((tag: any) =>
        tag?.name?.toLowerCase().includes(q),
      ) ||
      `${model.model_size}`.includes(q)
    );
  });

  const handleSelect = (model: Model) => {
    setSelectedModel(model);
    props?.onSelect(model);
    closeExpandedStep();
  };

  return (
    <BudForm data={{}} onBack={() => closeExpandedStep()} backText="Cancel">
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={displayName}
            description={
              modelCapability
                ? `Select a model with ${modelCapability} capability`
                : "Select a model for this component"
            }
          />
          <div className="px-[1.4rem] py-[1.8rem] pb-[.5rem]">
            <SearchHeaderInput
              placeholder="Model names, Tags, Tasks, Parameter sizes"
              searchValue={search}
              expanded
              setSearchValue={setSearch}
              classNames="border border-[.5px] border-[#757575]"
            />
          </div>
          <div className="px-[1.4rem] pb-[.5rem] flex justify-between items-center">
            <div className="text-[#757575] text-[.75rem] font-[400]">
              Models Available{" "}
              <span className="text-[#EEEEEE]">{filteredModels.length}</span>
            </div>
          </div>
          <div>
            {loading && allModels.length === 0 ? (
              <div className="py-8 text-center">
                <Text_10_400_B3B3B3>Loading models...</Text_10_400_B3B3B3>
              </div>
            ) : filteredModels.length > 0 ? (
              filteredModels.map((model: Model) => (
                <ModelListCard
                  key={model.id}
                  data={model}
                  selected={
                    selectedModel?.id === model.id ||
                    selectedModelId === model.id
                  }
                  hideSeeMore
                  handleClick={() => handleSelect(model)}
                />
              ))
            ) : (
              <div className="flex justify-center items-center min-h-[4rem]">
                <Text_10_400_B3B3B3>
                  {search
                    ? `No models found for "${search}"`
                    : "No models available."}
                </Text_10_400_B3B3B3>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
