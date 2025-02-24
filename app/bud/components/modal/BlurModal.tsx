import { Modal } from "antd";
import React from "react";

interface BlurModalProps {
  children: React.ReactNode;
  open: boolean;
  onClose: () => void;
  width: string;
  height: string;
}

export default function BlurModal(props: BlurModalProps) {
  return (
    <Modal
      rootClassName="!mt-[-3.25rem]"
      open={props.open}
      onClose={props.onClose}
      classNames={{
        content: "!p-0 !bg-transparent border-0",
      }}
      footer={null}
      closeIcon={null}
      style={{
        width: props.width,
        height: props.height,
      }}
    >
      <div className="w-full h-full bg-[#1E1E1E25] rounded-[.625rem] relative shadow-2xl">
        <div className="blur  absolute top-0 left-0 w-full h-full bg-[#1E1E1E25] rounded-[.625rem] z-[-1] backdrop-filter backdrop-blur-[4px]" />
        {props.children}
      </div>
    </Modal>
  );
}
