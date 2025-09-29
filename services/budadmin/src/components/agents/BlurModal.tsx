import { Modal } from "antd";
import React, { useEffect, useState } from "react";

interface BlurModalProps {
  children: React.ReactNode;
  open: boolean;
  onClose: () => void;
  width: string;
  height: string;
  containerRef?: React.RefObject<HTMLDivElement | null>;
}

export default function BlurModal(props: BlurModalProps) {
  const [modalPosition, setModalPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    const rect = props.containerRef?.current?.getBoundingClientRect();
    if (rect) {
      setModalPosition({
        top: rect.bottom + window.scrollY - 32, // a little offset below
        left: rect.left + window.scrollX - 160,
      });
    }
  }, [props.open, props.containerRef])

  return (
    <Modal
      rootClassName=""
      open={props.open}
      classNames={{
        content: "!p-0 !bg-transparent border-0",
      }}
      closable={false}
      onCancel={props.onClose}
      footer={null}
      closeIcon={null}
      style={{
        position: 'absolute',
        width: props.width,
        height: props.height,
        top: modalPosition.top,
        left: modalPosition.left
      }}
    >
      <div className="w-full h-full bg-[#1E1E1E25] rounded-[.625rem] relative shadow-2xl">
        <div className="blur absolute top-0 left-0 w-full h-full bg-[#1E1E1E66] rounded-[.625rem] z-[-9] backdrop-filter backdrop-blur-[4px]" />
        {props.children}
      </div>
    </Modal>
  );
}
