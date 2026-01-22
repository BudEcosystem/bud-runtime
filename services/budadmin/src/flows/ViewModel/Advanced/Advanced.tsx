import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React from "react";
import { Image } from "antd"; // Added Checkbox import
import { Model, useModels } from "src/hooks/useModels";

import Tags from "src/flows/components/DrawerTags";
import Link from "next/link";
import {
  SpecificationTableItem,
  SpecificationTableItemProps,
} from "src/flows/components/SpecificationTableItem";
import {
  capitalize,
  getCommaSeparated,
  getFormattedToBillions,
  getInGB,
} from "@/lib/utils";
import { useDrawer } from "src/hooks/useDrawer";

export type BranchType = {
  name: string;
  value: string;
  color: string;
  key: string;
};

function Branch({ data }: { data: BranchType }) {
  const { openDrawerWithExpandedStep } = useDrawer();
  const { selectedModel } = useModels();

  const onTagClick = () => {
    openDrawerWithExpandedStep("derived-model-list", {
      selectedBranch: data,
      model: selectedModel,
    });
  };

  return (
    <div
      className="treeDiv flex h-[28px] w-full items-center justify-between gap-1.5"
      onClick={() => {
        if (data.value !== "0 models") onTagClick();
      }}
    >
      <div className="relative h-[28px] w-[19px] flex-none">
        <div className="TreeLine left absolute inset-y-0 -top-[3px] left-0  w-px bg-[#757575] dark:bg-[#757575]"></div>
        <svg
          className="text-[#757575] dark:text-[#757575]"
          width="19"
          height="28"
          viewBox="0 0 19 28"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            fillRule="evenodd"
            clipRule="evenodd"
            d="M1 0C1 7.42391 7.4588 13.5 15.5 13.5V14.5C6.9726 14.5 0 8.04006 0 0H1Z"
            fill="currentColor"
          ></path>
        </svg>
      </div>
      <Text_12_400_B3B3B3>{data.name}</Text_12_400_B3B3B3>
      <div className="mx-[.1rem] flex-1 translate-y-[2.5px] self-center border-b border-solid dark:border-gray-800"></div>
      <Link
        className="inline-block text-left min-w-[75px] text-gray-700 underline decoration-gray-300 hover:text-gray-900 hover:decoration-gray-600 dark:text-gray-300 dark:decoration-gray-500 dark:hover:text-gray-100 dark:hover:decoration-gray-200"
        href=""
      >
        <Text_12_400_B3B3B3 className="hover:text-[#FFFFFF]">
          {data.value}
        </Text_12_400_B3B3B3>
      </Link>
    </div>
  );
}
interface GeneralProps {
  data?: Model;
}

const Advanced: React.FC<GeneralProps> = ({ data }) => {
  // Dynamic array text and vision config

  const treeData: BranchType[] = [
    {
      name: "Adapters",
      value: `${data?.adapters_count} models`,
      color: "#B3B3B3",
      key: "adapter",
    },
    {
      name: "Finetunes",
      value: `${data?.finetunes_count} models`,
      color: "#B3B3B3",
      key: "finetune",
    },
    {
      name: "Merges",
      value: `${data?.merges_count} models`,
      color: "#B3B3B3",
      key: "merge",
    },
    {
      name: "Quantizations",
      value: `${data?.quantizations_count} models`,
      color: "#B3B3B3",
      key: "quantized",
    },
  ];

  let architectureArrayAdditional: SpecificationTableItemProps[] = [
    {
      name: "Model Size",
      value: data.model_size
        ? [`${getFormattedToBillions(data.model_size)}`]
        : "",
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Architecture",
      value: data.model_type ? [capitalize(`${data.model_type}`)] : "",
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Model Type",
      value: data.family ? [capitalize(`${data.family}`)] : "",
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Modality",
      // value: "",
      value: data.modality ? [`${data.modality}`.toUpperCase()] : "",
      full: true,
      icon: "/images/drawer/tag.png",
      children: Object.entries(data.modality || {})
        .filter(([_, value]) => value.input || value.output)
        .map(([key, value], index) => ({
          name: `#${index + 1} ${value.label}`,
          value: [value.input && "Input", value.output && "Output"],
          full: true,
          icon: "/images/drawer/tag.png",
          children: [],
        })),
    },
    data.base_model?.length > 0 && {
      name: "Base Models",
      value: data.base_model ? data.base_model : "",
      full: true,
      icon: "/images/drawer/tag.png",
      children: data.base_model?.map((item, index) => ({
        name: `#${index + 1} Model`,
        value: [item],
        full: true,
        icon: "/images/drawer/tag.png",
        children: [],
      })),
    },
    {
      name: "Model Weights Size",
      value: data.model_weights_size
        ? [`${getInGB(data.model_weights_size)}`]
        : "",
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
  ];

  const filterEmpty = (item) =>
    Array.isArray(item.value) ? item.value.length > 0 : item.value !== "";

  function mapDynamicArray([key, value]): SpecificationTableItemProps {
    const formattedName = key
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
    let tag: string[] | string = [];
    let children: any = [];
    if (typeof value === "object" && value) {
      if (Array.isArray(value)) {
        tag = [value.join(", ")];
      } else {
        children = Object.entries(value)
          .map(mapDynamicArray)
          ?.filter(filterEmpty);
        tag = "CHILDREN";
      }
    } else {
      if (typeof value === "string") {
        tag = [value];
      } else if (typeof value === "number") {
        // comma separated number
        const commaSeparated = getCommaSeparated(value);
        tag = [commaSeparated];
      }
    }
    return {
      name: formattedName,
      value: tag,
      full: true,
      icon: "/images/drawer/tag.png",
      children,
    };
  }

  const architectureArray = Object.entries(data?.architecture_text_config || {})
    .map(mapDynamicArray)
    ?.filter(filterEmpty);

  const architectureVisionArray = Object.entries(
    data?.architecture_vision_config || {},
  )
    .map(mapDynamicArray)
    ?.filter(filterEmpty);

  const architectureAudioArray = Object.entries(
    data?.architecture_audio_config || {},
  )
    .map(mapDynamicArray)
    ?.filter(filterEmpty);

  return (
    <div className="pt-[.45rem]">
      <div>
        {/* Technical Specifications Section */}
        <div>
          <Text_14_400_EEEEEE>Techinical Specifications</Text_14_400_EEEEEE>
          {architectureArrayAdditional.length > 0 ? (
            <Text_12_400_757575 className="mt-[.55rem]">
              Below are the techinical specifications of the selected model
            </Text_12_400_757575>
          ) : (
            <Text_12_400_757575 className="mt-[.55rem]">
              Techinical specifications not available
            </Text_12_400_757575>
          )}
        </div>
        <div className="mt-[.8rem] flex flex-col gap-y-[1.15rem] mb-[1.1rem]">
          {[...architectureArrayAdditional]
            .filter(
              (item) =>
                Array.isArray(item.value) &&
                item.value.length > 0 &&
                item.value.some(Boolean),
            )
            .map((item, index) => (
              <SpecificationTableItem key={index} item={item} />
            ))}
        </div>
        <div>
          <Text_14_400_EEEEEE>
            Text Architecture Specifications
          </Text_14_400_EEEEEE>
          {architectureArray.length > 0 ? (
            <Text_12_400_757575 className="mt-[.55rem]">
              Below are the text architecture specifications of the selected
              model
            </Text_12_400_757575>
          ) : (
            <Text_12_400_757575 className="mt-[.55rem]">
              Techinical specifications not available
            </Text_12_400_757575>
          )}
        </div>
        <div className="mt-[.8rem] flex flex-col gap-y-[1.15rem] mb-[1.1rem]">
          {architectureArray
            .filter(
              (item) =>
                Array.isArray(item.value) &&
                item.value.length > 0 &&
                item.value.some(Boolean),
            )
            .map((item, index) => (
              <SpecificationTableItem key={index} item={item} />
            ))}
        </div>
        {architectureVisionArray.length > 0 && (
          <>
            <div>
              <Text_14_400_EEEEEE>
                Vision Architecture Specifications
              </Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.55rem]">
                Below are the techinical specifications of the selected model
              </Text_12_400_757575>
            </div>
            <div className="mt-[.8rem] flex flex-col gap-y-[1.15rem] mb-[1.1rem]">
              {architectureVisionArray
                .filter(
                  (item) =>
                    Array.isArray(item.value) &&
                    item.value.length > 0 &&
                    item.value.some(Boolean),
                )
                .map((item, index) => (
                  <SpecificationTableItem key={index} item={item} />
                ))}
            </div>
            <div className="hR"></div>
          </>
        )}
        {architectureAudioArray.length > 0 && (
          <>
            <div>
              <Text_14_400_EEEEEE>
                Audio Architecture Specifications
              </Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.55rem]">
                Below are the audio architecture specifications of the selected
                model
              </Text_12_400_757575>
            </div>
            <div className="mt-[.8rem] flex flex-col gap-y-[1.15rem] mb-[1.1rem]">
              {architectureAudioArray
                .filter(
                  (item) =>
                    Array.isArray(item.value) &&
                    item.value.length > 0 &&
                    item.value.some(Boolean),
                )
                .map((item, index) => (
                  <SpecificationTableItem key={index} item={item} />
                ))}
            </div>
            <div className="hR"></div>
          </>
        )}

        {/* Model Tree Section */}
        <div className="mt-[1.4rem]">
          <Text_14_400_EEEEEE>Model Tree</Text_14_400_EEEEEE>
          <Text_12_400_757575 className="mt-[.55rem]">
            A model tree is a hierarchical visualization of new models derived
            from a base model
          </Text_12_400_757575>
        </div>
        <div className="flex flex-col justify-center space-y-0 mt-[1.15rem] mb-[1.15rem] w-[58.8%]">
          {treeData.map((item, index) => (
            <Branch key={index} data={item} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default Advanced;
