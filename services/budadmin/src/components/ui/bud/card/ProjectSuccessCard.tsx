import React from "react";

import { Image } from "antd";
import {
  Text_24_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_300_EEEEEE,
} from "../../text";
import { PrimaryButton } from "../form/Buttons";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

const ProjectSuccessCard = (props: { text?: string }) => {
  const { openDrawerWithStep } = useDrawer();
  const { reset } = useDeployModel();

  return (
    <div className="flex flex-col	justify-start items-center p-[2.5rem]">
      <div className="align-center">
        <Image
          preview={false}
          src="/images/successHand.png"
          alt="info"
          width={140}
          height={129}
        />
      </div>
      <div className="max-w-[80%] mt-[1rem] mb-[3rem] flex flex-col items-center justify-center">
        <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[70%]">
          {props.text}
        </Text_24_600_EEEEEE>
        <Text_12_400_B3B3B3 className="text-center">
          Ready to deploy models to this project? Let’s get started!
        </Text_12_400_B3B3B3>
      </div>
      <PrimaryButton
        onClick={() => {
          reset();
          openDrawerWithStep("deploy-model");
        }}
      >
        <div className="flex items-center justify-center gap">
          <Image
            preview={false}
            src="/images/deployRocket.png"
            alt="info"
            width={12}
            height={12}
          />
          <Text_12_300_EEEEEE className="ml-[.3rem]">
            Deploy Model
          </Text_12_300_EEEEEE>
        </div>
      </PrimaryButton>
    </div>
  );
};

export default ProjectSuccessCard;
