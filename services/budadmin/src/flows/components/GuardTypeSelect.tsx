import React from "react";
import { ConfigProvider, Select, Tag } from "antd";
import { Text_12_400_EEEEEE } from "@/components/ui/text";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";

// Guard type options with their designated colors
const GUARD_TYPE_OPTIONS = [
  { label: "Input", value: "input" },
  { label: "Output", value: "output" },
  { label: "Agents", value: "agents" },
  { label: "Retrieval", value: "retrieval" },
];

// Color mapping for each guard type
const GUARD_TYPE_COLORS: Record<string, string> = {
  input: "#4077E6", // Blue - represents incoming data/requests
  output: "#479D5F", // Green - represents successful responses
  agents: "#965CDE", // Purple - represents AI/autonomous entities
  retrieval: "#ECAE75", // Orange - represents data fetching/search
};

export interface GuardTypeSelectProps {
  value?: string[];
  onChange?: (values: string[]) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  className?: string;
}

function GuardTypeSelect({
  value = [],
  onChange,
  placeholder = "Select guard types",
  label = "Guard type",
  disabled = false,
  className = "",
}: GuardTypeSelectProps) {
  const handleChange = (selectedValues: string[]) => {
    if (onChange) {
      onChange(selectedValues);
    }
  };

  // Custom tag render for colored tags
  const tagRender = (props: any) => {
    const { label, value: tagValue, closable, onClose } = props;
    const color = GUARD_TYPE_COLORS[tagValue] || "#D1B854";

    const onPreventMouseDown = (event: React.MouseEvent<HTMLSpanElement>) => {
      event.preventDefault();
      event.stopPropagation();
    };

    return (
      <Tag
        color={color}
        onMouseDown={onPreventMouseDown}
        closable={closable}
        onClose={onClose}
        style={{
          marginRight: 4,
          marginTop: 2,
          marginBottom: 2,
          backgroundColor: getChromeColor(color),
          color: color,
          border: `1px solid ${getChromeColor(color)}`,
          borderRadius: 6,
          padding: "2px 8px",
          fontSize: "0.75rem",
          fontWeight: 500,
        }}
        closeIcon={
          <span style={{ color: color, marginLeft: 4 }}>×</span>
        }
      >
        {label}
      </Tag>
    );
  };

  return (
    <div
      className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0] hover:bg-[#FFFFFF08] ${className}`}
    >
      {label && (
        <div className="w-full">
          <Text_12_400_EEEEEE className="absolute px-[.2rem] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap floatingLabel">
            {label}
          </Text_12_400_EEEEEE>
        </div>
      )}
      <div className="custom-select-two w-full rounded-[6px] relative ">
        <ConfigProvider
          theme={{
            token: {
              colorTextPlaceholder: "#808080",
              colorBgElevated: "#101010",
            },
          }}
        >
          <Select
            mode="multiple"
            value={value}
            onChange={handleChange}
            placeholder={placeholder}
            options={GUARD_TYPE_OPTIONS}
            disabled={disabled}
            size="large"
            tagRender={tagRender}
            maxTagCount="responsive"
            className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
            style={{
              backgroundColor: "transparent",
              color: "#EEEEEE",
              border: "0.5px solid #757575",
              width: "100%",
              paddingTop: ".3rem",
              paddingBottom: ".26rem",
              fontSize: ".75rem",
            }}
            suffixIcon={
              <img
                src="/icons/customArrow.png"
                alt="dropdown"
                style={{ width: "10px", height: "7px" }}
              />
            }
            classNames={{ popup: { root: "guard-type-dropdown" } }}
          />
        </ConfigProvider>
      </div>
    </div>
  );
}

export default GuardTypeSelect;
