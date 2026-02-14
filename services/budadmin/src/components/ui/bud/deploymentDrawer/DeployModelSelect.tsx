import React, { useState } from "react";
import { Model } from "src/hooks/useModels";
import { Text_12_300_EEEEEE, Text_12_600_EEEEEE } from "../../text";
import { ModelListCard } from "./ModelListCard";
import { Tag } from "../dataEntry/TagsInput";
import { useDrawer } from "src/hooks/useDrawer";
import { Checkbox, Spin } from "antd";

function DeployModelSelect({
  multiSelect,
  multiSelectedModels,
  setMultiSelectedModels,
  setSelecteUnselectAllModels,

  selectedModel,
  setSelectedModel,
  models,
  filteredModels,
  hideSeeMore,
  selectedTags = [],
  children,
  hideSelect,
  emptyComponent = <Text_12_300_EEEEEE className="pl-5">
    To add new models for the provider, click the &quot;+Cloud Model&quot; button
  </Text_12_300_EEEEEE>,
  isLoadingMore,
}: {
  multiSelect?: boolean;
  multiSelectedModels?: Model[];
  setMultiSelectedModels?: (value) => void;
  setSelecteUnselectAllModels?: (value: boolean) => void;

  selectedModel?: Model;
  setSelectedModel?: (value: Model) => void;
  models: Model[];
  filteredModels: Model[];
  hideSeeMore?: boolean;
  selectedTags?: Tag[];
  children: React.ReactNode;
  hideSelect?: boolean;
  emptyComponent?: React.ReactNode;
  isLoadingMore?: boolean;
}) {
  const [selectAllModels, setSelectAllModels] = useState<boolean>(false);

  const { openDrawer } = useDrawer();
  const tagsFilteredModels = filteredModels?.filter((model) => {
    if (selectedTags.length === 0) {
      return true;
    }

    return selectedTags.every((tag) =>
      model.tags?.find((modelTag) => modelTag.name === tag.name),
    );
  });

  const handleSelectAll = () => {
    setSelectAllModels(!selectAllModels);
    setSelecteUnselectAllModels(selectAllModels);
  };

  return (
    <div>
      {children}
      <div className="px-[1.4rem] pb-[.5rem] flex justify-between items-center">
        <div className="text-[#757575] text-[.75rem] font-[400]">
          Models Available{" "}
          <span className="text-[#EEEEEE]">{models?.length}</span>
        </div>
        {multiSelect && (
          <div className="flex items-center justify-start gap-[.7rem]">
            <Text_12_600_EEEEEE>Select All</Text_12_600_EEEEEE>
            <Checkbox
              checked={selectAllModels}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
              onChange={handleSelectAll}
            />
          </div>
        )}
      </div>
      <div className="">
        {tagsFilteredModels?.length > 0 ? (
          <>
            {tagsFilteredModels?.map((model, index) => (
              <div key={index}>
                {multiSelect ? (
                  <ModelListCard
                    hideSeeMore={hideSeeMore}
                    key={index}
                    selected={multiSelectedModels?.some(
                      (selected) => selected.id === model.id,
                    )}
                    data={model}
                    hideSelect={hideSelect}
                    handleClick={() => {
                      // if (selectedModel?.id === model.id) {
                      //   setSelectedModel(null);
                      //   return;
                      // }
                      // setSelectedModel(model);
                      setMultiSelectedModels(model);
                      if (hideSelect) {
                        openDrawer("view-model");
                      }
                    }}
                  />
                ) : (
                  <ModelListCard
                    hideSeeMore={hideSeeMore}
                    key={index}
                    selected={selectedModel?.id === model.id}
                    data={model}
                    hideSelect={hideSelect}
                    handleClick={() => {
                      if (selectedModel?.id === model.id) {
                        setSelectedModel(null);
                        return;
                      }
                      setSelectedModel(model);
                      if (hideSelect) {
                        openDrawer("view-model");
                      }
                    }}
                  />
                )}
              </div>
            ))}
            {isLoadingMore && (
              <div className="flex justify-center items-center py-4">
                <Spin size="small" />
              </div>
            )}
          </>
        ) : (
          <div className="flex justify-center items-center min-h-[4rem]">
            {emptyComponent}
          </div>
        )}
      </div>
    </div>
  );
}

export default DeployModelSelect;
