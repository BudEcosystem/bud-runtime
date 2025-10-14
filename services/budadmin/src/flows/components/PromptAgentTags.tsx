import React from "react";
import { Popover } from "antd";
import { PromptAgent } from "@/stores/usePromptsAgents";
import ProjectTags from "./ProjectTags";

type PromptAgentTagsProps = {
  promptAgent: PromptAgent;
  maxTags?: number;
  limit?: boolean;
};

function PromptAgentTags(props: PromptAgentTagsProps) {
  const [showMore, setShowMore] = React.useState(false);

  if (!props.promptAgent) return null;

  const tags = [...(props.promptAgent?.tags || [])];

  return (
    <div className="flex flex-wrap items-center gap-[.25rem]">
      {!props.limit && (
        <>
          {(props.maxTags > 0 ? tags.slice(0, props.maxTags) : tags).map((tag, idx) => (
            <ProjectTags
              key={idx}
              name={tag.name}
              color={tag.color}
              textClass="text-[.625rem]"
            />
          ))}
        </>
      )}
      {props.maxTags && tags.length > props.maxTags && (
        <Popover
          arrow={false}
          showArrow={false}
          content={
            <div className="flex flex-row flex-wrap gap-[.4rem] border-[#1F1F1F] border rounded-[6px] bg-[#1F1F1F] p-3 max-w-[350px]">
              {tags.slice(props.maxTags).map((tag, idx) => (
                <ProjectTags
                  key={idx}
                  name={tag.name}
                  color={tag.color}
                  textClass="text-[.625rem]"
                />
              ))}
            </div>
          }
        >
          <div
            onMouseEnter={() => setShowMore(!showMore)}
            onMouseLeave={() => setShowMore(!showMore)}
            className="text-[#EEEEEE] hover:text-[white] text-[0.625rem] font-[400] cursor-pointer"
          >
            {showMore
              ? "Show less"
              : `+${tags.length - props.maxTags} more`}
          </div>
        </Popover>
      )}
    </div>
  );
}

export default PromptAgentTags;
