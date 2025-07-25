import { Image, Slider, Tooltip } from "antd";
import React from "react";

interface SliderInputProps {
  title: string;
  description?: string;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  value: number;
  onChange: (value: number) => void;
}

function SliderInput(props: SliderInputProps) {
  return (
    <>
      <div className="flex flex-col items-start  px-[.5rem] py-[.375rem]">
        <div className="flex flex-row justify-start gap-[.5rem]">
          <span className="text-[#EEEEEE] text-[.75rem] font-[400]">
            {props.title}
          </span>
          <Tooltip title="Top P Sampling">
            <Image
              src="icons/info.svg"
              preview={false}
              alt="bud"
              width={".875rem"}
              height={".875rem"}
            />
          </Tooltip>
        </div>
        {props.description && (
          <div>
            <span className="text-[#757575] text-[.625rem] font-[400]">
              {props.description}
            </span>
          </div>
        )}
      </div>
      <div className="flex items-center justify-center mt-[.5rem] px-[.5rem]">
        <div className="text-[#757575] text-[.75rem] mr-1 ">{props.min}</div>
        <Slider
          className="budSlider mt-10 w-full"
          defaultValue={props.defaultValue}
          min={props.min}
          max={props.max}
          value={props.value}
          onChange={props.onChange}
          step={props.step}
          tooltip={{
            open: true,
            getPopupContainer: (trigger) =>
              (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
          }}
          styles={{
            track: {
              backgroundColor: "#965CDE",
            },
            rail: {
              backgroundColor: "#212225",
              height: 4,
            },
          }}
        />
        <div className="text-[#757575] text-[.75rem] ml-1">{props.max}</div>
      </div>
    </>
  );
}

export default SliderInput;
