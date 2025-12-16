import { Image } from "antd";
import React from "react";

type Props = {
  type: "warning" | "failed" | "success";
};

export default function AlertIcons(props: Props) {
  return (
    <div className="width-69 height-69 ">
      {props.type == "warning" && (
        <Image
          preview={false}
          src="/images/drawer/warning.png"
          alt="info"
          width={69}
          height={69}
        />
      )}
      {props.type == "failed" && (
        <Image preview={false} src="/images/drawer/bigRed.png" alt="info" />
      )}
      {props.type == "success" && (
        <Image
          preview={false}
          src="/images/drawer/successHand.png"
          alt="info"
        />
      )}
    </div>
  );
}
