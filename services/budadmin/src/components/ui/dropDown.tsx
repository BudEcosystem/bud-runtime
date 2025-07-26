import React, { useContext } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Box, Button, Flex } from "@radix-ui/themes";
import { Text_12_300_EEEEEE, Text_12_400_FFFFFF } from "./text";
import CustomPopover from "src/flows/components/customPopover";
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
  const handleSelect = (value) => {
    onSelect(value);
  };
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className={`outline-none ${triggerClassNames}`}>
        {/* <Button variant="soft" className='bg-transparent border-0 outline-none p-[0rem] h-[100%] w-[100%]'>
        </Button> */}
        <Flex
          align="center"
          justify="start"
          className="bg-transparent border-0 outline-none p-[0rem] h-[100%] w-[100%]"
        >
          {triggerRenderItem}
        </Flex>
      </DropdownMenu.Trigger>
      <DropdownMenu.Content
        className={`min-w-[140px] rounded rounded-lg bg-[#111113] p-[.5rem] border border-[#212225] ${contentClassNames}`}
        side="bottom"
        align={align || "start"}
      >
        {contentRenderItem ? (
          <>
            {contentRenderItem.map((item, index) => (
              <DropdownMenu.Item
                className={`h-[1.75] px-[1rem] py-[.5rem] rounded rounded-md hover:bg-[#18191B] outline-none cursor-pointer ${itemsClassNames}`}
                key={index}
                onSelect={() => handleSelect(item.props.children)}
              >
                {item}
              </DropdownMenu.Item>
            ))}
          </>
        ) : (
          <>
            {items.map((item, index) => (
              <DropdownMenu.Item
                className={`h-[1.75] px-[1rem] py-[.5rem] rounded rounded-md hover:bg-[#18191B] outline-none cursor-pointer ${itemsClassNames}`}
                key={index}
                onSelect={() => handleSelect(item)}
              >
                <Text_12_400_FFFFFF>{item}</Text_12_400_FFFFFF>
              </DropdownMenu.Item>
            ))}
          </>
        )}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
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
  onSelect?: any;
  onChange?: any;
  rules?: any[];
  formItemClassnames?: string;
}

export const BudDropdownMenu = (props: BudDropdownMenuProps) => {

  const { values, form } = useContext(BudFormContext);

  // Component that receives value and onChange from Form.Item
  const FormItemSelect = ({ value, onChange, ...restProps }: any) => {
    return (
      <div className="floating-textarea">
        <FloatLabel
          label={<InfoLabel
            text={props.label} content={props.infoText || props.placeholder} />}
          value={value}>
          <div className="custom-select-two w-full rounded-[6px] relative">
            <ConfigProvider
              theme={{
                token: {
                  colorTextPlaceholder: '#808080'
                },
              }}
            >
              <Select
                value={value}
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
                onChange={(newValue) => {
                  // Call Form.Item's onChange
                  onChange?.(newValue);
                  // Call custom onChange if provided
                  props.onChange?.(newValue);
                }}
              />
            </ConfigProvider>
          </div>
        </FloatLabel>
      </div>
    );
  };

  return (
    <Form.Item name={props.name} rules={props.rules}  hasFeedback className={`${props.formItemClassnames}`}>
      <FormItemSelect />
    </Form.Item>
  )
};
