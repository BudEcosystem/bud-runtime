import React from "react";
import { Image } from "antd";
import CustomPopover from "@/flows/components/customPopover";
import { useTheme } from "@/context/themeContext";

interface InfoLabelProps {
  text: string;
  classNames?: string;
  content?: any;
  required?: boolean;
}

const InfoLabel: React.FC<InfoLabelProps> = ({
  text,
  content,
  required,
  classNames,
}) => {
  const { effectiveTheme } = useTheme();
  const isLight = effectiveTheme === "light";

  return (
    <div
      className={`flex items-center gap-1 text-[.75rem] font-[400] h-[3px] pl-[.35rem] pr-[.55rem] ${classNames}`}
      style={{
        background: isLight ? "#ffffff" : "#0d0d0d",
        color: isLight ? "#1a1a1a" : "#EEEEEE",
      }}
    >
      {text} {required && <b className="text-[#FF4D4F]">*</b>}
      {content && (
        <CustomPopover title={content}>
          <Image
            className="mt-[.1rem]"
            preview={false}
            src="/images/drawer/info.png"
            alt="info"
            style={{ width: ".75rem" }}
          />
        </CustomPopover>
      )}
    </div>
  );
};

export default InfoLabel;
