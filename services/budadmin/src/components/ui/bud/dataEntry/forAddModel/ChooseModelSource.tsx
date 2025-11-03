import { useContext, useEffect, useState } from "react";
import { Checkbox, Form, Image } from "antd";
import React from "react";
import form from "antd/es/form";
import { BudFormContext } from "../../context/BudFormContext";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import { useDeployModel } from "src/stores/useDeployModel";
import ComingSoon from "@/components/ui/comingSoon";

function ModelCard({
  selected,
  handleClick,
  data,
}: {
  selected?: boolean;
  handleClick?: () => void;
  data: any;
}) {
  const [hover, setHover] = React.useState(false);

  const { icon, name, description } = data;

  // Determine if the tab should be inactive
  const isInactive = name === "";

  return (
    <div
      onMouseEnter={() => !isInactive && setHover(true)}
      onClick={() => {
        if (!isInactive) {
          handleClick?.();
        }
      }}
      onMouseLeave={() => !isInactive && setHover(false)}
      className={`addModelSelectCard relative pt-[.6rem] pb-[.95rem] px-[1.5rem] cursor-pointer border-t-[0.5px] border-b-[0.5px] border-b-[transparent] border-t-[#1F1F1F]
        flex-row flex items-center border-box
        ${
          isInactive
            ? "cursor-not-allowed  text-[#757575]"
            : "hover:shadow-lg hover:border-y-[#757575] hover:bg-[#FFFFFF08]"
        }
        `}
      // className={`addModelSelectCard relative pt-[.6rem] pb-[.95rem] px-[1.5rem] cursor-pointer border-t-[0.5px] border-b-[0.5px] border-b-[transparent] border-t-[#1F1F1F]
      //     flex-row flex items-center border-box
      //     ${isInactive
      //     ? "cursor-not-allowed bg-[#1F1F1F] text-[#757575]"
      //     : "hover:shadow-lg hover:border-y-[#757575] hover:bg-[#FFFFFF08]"
      //   }`}
    >
      {/* {isInactive && <ComingSoon comingXpos="70%" shrink={true} scaleValue={0.7} />} */}
      <div className="bg-[#1F1F1F] rounded-[4px] w-[1.75rem] h-[1.75rem] flex justify-center items-center mr-[.8rem] grow-0 shrink-0">
        <div className="w-[0.875rem] h-[0.875rem] flex justify-center items-center">
          <Image
            preview={false}
            src={icon}
            alt="info"
            style={{ width: "0.875rem", height: "0.875rem" }}
          />
        </div>
      </div>
      <div className="flex justify-between w-full flex-col">
        <div className="flex items-center justify-between h-4">
          <div className="flex pt-[.4rem]">
            <Text_14_400_EEEEEE className="mr-2 truncate leading-[2rem]">
              {name}
            </Text_14_400_EEEEEE>
          </div>
        </div>
        <Text_12_400_757575 className="text-[#757575] w-full overflow-hidden text-ellipsis pt-[.6rem] text-xs leading-[1.3rem]">
          {description}
        </Text_12_400_757575>
      </div>
      <div
        style={{
          display: hover || selected ? "flex" : "none",
        }}
        className="justify-end items-center"
      >
        <Checkbox
          checked={selected}
          className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
          disabled={isInactive}
        />
      </div>
    </div>
  );
}

export function ChooseModelSource() {
  const { providerType, setProviderType, providerTypeList } = useDeployModel();

  return (
    <div className="addModelSelect">
      {providerTypeList.map((model, index) => (
        <ModelCard
          key={index}
          data={model}
          selected={providerType?.id === model.id}
          handleClick={() => {
            setProviderType(model.id);
          }}
        />
      ))}
    </div>
  );
}

export function ChooseModalitySource() {
  const { modalityType, setModalityType, modalityTypeList } = useDeployModel();

  return (
    <div className="addModelSelect">
      {modalityTypeList.filter((modality) => !modality.hide).map((modality, index) => (
        <ModelCard
          key={index}
          data={modality}
          selected={modalityType?.id == modality.id}
          handleClick={() => {
            setModalityType(modality.id);
          }}
        />
      ))}
    </div>
  );
}
