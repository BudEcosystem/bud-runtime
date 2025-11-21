import { ConfigProvider, Popover } from "antd";
import React from "react";
import { TooltipPlacement } from "antd/es/tooltip";

interface CustomPopoverProps {
  children?: React.ReactNode;
  classNames?: string;
  contentClassNames?: string;
  titleClassName?: string;
  title?: string;
  Placement?: TooltipPlacement;
}

const CustomPopover: React.FC<CustomPopoverProps> = ({
  children,
  title,
  classNames,
  contentClassNames,
  titleClassName,
  Placement = "top"
}) => {
  return (
    <div className={`antPopoverArrow ${classNames}`} style={{ width: '100%' }}>
      <ConfigProvider
        theme={{
          components: {
            Popover: {
              borderRadiusLG: 10,
            },
          },
        }}
      >
        <Popover
          placement={Placement}
          showArrow
          content={
            <div
              className={`flex items-center gap-[.8rem] bg-[#1F1F1F] backdropBlur rounded-[6px] border-[#1F1F1F] ${contentClassNames}`}
              style={{ padding: '.5rem' }}
            >
              <div className={`text-[#EEEEEE] text-[.75rem] font-400 ${titleClassName}`}>
                {title}
              </div>
            </div>
          }
          getPopupContainer={(trigger) =>
            (trigger.parentNode as HTMLElement) || document.body
          }
          overlayStyle={{
            maxWidth: "25rem",
            zIndex: 9999,
          }}
        >
          {children}
        </Popover>
      </ConfigProvider>
    </div>
  );
};

export default CustomPopover;
