import React from "react";
import { Tag } from "antd";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";

function ProjectTags(props: {
  name: string;
  color: string;
  tagClass?: string;
  textClass?: string;
}) {
  return (
    <Tag
      className={`border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] ${props.tagClass}`}
      style={{
        backgroundColor: getChromeColor(props.color),
        marginRight: "0",
        padding: "0",
      }}
    >
      <div
        className={`font-[400] leading-[100%] ${props.textClass}`}
        style={{
          fontSize: "0.625rem",
          color: props.color || "#B3B3B3",
          paddingTop: "0.375rem",
          paddingBottom: "0.375rem",
          paddingLeft: "0.375rem",
          paddingRight: "0.375rem",
        }}
      >
        {props.name}
      </div>
    </Tag>
  );
}

export default ProjectTags;
