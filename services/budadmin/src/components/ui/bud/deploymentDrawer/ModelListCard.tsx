import { Checkbox, Image } from "antd";
import { ChevronRight } from "lucide-react";
import React from "react";
import { Model, useModels } from "src/hooks/useModels";
import { assetBaseUrl } from "@/components/environment";
import CustomPopover from "src/flows/components/customPopover";
import { useDrawer } from "src/hooks/useDrawer";
import IconRender from "src/flows/components/BudIconRender";

export function ModelListCard({
  selected,
  handleClick,
  data,
  hideSeeMore,
  hideSelect,
}: {
  selected?: boolean;
  handleClick?: () => void;
  data: Model;
  hideSeeMore?: boolean;
  hideSelect?: boolean;
}) {
  const {
    openDrawer,
    setPreviousStep,
    step,
    openDrawerWithStep,
    openDrawerWithExpandedStep,
    expandedStep,
  } = useDrawer();
  const { getModel } = useModels();
  const [hover, setHover] = React.useState(false);

  const { name, tags } = data;

  const imageUrl = assetBaseUrl + (data?.icon || data.uri);
  const fallbackImageUrl =
    data.provider_type === "url"
      ? "/images/drawer/url-2.png"
      : "/images/drawer/disk-2.png";

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={() => {
        if (data.is_present_in_model) return;
        handleClick?.();
      }}
      onMouseLeave={() => setHover(false)}
      className={`pt-[1.05rem] pb-[.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF08] ${data.is_present_in_model ? "opacity-30 !cursor-not-allowed" : ""}`}
    >
      <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center mr-[1.3rem] shrink-0 grow-0">
        <IconRender
          icon={data?.icon || data?.icon}
          size={26}
          imageSize={24}
          type={data.provider_type}
          model={data}
        />
      </div>
      <div className="flex justify-between flex-col w-full max-w-[85%]">
        <div className="flex items-center justify-between ">
          <div
            className="flex flex-grow max-w-[90%]"
            style={{
              width: hover || selected ? "12rem" : "90%",
            }}
          >
            <CustomPopover title={name}>
              <div className="text-[#EEEEEE] mr-2 pb-[.3em] text-[0.875rem] truncate overflow-hidden whitespace-nowrap">
                {name}
              </div>
            </CustomPopover>
          </div>
          <div
            style={{
              // Hidden temprorily
              display: (hover || selected) && !hideSelect ? "flex" : "none",
              // display: "none",
            }}
            className="justify-end items-center]"
          >
            <div
              className={`items-center text-[0.75rem] cursor-pointer text-[#757575] hover:text-[#EEEEEE] flex mr-[.6rem] whitespace-nowrap ${hideSeeMore ? "hidden" : ""}`}
              onClick={async (e) => {
                e.stopPropagation();
                if (expandedStep) return;
                const result = await getModel(data.id);
                if (result) {
                  openDrawerWithExpandedStep("view-model-details");
                }
              }}
            >
              See More <ChevronRight className="h-[1rem]" />
            </div>
            <CustomPopover
              Placement="topRight"
              title={
                data.is_present_in_model
                  ? "Already added to model repository"
                  : "Add to model repository"
              }
            >
              <Checkbox
                disabled={data.is_present_in_model}
                checked={selected}
                className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center"
              />
            </CustomPopover>
          </div>
        </div>
        <CustomPopover title={data.description}>
          <div className="text-[#757575] w-full overflow-hidden text-ellipsis text-xs line-clamp-2 leading-[150%]">
            {data.description || "-"}
          </div>
        </CustomPopover>
      </div>
    </div>
  );
}
