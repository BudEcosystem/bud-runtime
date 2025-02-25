import React, { useEffect } from "react";
import BlurModal from "../components/modal/BlurModal";
import { Endpoint, useEndPoints } from "../hooks/useEndPoint";
import SliderInput from "../components/input/SliderInput";
import LabelInput from "../components/input/LabelInput";

interface LoadModelProps {
  data: Endpoint | null;
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

function LoadModelConfig(props: LoadModelProps) {
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
        </div>
      </div>
    </BlurModal>
  );
}

export default LoadModelConfig;
