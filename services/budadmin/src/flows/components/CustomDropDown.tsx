import { Button, ConfigProvider, Dropdown } from "antd";
import React, { useEffect, useState } from "react";

interface CustomDropDownProps {
  isDisabled?: boolean
  children?: React.ReactNode;
  buttonContent?: any;
  classNames?: any;
  parentClassNames?: any;
  items?: any;
  Placement?: string;
  menuItemColor? : string,
  text? : string,
}

const CustomDropDown: React.FC<CustomDropDownProps> = ({
  isDisabled,
  children,
  items = [], 
  classNames,
  parentClassNames,
  buttonContent,
  text,
  Placement = "bottomRight", // Default to 'bottomRight'
  menuItemColor = "#FFFFFF",
}) => {
  const [placement, setPlacement] = useState<any>(Placement);

  useEffect(() => {
    setPlacement(Placement || "bottomRight");
  }, [Placement]);

  const customStyles = `
    .custom-dropdown-menu .ant-dropdown-menu-item {
      color: ${menuItemColor} !important;
      background: #161616;
    }
  `;
  return (
    <div className={`CustomDropDown relative z-[5000] ${parentClassNames}`}
      style={{
        width: '100%'
      }}
    >
       <style>{customStyles}</style>
      <ConfigProvider 
      theme={{ token: {}, components: { Dropdown: {} } }}
      >
        <Dropdown
        // open={text=='test10'}
          onOpenChange={(value)=> {
            // console.log('value', value)
          }}
          disabled={isDisabled}
          menu={{ items, className: "custom-dropdown-menu" }}
          placement={placement}
          className={classNames}
          getPopupContainer={trigger => (trigger.parentNode as HTMLElement) || document.body}
        >
          <Button className="text-[#EEEEEE]">{buttonContent}</Button>
        </Dropdown>
      </ConfigProvider>
    </div>
  );
};

export default CustomDropDown;
