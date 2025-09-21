import React from "react";
import { Model } from "src/hooks/useModels";
import TagsList, { TagListeItem } from "./TagsList";
import Tags, { DropDownContent } from "./DrawerTags";
import { successToast } from "@/components/toast";
import { LinkOutlined } from "@ant-design/icons";
import { Image, Popover } from "antd";
import { CpuIcon } from "lucide-react";
import { assetBaseUrl } from "@/components/environment";

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
  const [showMore, setShowMore] = React.useState(false);
  if (!props.model) return null;
  const externalLinks = [
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
      // url: `${assetBaseUrl}${paper.url}`
      url: paper.url,
      dropContent: {
        title: paper.title,
        description: `This is the paper for the ${props.model.name} model`,
      },
    })) || []),
  ]?.filter((link) => link.url);
  const licenseLinks = [
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
  ];
  const tags: TagListeItem[] = [...(props.model?.tags || [])];

  return (
    <div className="flex flex-wrap items-center gap-[.25rem]">
      {!props.hideEndPoints && (
        <Tags
          name={props.model.endpoints_count || 0}
          color={"#965CDE"}
          textClass="text-[.625rem]"
          image={
            <div className="bg-[#1F1F1F] w-[0.75rem] h-[0.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0 mr-[.25rem]">
              <Image
                preview={false}
                src={"/images/drawer/rocket.png"}
                className="!w-[.75rem] !h-[.75rem]"
                style={{ width: ".75rem", height: ".75rem" }}
                alt="home"
              />
            </div>
          }
        />
      )}
      {props.hideTags ? null : (
        <>
          {props.model?.provider_type && (
            <Tags
              name={
                props.model?.provider_type === "cloud_model" ? "Cloud" : "Local"
              }
              color={"#D1B854"}
              image={
                <div className="bg-[#1F1F1F] w-[0.75rem] h-[0.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0 mr-[.25rem]">
                  <Image
                    preview={false}
                    src={
                      props.model?.provider_type === "cloud_model"
                        ? "/images/drawer/cloud.png"
                        : "/images/drawer/disk.png"
                    }
                    className="!w-[.75rem] !h-[.75rem]"
                    style={{ width: ".75rem", height: ".75rem" }}
                    alt="home"
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
                // copy to clipboard
                // navigator.clipboard.writeText(props.model?.uri);
                // successToast("Copied to clipboard");
                if (props.model?.provider_type == "hugging_face") {
                  window.open(
                    "https://huggingface.co/" + props.model?.uri,
                    "_blank",
                  );
                } else {
                  // navigator.clipboard.writeText(props.model?.uri);
                  // successToast("Copied to clipboard");
                }
              }}
              tooltipText={
                props.model?.provider_type == "hugging_face" ? "Link" : "Copy"
              }
              copyText={props.model?.uri}
              showTooltip={true}
              name={props.model?.uri}
              textClass="truncate text-[.625rem] overflow-hidden max-w-[100px]"
              color={"#8E5EFF"}
              image={
                <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
                  <LinkOutlined
                    style={{
                      color: "#B3B3B3",
                    }}
                  />
                </div>
              }
            />
          )}

          {/* {props.model?.modality && !props.hideModality && <Tags
                key={'modality'}
                name={props.model.modality}
                color={'#D1B854'}
                image={
                    (
                        <div className="bg-[#1F1F1F] w-[0.75rem] h-[0.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0 mr-[.25rem]">
                            <CpuIcon size={16} color='#B3B3B3' />
                        </div>
                    )
                }
            />} */}
          {props?.model?.author && !props.hideAuthor && (
            <Tags
              name={props?.model?.author}
              color={"#D1B854"}
              image={
                <div className="bg-[#1F1F1F] w-[0.75rem] h-[0.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0 mr-[.25rem]">
                  <Image
                    preview={false}
                    src={"/icons/user.png"}
                    className="!w-[.75rem] !h-[.75rem]"
                    style={{ width: ".75rem", height: ".75rem" }}
                    alt="home"
                  />
                </div>
              }
              textClass="text-[.625rem]"
            />
          )}
          {!props.limit && (
            <TagsList
              data={props.maxTags > 0 ? tags.slice(0, props.maxTags) : tags}
            />
          )}
          {props.maxTags && tags.length > props.maxTags && (
            <Popover
              arrow={false}
              showArrow={false}
              content={
                <div className="flex flex-row flex-wrap gap-[.4rem] border-[#1F1F1F] border rounded-[6px] bg-[#1F1F1F] p-3 max-w-[350px]">
                  <TagsList data={tags.slice(props.maxTags)} />
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
        </>
      )}
      {props.showExternalLink && <TagsList data={externalLinks} />}
      {props.showLicense && <TagsList data={licenseLinks} />}
    </div>
  );
}

export default ModelTags;
