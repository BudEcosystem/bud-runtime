import React from "react";
import Tags from "./Tags";
import { Image } from "antd";

export type TagListItem = {
  icon?: string;
  name: string;
  color: string;
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

export interface TagsListProps {
  data: TagListItem[];
}

export default function TagsList(props: TagsListProps) {
  const { data: tags } = props;

  return (
    <>
      {tags?.map((tag, index) => (
        <Tags
          key={index}
          name={tag.name}
          color={tag.color}
          textClass="text-[.625rem]"
          drop={
            tag.drop &&
            tag.dropContent && (
              <div className="p-4 bg-bud-bg-secondary rounded-lg max-w-xs">
                <div className="text-bud-text-primary font-medium mb-2">
                  {tag.dropContent.title || tag.name}
                </div>
                <div className="text-bud-text-muted text-xs mb-3">
                  {tag.dropContent.description}
                </div>
                {tag.url && (
                  <button
                    className="text-bud-purple text-xs hover:underline"
                    onClick={() => window.open(tag.url, "_blank")}
                  >
                    {tag.dropContent.actionLabel || "View page"}
                  </button>
                )}
              </div>
            )
          }
          image={
            tag.icon && (
              <div className="bg-bud-bg-tertiary w-3 h-3 rounded flex justify-center items-center shrink-0 mr-1">
                <Image
                  preview={false}
                  src={tag.icon}
                  className="!w-3 !h-3"
                  style={{ width: "0.75rem", height: "0.75rem" }}
                  alt="icon"
                />
              </div>
            )
          }
        />
      ))}
    </>
  );
}
