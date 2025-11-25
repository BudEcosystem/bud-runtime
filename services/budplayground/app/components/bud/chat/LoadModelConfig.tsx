import React, { useEffect } from "react";
import BlurModal from "../components/modal/BlurModal";
import SliderInput from "../components/input/SliderInput";
import LabelInput from "../components/input/LabelInput";
import { Button, Checkbox, Image } from "antd";
import { ChevronLeft } from "lucide-react";
import { useConfig } from "../../../context/ConfigContext";
import { Endpoint } from "@/app/types/deployment";

interface LoadModelConfigProps {
  data: Endpoint | null;
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  onBack: () => void;
}

function LoadModelConfig(props: LoadModelConfigProps) {
  const { assetBaseUrl } = useConfig();

  React.useEffect(() => {
    document.documentElement.scrollTop = document.documentElement.clientHeight;
    document.documentElement.scrollLeft = document.documentElement.clientWidth;
  }, []);

  return (
    <BlurModal
      width="520px"
      height="400px"
      open={props.open}
      onClose={() => props.setOpen(false)}
    >
      <div>
        <div className="p-[1.25rem] flex justify-between items-center bg-[#1E1E1E] rounded-t-[.5rem]">
          <div onClick={props.onBack}>
            <ChevronLeft className="text-[#B3B3B3] cursor-pointer" />
          </div>
          <div className="flex items-center gap-x-[.5rem]">
            <Image
              src={`${assetBaseUrl}${typeof props.data?.model === 'object' && props.data?.model?.provider?.icon}`}
              alt={props.data?.name}
                    preview={false}
                    width={".875rem"}
              height={".875rem"}
            />
            <span className="text-[#EEEEEE] text-[.875rem] font-[400] ">
              {props.data?.name}
            </span>
          </div>
          <div></div>
        </div>
      </div>
      <div>
        <div className="p-[1.25rem]">
          <SliderInput
            title="Context Length"
            description={`Model supports upto 14852 tokens`}
            defaultValue={50}
            step={1}
            min={0}
            max={100}
            value={50}
            onChange={(value) => console.log(value)}
          />
          <LabelInput
            className="mt-[1.25rem]"
            title="Evaluation Batch Size"
            placeholder="Enter evaluation batch size"
            description={`Batch size for evaluation`}
            value="gpt-2"
            onChange={(value) => console.log(value)}
          />
          <LabelInput
            className="mt-[1.25rem]"
            title="RoPe Frequency Base"
            placeholder="Enter RoPe frequency base"
            description={`RoPe frequency base`}
            value="gpt-2"
            onChange={(value) => console.log(value)}
          />
          <LabelInput
            className="mt-[1.25rem]"
            title="RoPe Frequency Scale"
            placeholder="Enter RoPe frequency scale"
            description={`RoPe frequency scale`}
            value="gpt-2"
            onChange={(value) => console.log(value)}
          />
        </div>
      </div>
      <div className="flex justify-between p-[1.25rem]">
        <div className="flex gap-x-[.5rem] items-center">
          <Checkbox />
          <span className="text-[#B3B3B3] text-[.75rem] font-[300]">
            Remember settings for{" "}
            <span className="text-[#EEEEEE]">OpenAI/ gpt-4o</span>
          </span>
        </div>
        <div>
          <Button className="mr-[1.25rem] bg-[#FF5C01]">Cancel</Button>
          <Button type="primary">Load Model</Button>
        </div>
      </div>
    </BlurModal>
  );
}

export default LoadModelConfig;
