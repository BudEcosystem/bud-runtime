import { Image, notification, Tag } from "antd";
import React from "react";
import { useConfig } from "../../../context/ConfigContext";
import { getChromeColor } from "../utils/color";
import { Endpoint } from "@/app/types/deployment";
import { toast } from "react-toastify";

type Model = {
  id: string;
  name: string;
  description: string;
  uri: string;
  tags: string[];
  provider: {
    icon: string;
  };
  is_present_in_model: boolean;
};

export function ModelListCard({
  selected,
  selectable,
  handleClick,
  data,
  hideSeeMore,
  hideSelect,
}: {
  selected?: boolean;
  selectable?: boolean;
  handleClick?: () => void;
  data: Endpoint;
  hideSeeMore?: boolean;
  hideSelect?: boolean;
}) {
  const { assetBaseUrl } = useConfig();
  const [hover, setHover] = React.useState(false);

  const { name, model } = data;

  const imageUrl =
    assetBaseUrl + (typeof data.model === 'object' && data.model ?
      (data.model.icon || (data.model.provider && data.model.provider.icon)) :
      '/icons/modelRepoWhite.png');
  const fallbackImageUrl = "/icons/modelRepoWhite.png";

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={() => {
        if(data.status === "unhealthy") {
          return toast.error("Model is unhealthy");
        }
        handleClick?.();
      }}
      onMouseLeave={() => setHover(false)}
      className={`pt-[1.05rem] pb-[.8rem] cursor-pointer
        hover:shadow-lg pl-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F]
        hover:border-[#757575] h-[80px] flex-row flex border-box
        hover:bg-[#FFFFFF08]
          items-center justify-center ${
            selectable ? (selected ? "bg-[#FFFFFF08]" : "bg-[#1F1F1F]") : ""
          }`}
    >
      <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center mr-[1rem] shrink-0 grow-0">
        <div className=" w-[1.68rem] h-[1.68rem] flex justify-center items-center shrink-0 grow-0">
          <Image
            preview={false}
            src={imageUrl}
            fallback={fallbackImageUrl}
            alt="info"
            style={{ width: "1.625rem", height: "1.625rem" }}
          />
        </div>
      </div>
      <div className="flex justify-between flex-col w-full max-w-[95%] relative">
        <div className="flex items-center gap-[.625rem] w-full">
          <div
            className="flex flex-grow max-w-[90%]"
            style={{
              width: hover || selected ? "12rem" : "90%",
            }}
          >
            {/* <CustomPopover title={name}> */}
            <div className="text-[#EEEEEE] mr-2 text-[0.875rem] truncate overflow-hidden whitespace-nowrap">
              {name}
            </div>
            {/* </CustomPopover> */}
          </div>
          <div className="justify-end items-center h-[1.5rem] flex absolute right-[1.5rem] top-[50%] transform -translate-y-1/2">
            <div
              className={`items-center text-[0.75rem] cursor-pointer text-[#757575] hover:text-[#EEEEEE] flex whitespace-nowrap`}
              onClick={async (e) => {
                e.stopPropagation();
              }}
            >
              <svg
                width="10"
                height="15"
                viewBox="0 0 10 15"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M5.29426 11.8648C5.09281 11.6759 5.0826 11.3595 5.27146 11.158L8.70087 7.5L5.27146 3.84197C5.0826 3.64052 5.09281 3.3241 5.29426 3.13523C5.49572 2.94637 5.81214 2.95658 6.001 3.15803L9.751 7.15803C9.93131 7.35036 9.93131 7.64964 9.751 7.84197L6.001 11.842C5.81214 12.0434 5.49572 12.0536 5.29426 11.8648Z"
                  fill="#B3B3B3"
                />
              </svg>
            </div>
          </div>
        </div>
        <div className="text-[#757575] w-full overflow-hidden text-ellipsis text-xs mt-[0.25rem] flex">
          {typeof model === 'object' && model?.tags.map((tag) => (
            <Tag
              key={tag.name}
              className=" !text-[.625rem] font-[400] rounded-[0.5rem] !px-[.375rem] !h-[1.25rem] flex items-center justify-center leading-[1.25rem]"
              style={{
                background: getChromeColor(tag.color || "#D1B854"),
                borderColor: getChromeColor(tag.color || "#D1B854"),
                color: tag.color || "#D1B854",
              }}
            >
              {tag.name}
            </Tag>
          ))}
        </div>
      </div>
    </div>
  );
}
