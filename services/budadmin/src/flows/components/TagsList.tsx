import React from "react";
import Tags, { DropDownContent } from "./DrawerTags";
import { Image } from "antd";

export type TagListeItem = {
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
  data: TagListeItem[];
}

export default function TagsList(props: TagsListProps) {
  const { data: tags } = props;
  return tags?.map((tag, index) => (
    <Tags
      key={index}
      // key={tag.name}
      name={tag.name}
      color={tag.color}
      // classNames='mb-[.3rem]'
      textClass="text-[.625rem]"
      drop={
        tag.drop && (
          <DropDownContent
            dropMessage={{
              title: tag.name,
              description: `This is the ${tag.name} model`,
              ...tag.dropContent,
              actionLabel: "View page",
              onClick: () => {
                try {
                  // Open link in a new tab
                  window.open(tag.url, "_blank");
                } catch (error) {
                  console.error(error);
                }
              },
            }}
          />
        )
      }
      image={
        tag.icon && (
          <div className="bg-[#1F1F1F] w-[0.75rem] h-[0.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0 mr-[.25rem]">
            <Image
              preview={false}
              src={tag.icon}
              className="!w-[.75rem] !h-[.75rem]"
              style={{ width: ".75rem", height: ".75rem" }}
              alt="home"
            />
          </div>
        )
      }
    />
  ));
}
