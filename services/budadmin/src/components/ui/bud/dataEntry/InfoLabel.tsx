import React from "react";
import { Image } from 'antd';
import CustomPopover from "src/flows/components/customPopover";

interface InfoLabelProps {
  text: string;
  classNames?: string;
  content?: any;
  required?: boolean;
}

const InfoLabel: React.FC<InfoLabelProps> = ({ text, content, required, classNames }) => {
  return (
    // <span className={`flex items-center gap-1 text-[.75rem] font-[400] text-[#EEEEEE] h-[2px] bg-[#0d0d0d] ${classNames}`}>

    <div className={`flex items-center gap-1 text-[.75rem] font-[400] text-[#EEEEEE] h-[3px] pl-[.35rem] pr-[.55rem] ${classNames}`}
      style={{
        background: '#0d0d0d'
      }}
    >
      <div className="whitespace-nowrap">{text}</div> {required && <b className="text-[#FF4D4F]">*</b>}
      {content && (
        <CustomPopover title={content}>
          <Image className="mt-[.1rem]" preview={false} src="/images/drawer/info.png" alt="info"
            style={{ width: '.75rem' }}
          />
        </CustomPopover>
      )}
    </div>
  );
}

export default InfoLabel;
