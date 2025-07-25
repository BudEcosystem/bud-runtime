import { Text_12_400_B3B3B3, Text_12_400_EEEEEE } from "@/components/ui/text";
import { Image } from "antd";
import Tags from "./DrawerTags";
import React from "react";

export type SpecificationTableItemProps = {
  icon?: string;
  name: string;
  value: string | string[] | number;
  full?: boolean;
  fullText?: boolean;
  secret?: boolean;
  tagColor?: string;
  children?: SpecificationTableItemProps[];
};

export function SpecificationTableItem({
  item,
  valueWidth,
  tagClass,
  benchmark = false,
}: {
  item: SpecificationTableItemProps;
  valueWidth?: number;
  tagClass?: string;
  benchmark?: boolean;
}) {
  const [show, setShow] = React.useState(false);
  const tagColor = item.tagColor || "#D1B854";
  const fullText = item.fullText ? "w-full text-left" : "truncate";
  return (
    <>
      <div
        className={`flex  items-center justify gap-[.4rem]`}
        style={{
          width: item.full ? "100%" : "48%",
          justifyContent: item.full ? "flex-start" : "",
        }}
      >
        <div
          className={`flex justify-start items-center ${
            benchmark && "min-w-[32%]"
          }`}
        >
          <div className="h-[.75rem] flex justify-start items-start">
            {item.icon && (
              <div className="!mr-[.4rem] w-[0.75rem] flex justify-start items-start">
                <Image
                  preview={false}
                  src={item.icon}
                  alt="info"
                  style={{ height: ".75rem" }}
                />
              </div>
            )}
          </div>
          <Text_12_400_B3B3B3 className="ml-[.1rem] mr-[.4rem] text-nowrap">
            {item.name}
          </Text_12_400_B3B3B3>
        </div>
        {!benchmark && <div className="flex-grow"></div>}
        {item.children?.length > 0 ? null : Array.isArray(item?.value) ? (
          <div
            className={`flex flex-row gap-[.4rem] max-w-full ${
              valueWidth ? `width-${valueWidth}` : "max-w-[50%]"
            } text-left`}
          >
            {item?.value.map((tag: string, index: number) => (
              <Tags
                key={index}
                name={tag}
                color={tagColor}
                textClass="!text-[0.625rem] leading-[150%] whitespace-break-spaces"
                classNames={`${tagClass} py-[.2rem]`}
              />
            ))}
          </div>
        ) : item.secret ? (
          <div
            className={` ${
              valueWidth
                ? `width-${valueWidth} text-left`
                : (item.fullText ? "text-left" : "text-right") + " max-w-[50%]"
            }  ${fullText} text-12 text-400 text-[#EEEEEE] flex items-center`}
          >
            <Text_12_400_EEEEEE className="truncate">
              {!show ? item.value.toString().replace(/./g, "*") : item.value}
            </Text_12_400_EEEEEE>
            {
              <Text_12_400_EEEEEE
                className="ml-[1rem] cursor-pointer"
                onClick={() => {
                  setShow(!show);
                }}
              >
                <svg
                  width="0.75rem"
                  height="0.75rem"
                  viewBox="0 0 13 12"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <g clipPath="url(#clip0_1956_3584)">
                    <path
                      d="M0.891534 1.41914L1.32596 1.01367L11.6077 10.6104L11.1738 11.0154L9.11868 9.09735C8.27945 9.42595 7.35738 9.60782 6.39001 9.60782C3.59152 9.60782 1.17284 8.08766 0.03125 5.88362C0.623887 4.73988 1.56061 3.7799 2.71569 3.1217L0.891534 1.41914ZM6.39002 9.03494C7.18355 9.03494 7.94342 8.90088 8.64555 8.6562L7.95297 8.00979C7.5085 8.29479 6.97011 8.46166 6.39006 8.46166C4.8643 8.46166 3.62783 7.3076 3.62783 5.88358C3.62783 5.34218 3.80662 4.83968 4.11248 4.42486L3.16376 3.5394C2.1362 4.09533 1.28842 4.90812 0.720907 5.8836C1.81226 7.76052 3.94175 9.03504 6.39014 9.03504L6.39002 9.03494ZM12.0592 5.8835C10.9684 4.00706 8.8384 2.73254 6.39002 2.73254C5.68137 2.73254 4.99939 2.83941 4.36155 3.03676L3.88091 2.58817C4.66037 2.31114 5.50618 2.15973 6.39011 2.15973C9.18911 2.15973 11.6073 3.67989 12.7489 5.88345C12.1889 6.96486 11.3215 7.88169 10.2523 8.53473L9.80779 8.12036C10.7495 7.56958 11.5273 6.79802 12.0592 5.8835ZM6.39002 3.30542C7.91578 3.30542 9.15225 4.45995 9.15225 5.8835C9.15225 6.35084 9.01915 6.78913 8.78611 7.1669L8.3321 6.74268C8.46418 6.48205 8.53853 6.19095 8.53853 5.88345C8.53853 4.77626 7.57675 3.87861 6.38997 3.87861C6.0605 3.87861 5.74862 3.94752 5.46989 4.07127L5.01536 3.64705C5.42015 3.42955 5.88925 3.30532 6.38992 3.30532L6.39002 3.30542ZM4.24146 5.8835C4.24146 6.99116 5.20324 7.88882 6.39002 7.88882C6.80034 7.88882 7.18355 7.78148 7.50949 7.59538L4.55582 4.83862C4.35643 5.14332 4.24146 5.501 4.24146 5.8835Z"
                      fill="#808080"
                    />
                  </g>
                  <defs>
                    <clipPath id="clip0_1956_3584">
                      <rect width="12.8571" height="12" fill="white" />
                    </clipPath>
                  </defs>
                </svg>
              </Text_12_400_EEEEEE>
            }
          </div>
        ) : (
          <div
            className={` ${
              valueWidth
                ? `width-${valueWidth} text-left`
                : (item.fullText ? "text-left" : "text-right") + " max-w-[50%]"
            }  ${fullText} text-12 text-400 text-[#EEEEEE]`}
          >
            {item.value}
          </div>
        )}
      </div>
      {item.children?.length > 0 && (
        <div className="flex flex-col gap-[.5rem] ml-[2rem]">
          {item.children.map((child, index) => (
            <SpecificationTableItem
              key={index}
              item={{ ...child, full: true, icon: null }}
              valueWidth={valueWidth}
            />
          ))}
        </div>
      )}
    </>
  );
}
