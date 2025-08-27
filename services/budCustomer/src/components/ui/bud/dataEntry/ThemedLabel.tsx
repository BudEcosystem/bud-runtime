import React from "react";
import { Image } from "antd";
import CustomPopover from "@/flows/components/customPopover";
import { useTheme } from "@/context/themeContext";

interface ThemedLabelProps {
  text: string;
  required?: boolean;
  info?: string;
  className?: string;
}

const ThemedLabel: React.FC<ThemedLabelProps> = ({
  text,
  required,
  info,
  className = "",
}) => {
  const { effectiveTheme } = useTheme();
  const isLight = effectiveTheme === "light";

  return (
    <div
      className={`absolute -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-[.75rem] font-[300] px-1 text-nowrap ${className}`}
      style={{
        backgroundColor: isLight ? "#ffffff" : "#101010",
        color: isLight ? "#1a1a1a" : "#EEEEEE",
      }}
    >
      {text}
      {required && <span className="text-[#FF4D4F] text-[1rem]">*</span>}
      {info && (
        <CustomPopover title={info}>
          <Image
            src="/images/info.png"
            preview={false}
            alt="info"
            style={{ width: '.75rem', height: '.75rem' }}
          />
        </CustomPopover>
      )}
    </div>
  );
};

export default ThemedLabel;
