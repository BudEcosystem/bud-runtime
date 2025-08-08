import React, { useContext, useState, useRef, useEffect } from "react";
import { Text_12_300_EEEEEE, Text_12_400_FFFFFF } from "./text";
import CustomPopover from "@/flows/components/customPopover";
import { ConfigProvider, Select, Image, Form } from "antd";
import FloatLabel from "./bud/dataEntry/FloatLabel";
import InfoLabel from "./bud/dataEntry/InfoLabel";
import { BudFormContext } from "./bud/context/BudFormContext";

interface DropDownProps {
  items?: any;
  onSelect: any;
  triggerClassNames?: any;
  contentClassNames?: any;
  itemsClassNames?: any;
  triggerRenderItem?: React.ReactNode;
  contentRenderItem?: any;
  align?: any;
}

const CustomDropdownMenu: React.FC<DropDownProps> = ({
  items,
  onSelect,
  triggerClassNames,
  contentClassNames,
  itemsClassNames,
  triggerRenderItem,
  contentRenderItem,
  align,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const handleSelect = (value: any) => {
    onSelect(value);
    setIsOpen(false);
  };

  const getAlignmentClass = () => {
    switch (align) {
      case 'end': return 'right-0';
      case 'center': return 'left-1/2 transform -translate-x-1/2';
      default: return 'left-0';
    }
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <div
        className={`outline-none ${triggerClassNames}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center justify-start bg-transparent border-0 outline-none p-[0rem] h-[100%] w-[100%] cursor-pointer">
          {triggerRenderItem}
        </div>
      </div>

      {isOpen && (
        <div className={`absolute top-full mt-1 min-w-[140px] rounded-lg bg-[#111113] p-[.5rem] border border-[#212225] z-50 ${getAlignmentClass()} ${contentClassNames}`}>
          {contentRenderItem ? (
            <>
              {contentRenderItem.map((item: any, index: number) => (
                <div
                  className={`h-[1.75rem] px-[1rem] py-[.5rem] rounded-md hover:bg-[#18191B] outline-none cursor-pointer ${itemsClassNames}`}
                  key={index}
                  onClick={() => handleSelect(item.props.children)}
                >
                  {item}
                </div>
              ))}
            </>
          ) : (
            <>
              {items.map((item: any, index: number) => (
                <div
                  className={`h-[1.75rem] px-[1rem] py-[.5rem] rounded-md hover:bg-[#18191B] outline-none cursor-pointer ${itemsClassNames}`}
                  key={index}
                  onClick={() => handleSelect(item)}
                >
                  <Text_12_400_FFFFFF>{item}</Text_12_400_FFFFFF>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default CustomDropdownMenu;


interface BudDropdownMenuProps {
  name: string;
  label: string;
  value?: string;
  placeholder?: string;
  disabled?: boolean;
  infoText?: string;
  items: any[];
  defaultValue?: any;
  onSelect?: any;
  onChange?: any;
  rules?: any[];
  formItemClassnames?: string;
}

export const BudDropdownMenu = (props: BudDropdownMenuProps) => {

  const { values, form } = useContext(BudFormContext);

  return (
    <Form.Item name={props.name} rules={props.rules}  hasFeedback className={`${props.formItemClassnames}`}>
      <div className="floating-textarea">
        <FloatLabel
        value={values?.[props.name] || props.value}
        label={<InfoLabel
          text={props.label} content={props.infoText || props.placeholder} />}>
      <div className="custom-select-two w-full rounded-[6px] relative">
        <ConfigProvider
        theme={{
            token: {
            colorTextPlaceholder: '#808080'
            },
        }}
        >
        <Select
            placeholder={props.placeholder}
            style={{
            backgroundColor: "transparent",
            color: "#EEEEEE",
            border: "0.5px solid #757575",
            }}
            popupClassName="!mt-[1.5rem]"
            size="large"
            className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
            options={props.items}
            defaultValue={props.defaultValue}
            onChange={(value) => {
            form.setFieldsValue({ [props.name]: value });
            form.validateFields([props.name]);
            props.onChange && props.onChange(value);
            }}
        />
        </ConfigProvider>
    </div>
    </FloatLabel>
    </div>
  </Form.Item>
  )
};
