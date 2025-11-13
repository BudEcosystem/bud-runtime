import React from "react";
import { Model } from "@/hooks/useModels";
import Tags from "./DrawerTags";
import { LinkOutlined } from "@ant-design/icons";
import { Image, Popover } from "antd";
import { successToast, errorToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";

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

  const tags = [...(props.model?.tags || [])];

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
              onTagClick={async () => {
                if (props.model?.provider_type == "hugging_face") {
                  window.open(
                    "https://huggingface.co/" + props.model?.uri,
                    "_blank",
                  );
                } else {
                  await copyToClipboard(props.model?.uri, {
                    onSuccess: () => successToast("Copied to clipboard"),
                    onError: () => errorToast("Failed to copy to clipboard"),
                  });
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

          {!props.limit &&
            props.maxTags &&
            props.maxTags > 0 &&
            tags
              .slice(0, props.maxTags)
              .map((tag, index) => (
                <Tags
                  key={index}
                  name={tag.name}
                  color={tag.color || "#1F1F1F"}
                  textClass="text-[.625rem]"
                />
              ))}

          {!props.limit &&
            !props.maxTags &&
            tags.map((tag, index) => (
              <Tags
                key={index}
                name={tag.name}
                color={tag.color || "#1F1F1F"}
                textClass="text-[.625rem]"
              />
            ))}

          {props.maxTags &&
            props.maxTags > 0 &&
            tags.length > props.maxTags && (
              <Popover
                arrow={false}
                showArrow={false}
                content={
                  <div className="flex flex-row flex-wrap gap-[.4rem] border-[#1F1F1F] border rounded-[6px] bg-[#1F1F1F] p-3 max-w-[350px]">
                    {tags.slice(props.maxTags).map((tag, index) => (
                      <Tags
                        key={index}
                        name={tag.name}
                        color={tag.color || "#1F1F1F"}
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
        </>
      )}
    </div>
  );
}

export default ModelTags;
