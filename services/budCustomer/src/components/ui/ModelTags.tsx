import React, { useState } from "react";
import { Image, Popover } from "antd";
import { LinkOutlined } from "@ant-design/icons";
import Tags from "./Tags";
import TagsList, { TagListItem } from "./TagsList";

export interface Model {
  id: string;
  name: string;
  endpoints_count?: number;
  provider_type?: string;
  model_size?: string | number;
  tags?: Array<{ name: string }>;
  type?: string;
  uri?: string;
  author?: string;
  github_url?: string;
  huggingface_url?: string;
  website_url?: string;
  paper_published?: Array<{ title?: string; url?: string }>;
  model_licenses?: { name?: string; url?: string };
}

type ModelTagsProps = {
  model: Model;
  hideLink?: boolean;
  hideTags?: boolean;
  maxTags?: number;
  hideEndPoints?: boolean;
  hideType?: boolean;
  hideModality?: boolean;
  hideAuthor?: boolean;
  showExternalLink?: boolean;
  showLicense?: boolean;
  limit?: boolean;
};

function ModelTags(props: ModelTagsProps) {
  const [showMore, setShowMore] = useState(false);

  if (!props.model) return null;

  const externalLinks: TagListItem[] = [
    {
      icon: "/images/drawer/github.png",
      name: "Github",
      color: "#965CDE",
      drop: true,
      title: "Github Link",
      url: props?.model?.github_url,
      dropContent: {
        title: "Github Link",
        description: `This is the github link for the ${props.model.name} model`,
      },
    },
    {
      icon: "/images/drawer/huggingface.png",
      name: "Huggingface",
      color: "#965CDE",
      drop: true,
      title: "Huggingface Link",
      url: props?.model?.huggingface_url,
      dropContent: {
        title: "Huggingface Link",
        description: `This is the huggingface link for the ${props.model.name} model`,
      },
    },
    {
      icon: "/images/drawer/websiteLink.png",
      name: "Website Link",
      color: "#965CDE",
      drop: true,
      title: "Website Link",
      url: props?.model?.website_url,
      dropContent: {
        title: "Website Link",
        description: `This is the website link for the ${props.model.name} model`,
      },
    },
    ...(props?.model?.paper_published?.map((paper, index) => ({
      name: paper.title
        ? paper.title?.length > 20
          ? `${paper.title.slice(0, 20)}...`
          : paper.title
        : `Paper ${index + 1}`,
      color: "#EC7575",
      drop: true,
      title: paper.title,
      url: paper.url,
      dropContent: {
        title: paper.title,
        description: `This is the paper for the ${props.model.name} model`,
      },
    })) || []),
  ].filter((link) => link.url);

  const licenseLinks: TagListItem[] = [
    {
      name: props?.model?.model_licenses?.name || "License",
      color: "#D1B854",
      drop: true,
      title: props?.model?.model_licenses?.name,
      url: props?.model?.model_licenses?.url,
      dropContent: {
        title: props?.model?.model_licenses?.name,
        description: `This is the license for the ${props.model.name} model`,
      },
    },
  ].filter((link) => link.url);

  const tags: TagListItem[] = [
    ...(props.model?.tags?.map((tag) => ({
      name: tag.name,
      color: "#8E5EFF",
    })) || []),
  ];

  return (
    <div className="flex flex-wrap items-center gap-[.25rem]">
      {!props.hideEndPoints && props.model.endpoints_count !== undefined && (
        <Tags
          name={`${props.model.endpoints_count} endpoints`}
          color={"#965CDE"}
          textClass="text-[.625rem]"
          image={
            <div className="bg-bud-bg-tertiary w-3 h-3 rounded flex justify-center items-center shrink-0 mr-1">
              <Image
                preview={false}
                src={"/images/drawer/rocket.png"}
                className="!w-3 !h-3"
                style={{ width: ".75rem", height: ".75rem" }}
                alt="endpoints"
              />
            </div>
          }
        />
      )}

      {!props.hideTags && (
        <>
          {props.model?.provider_type && (
            <Tags
              name={
                props.model?.provider_type === "cloud_model" ? "Cloud" : "Local"
              }
              color={"#D1B854"}
              image={
                <div className="bg-bud-bg-tertiary w-3 h-3 rounded flex justify-center items-center shrink-0 mr-1">
                  <Image
                    preview={false}
                    src={
                      props.model?.provider_type === "cloud_model"
                        ? "/images/drawer/cloud.png"
                        : "/images/drawer/disk.png"
                    }
                    className="!w-3 !h-3"
                    style={{ width: ".75rem", height: ".75rem" }}
                    alt="provider"
                  />
                </div>
              }
              textClass="text-[.625rem]"
            />
          )}

          {props.model?.type && !props.hideType && (
            <Tags
              name={props.model?.type}
              color={"#FF5E99"}
              textClass="text-[.625rem]"
            />
          )}

          {props.model?.uri && !props.hideLink && (
            <Tags
              onTagClick={() => {
                if (props.model?.provider_type === "hugging_face") {
                  window.open(
                    "https://huggingface.co/" + props.model?.uri,
                    "_blank",
                  );
                }
              }}
              tooltipText={
                props.model?.provider_type === "hugging_face" ? "Link" : "Copy"
              }
              copyText={props.model?.uri}
              showTooltip={true}
              name={props.model?.uri}
              textClass="truncate text-[.625rem] overflow-hidden max-w-[100px]"
              color={"#8E5EFF"}
              image={
                <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
                  <LinkOutlined style={{ color: "#B3B3B3" }} />
                </div>
              }
            />
          )}

          {props?.model?.author && !props.hideAuthor && (
            <Tags
              name={props?.model?.author}
              color={"#D1B854"}
              image={
                <div className="bg-bud-bg-tertiary w-3 h-3 rounded flex justify-center items-center shrink-0 mr-1">
                  <Image
                    preview={false}
                    src={"/icons/user.png"}
                    className="!w-3 !h-3"
                    style={{ width: ".75rem", height: ".75rem" }}
                    alt="author"
                  />
                </div>
              }
              textClass="text-[.625rem]"
            />
          )}

          {!props.limit && (
            <TagsList
              data={
                props.maxTags && props.maxTags > 0
                  ? tags.slice(0, props.maxTags)
                  : tags
              }
            />
          )}

          {props.maxTags && tags.length > props.maxTags && (
            <Popover
              arrow={false}
              showArrow={false}
              content={
                <div className="flex flex-row flex-wrap gap-[.4rem] border-bud-border border rounded-[6px] bg-bud-bg-secondary p-3 max-w-[350px]">
                  <TagsList data={tags.slice(props.maxTags)} />
                </div>
              }
            >
              <div
                onMouseEnter={() => setShowMore(true)}
                onMouseLeave={() => setShowMore(false)}
                className="text-bud-text-primary hover:text-white text-[0.625rem] font-[400] cursor-pointer"
              >
                {showMore
                  ? "Show less"
                  : `+${tags.length - props.maxTags} more`}
              </div>
            </Popover>
          )}
        </>
      )}

      {props.showExternalLink && <TagsList data={externalLinks} />}
      {props.showLicense && <TagsList data={licenseLinks} />}
    </div>
  );
}

export default ModelTags;
