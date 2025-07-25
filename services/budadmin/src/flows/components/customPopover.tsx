import { ConfigProvider, Popover, PopoverProps } from "antd";
import React from "react";
import { TooltipPlacement } from "antd/es/tooltip";

interface CustomPopoverProps extends Omit<PopoverProps, 'content' | 'title' | 'children' | 'classNames'> {
  children?: React.ReactNode;
  customClassName?: string;
  contentClassNames?: string;
  titleClassName?: string;
  title?: string;
  Placement?: TooltipPlacement;
}


const CustomPopover: React.FC<CustomPopoverProps> = ({ children, title, customClassName, contentClassNames, titleClassName,  Placement="top", ...rest}) => {
  return (
    <div className={`antPopoverArrow ${customClassName ?? ''}`}
    style={{width: '100%'}}
    >
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
          // open = {open}
          content={
            <div className={`flex items-center gap-[.8rem] backdropBlur rounded-[6px] border-[#1F1F1F] ${contentClassNames}`}
            style={{
              padding: '.5rem',
              backgroundColor: '#1F1F1F',
            }}
            >
              <div className={`text-[#b3b3b3] text-[.75rem] font-400 ${titleClassName}`}>{title}</div>
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
