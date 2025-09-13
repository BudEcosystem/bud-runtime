import React, { useState } from "react";
import { Tag, Popover, Image } from "antd";
import { checkColor, getChromeColor } from "./tagHelpers";
import { LinkOutlined } from "@ant-design/icons";

export interface TagProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  name: React.ReactNode;
  color: string;
  image?: any;
  classNames?: string;
  textClass?: string;
  drop?: any;
  dropOpen?: boolean;
  onTagClick?: () => void;
  closable?: boolean;
  showTooltip?: boolean;
  tooltipText?: string;
  dropClasses?: string;
  dropPatentClasses?: string;
  copyText?: string;
  onClose?: () => void;
}

function Tags(props: TagProps) {
  const [copyText, setCopiedText] = useState<string>(
    props.tooltipText ? props.tooltipText : "Copy",
  );
  const color = checkColor(props.color) ? props.color : "#D1B854";

  const handleCopy = (text: string) => {
    if (copyText === "Copy") {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          setCopiedText("Copied..");
        })
        .catch(() => {
          setCopiedText("Failed to copy");
        });

      setTimeout(() => {
        setCopiedText("Copy");
      }, 3000);
    }
  };

  const tagContent = (
    <div className="flex justify-center items-center w-full h-full">
      {props.image && <div>{props.image}</div>}
      <div
        className={`font-[400] ${props.textClass}`}
        style={{
          color: color,
          fontSize: "0.625rem",
          lineHeight: "115%",
        }}
      >
        {props.name}
      </div>
    </div>
  );

  const tagElement = (
    <Tag
      className={`customTags ${props.closable && "closableTag"} border-[0] rounded-[6px] flex cursor-pointer hover:text-[#EEEEEE] ${props.classNames}`}
      style={{
        backgroundColor: getChromeColor(color),
        marginRight: "0",
        paddingTop: !props.image ? ".37rem" : ".3rem",
        paddingBottom: !props.image ? ".37rem" : ".3rem",
      }}
      onClick={(e) => {
        if (props?.onTagClick) {
          e.stopPropagation();
          props.onTagClick();
          if (props.copyText) {
            handleCopy(props.copyText);
          }
        }
      }}
      closable={props.closable}
      onClose={props.onClose}
    >
      {props.showTooltip ? (
        <Popover content={copyText} placement="top">
          {tagContent}
        </Popover>
      ) : (
        tagContent
      )}
    </Tag>
  );

  // If there's a dropdown, wrap with Popover
  if (props.drop) {
    return (
      <Popover
        content={props.drop}
        trigger="click"
        placement="bottomLeft"
        open={props.dropOpen}
      >
        {tagElement}
      </Popover>
    );
  }

  return tagElement;
}

export default Tags;
