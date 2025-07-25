import { assetBaseUrl } from "@/components/environment";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import {
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import { Image } from "antd";
import React from "react";
import { useModels } from "src/hooks/useModels";
import Tags from "./DrawerTags";
import { successToast } from "@/components/toast";
import { LinkOutlined } from "@ant-design/icons";
import TagsList from "./TagsList";
import ModelTags from "./ModelTags";
import {
  SpecificationTableItem,
  SpecificationTableItemProps,
} from "./SpecificationTableItem";
import { SpecificationCard } from "./SpecificationCard";
import IconRender, { IconOnlyRender } from "./BudIconRender";

export default function SelectedModeInfoCard({
  specTitle,
  specifications,
}: {
  specTitle?: string;
  specifications?: SpecificationTableItemProps[];
} = {}) {
  const { selectedModel } = useModels();
  const imageUrl = assetBaseUrl + (selectedModel?.icon || selectedModel?.icon);

  return (
    <BudDrawerLayout>
      <div className="flex items-center justify-start w-full p-[1.35rem]">
        <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0">
          <IconOnlyRender
            icon={selectedModel?.icon || selectedModel?.icon}
            imageSize={26}
            type={selectedModel?.provider_type}
            model={selectedModel}
          />
        </div>
        <div>
          <Text_14_400_EEEEEE className="mb-[0.65rem]">
            {selectedModel?.name}
          </Text_14_400_EEEEEE>
          <div className="flex items-center justify-start flex-row flex-wrap gap-[0.375rem] row-gap-[0.375rem]">
            <ModelTags model={selectedModel} />
          </div>
        </div>
      </div>
      <div className="px-[1.4rem] pt-[.1rem] mb-[1.1rem]">
        <Text_12_400_B3B3B3 className="leading-[1.05rem]">
          {selectedModel?.description}
        </Text_12_400_B3B3B3>
      </div>
      {specTitle && (
        <SpecificationCard title={specTitle} specifications={specifications} />
      )}
    </BudDrawerLayout>
  );
}
