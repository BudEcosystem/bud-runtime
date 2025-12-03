import React from "react";
import Tags, { DropDownContent } from "./DrawerTags";
import { Popover } from "antd";

export type GeneralTagItem = {
  name: string;
  color?: string;
  drop?: boolean;
  title?: React.ReactNode;
  url?: string;
  dropContent?: {
    title?: string;
    description?: string;
    actionLabel?: string;
    onClick?: () => void;
  };
};

export interface GeneralTagsProps {
  data: GeneralTagItem[];
  limit?: number;
  defaultColor?: string;
  textClass?: string;
  classNames?: string;
}

export default function GeneralTags(props: GeneralTagsProps) {
  const {
    data: tags,
    limit,
    defaultColor = "#1F1F1F",
    textClass = "text-[.625rem]",
    classNames,
  } = props;
  const [showMore, setShowMore] = React.useState(false);

  if (!tags || tags.length === 0) return null;

  const visibleTags = limit && limit > 0 ? tags.slice(0, limit) : tags;
  const hiddenTags = limit && limit > 0 ? tags.slice(limit) : [];
  const hasMoreTags = hiddenTags.length > 0;

  const renderTag = (tag: GeneralTagItem, index: number) => (
    <Tags
      key={index}
      name={tag.name}
      color={tag.color || defaultColor}
      classNames={classNames}
      textClass={textClass}
      drop={
        tag.drop && (
          <DropDownContent
            dropMessage={{
              title: tag.name,
              description: `This is the ${tag.name} tag`,
              ...tag.dropContent,
              actionLabel: tag.dropContent?.actionLabel || "View page",
              onClick:
                tag.dropContent?.onClick ||
                (() => {
                  try {
                    if (tag.url) {
                      window.open(tag.url, "_blank", "noopener,noreferrer");
                    }
                  } catch (error) {
                    console.error(error);
                  }
                }),
            }}
          />
        )
      }
    />
  );

  return (
    <div className="flex flex-wrap items-center gap-[.25rem]">
      {visibleTags.map((tag, index) => renderTag(tag, index))}
      {hasMoreTags && (
        <Popover
          arrow={false}
          showArrow={false}
          trigger="hover"
          content={
            <div className="flex flex-row flex-wrap gap-[.4rem] border-[#1F1F1F] border rounded-[6px] bg-[#1F1F1F] p-3 max-w-[350px]">
              {hiddenTags.map((tag, index) => renderTag(tag, index))}
            </div>
          }
          onOpenChange={(open) => setShowMore(open)}
        >
          <div className="text-[#EEEEEE] hover:text-[white] text-[0.625rem] font-[400] cursor-pointer">
            {showMore ? "Show less" : `+${hiddenTags.length} more`}
          </div>
        </Popover>
      )}
    </div>
  );
}
