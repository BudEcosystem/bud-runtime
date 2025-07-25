import React, { forwardRef, useEffect, useState } from "react";
import { Tag, Dropdown, Image, MenuProps } from "antd";
import { checkColor, getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { Text_12_400_B3B3B3, Text_12_400_EEEEEE, Text_12_600_EEEEEE, Text_14_400_EEEEEE, Text_16_600_FFFFFF, Text_18_600_EEEEEE } from "@/components/ui/text";
import { ChevronRight } from "lucide-react";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useDrawer } from "src/hooks/useDrawer";
import CustomPopover from "./customPopover";
import FileViewer from "@/components/ui/FileViewer";

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  name: React.ReactNode;
  color: string;
  image?: any;
  classNames?: string;
  textClass?: string
  drop?: any
  dropOpen?: boolean
  onTagClick?: () => void;
  closable?: boolean;
  showTooltip?: boolean;
  tooltipText?: string;
  dropClasses?: string;
  dropPatentClasses?: string;
  copyText?: string;
  onClose?: () => void;
}


export interface MessageTopProps {
  classNames?: any;
  title?: string;
  description?: string;
  actionLabel?: string;
  showAll?: boolean;
  clickDisabled?: boolean;
  onClick?: () => void;
}


export interface MessageContentProps {
  show?: boolean;
  data?: any;
  file?: any;
  messageContentclassNames?: any;
  showAll?: boolean;
}
export const MessageContent = forwardRef<HTMLDivElement, MessageContentProps>((props, ref) => {
  const [showAll, setShowAll] = useState(props.showAll ? props.showAll : false);
  const [expandAll, setExpandAll] = useState(false);
  const [openDetail, setOpenDetail] = useState<number | null>(null);
  const displayData = showAll ? props.data : props.data.slice(0, 2);
  const { openDrawerWithExpandedStep } = useDrawer();

  useEffect(() => {
    console.log('data', props.data)
    console.log('data', props.file)

  }, [props.data])
  return (
    <div className={`MessageContent ${props.messageContentclassNames}`}
      style={{
        zIndex: 100,
      }}
    >
      <div className={`${showAll ? 'pl-[0]' : 'px-[1.4rem]'} `}>
        {/* <Text_14_400_EEEEEE>Get the Answers You’re Looking For</Text_14_400_EEEEEE> */}
        {showAll && (
          <div className="flex justify-end">
            <div className="flex justify-end items-center cursor-pointer max-w-[100px] gap-[.35rem] mt-[.2rem]"
              onClick={() => setExpandAll(!expandAll)}
            >
              <Text_12_400_EEEEEE className="leading-[1.2rem]">{expandAll ? 'Collapse All' : 'Expand All'}</Text_12_400_EEEEEE>
              <div className="w-[0.9375rem] h-[0.9375rem] "
              >
                <Image
                  preview={false}
                  width={15}
                  src="/images/drawer/ChevronUp.png"
                  alt="Logo"
                  style={{ transform: !expandAll ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.3s ease' }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className={`pt-[1.2rem] ${showAll ? 'pl-[0]' : 'px-[1.4rem]'}`}>
        {displayData.map((item, index) => (
          <div key={index} className={`flex flex-col justify-end items-end px-[0.9rem] py-[1rem] mb-[.9rem] rounded-[8px] gap-[.5rem] ${showAll ? 'bg-[#FFFFFF08]' : 'bg-[#161616]'}`}>
            <div key={index} className="flex justify-between items-start gap-[.5rem] w-full">
              <div className="mt-[0rem] w-[2rem]">
                <Image
                  preview={false}
                  className=""
                  src={item.answer == 'YES' ? '/images/drawer/greenTick.png' : '/images/drawer/redCross.png'}
                  alt="Logo"
                  style={{ width: '1.5rem' }}
                />
              </div>
              <div className="flex flex-auto justify-between items-center gap-[.8rem] max-w-[90%]">
                <Text_12_600_EEEEEE className="!leading-[160%] max-w-[90%]">{item.question}</Text_12_600_EEEEEE>
                {showAll && (
                  <div className="flex justify-end items-start"
                    onClick={() => setOpenDetail((prev) => (prev === index ? null : index))}
                  >
                    <div className="w-[0.9375rem] h-[0.9375rem] "
                    >
                      <Image
                        preview={false}
                        width={15}
                        src="/images/drawer/ChevronUp.png"
                        alt="Logo"
                        style={{
                          transform: expandAll || openDetail === index ? 'rotate(0deg)' : 'rotate(180deg)',
                          transition: 'transform 0.3s ease',
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div
              className={`w-full overflow-hidden transition-all duration-300 ease-in-out ${expandAll || openDetail === index
                ? 'max-h-[500px] opacity-100 overflow-y-auto'
                : 'max-h-0 opacity-0'
                }`}
            >
              <div className="flex justify-start items-center gap-[.5rem] w-full pl-[2.7rem]">
                {/* <div className="mt-[.3rem] w-[2rem]">
                  <div className="w-[1.9rem]"></div>
                </div> */}
                <div className="text-left flex flex-auto  w-full">
                  <Text_12_400_B3B3B3 className="leading-[1.05rem] w-full">{item.description}</Text_12_400_B3B3B3>
                </div>
              </div>
            </div>
          </div>
        ))}
        {props.file?.data_type != "url" && (
          <div ref={ref}>
            {showAll && (
              <>
                <div className="hR mt-[1.3rem]"></div>
                <Text_18_600_EEEEEE className="pt-[1.5rem] pb-[1rem]">License</Text_18_600_EEEEEE>
              </>
            )}
            {showAll && (
              <>
                {props.file?.url ? (
                  <div className="w-full h-[65vh]">
                    <FileViewer fileUrl={props.file?.url} />
                  </div>
                ) : (
                  <Text_12_400_B3B3B3>No file available</Text_12_400_B3B3B3>
                )}
              </>
            )}
          </div>
        )}

      </div>
      {!showAll && (
        <div className="flex justify-end pr-[1rem] pb-[.5rem]">
          <div className="flex justify-start items-center cursor-pointer duration-[500ms] hover:scale-[1.06]"
            onClick={async (e) => {
              e.stopPropagation();
              openDrawerWithExpandedStep("license-Details")
            }}
          >
            <Text_12_400_EEEEEE>See More</Text_12_400_EEEEEE>
            <ChevronRight className="text-[.75rem] w-[.9rem] text-[#EEEEEE]" />
          </div>
        </div>
      )}
    </div>
  );
});
MessageContent.displayName = "MessageContent";

export function MessageTop({ classNames,
  actionLabel,
  title,
  description,
  onClick,
  showAll,
  clickDisabled
}: MessageTopProps) {
  const [showall, setShowAll] = useState(showAll ? showAll : false);
  return (
    <div className={`MessageTop rounded-[6px] pb-[1.25rem] ${classNames}`}
      style={{
        width: '100%',
        // width: '359px',
        background: '#1F1F1F'
      }}
    >
      {(title || description) && (
        <div className="border-b-[1px] border-b-[#757575] px-[1.4rem] py-[1.3rem] pb-[1.2rem] mb-[1.25rem]">
          <Text_14_400_EEEEEE className="leading-[1.24375rem]">{title}</Text_14_400_EEEEEE>
          <Text_12_400_B3B3B3 className="pt-[1rem] leading-[180%]">{description}</Text_12_400_B3B3B3>
        </div>
      )}
      {/* <div className="border-b-[1px] border-b-[#757575] px-[1.5rem] py-[1.3rem] pb-[1.2rem] mb-[1.25rem]">
          <Text_14_400_EEEEEE className="leading-[1.24375rem]">{title}</Text_14_400_EEEEEE>
          <Text_12_400_B3B3B3 className="pt-[0.7rem]">{description}</Text_12_400_B3B3B3>
        </div> */}
      {onClick && <div className={showAll ? 'pl-[0]' : 'pl-[1.4rem]'}>
        <PrimaryButton className="!border-[.5px]"
          disabled={clickDisabled}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onClick();
          }}
          classNames="px-[1rem]"
          Children={
            <div className="w-[0.65rem]">
              <Image
                preview={false}
                className=""
                src="/images/drawer/notes.png"
                alt="Logo"
                style={{ width: '0.65rem' }}
              />
            </div>
          }
        >
          {actionLabel}
        </PrimaryButton>
      </div>}
    </div>
  );
}

export function DropDownContent({
  dropMessage,
  contentmessage,
  classNames
}: {
  dropMessage?: MessageTopProps,
  contentmessage?: MessageContentProps,
  classNames?: string,
}) {
  // return <div className={`w-[359px] bg-[#1F1F1F] rounded-[6px] z-[1500] relative`}>
  return <div className={`w-[100%] bg-[#1F1F1F] rounded-[6px] relative ${classNames}`}
    style={{
      zIndex: 1500,
    }}
  >
    {dropMessage && (
      <MessageTop {
        ...dropMessage
      } />
    )}
    {contentmessage?.show && (
      <MessageContent
        {...contentmessage}
      />
    )}
  </div>
}

function Tags(props: BudInputProps) {
  const [copyText, setCopiedText] = useState<string>(props.tooltipText ? props.tooltipText : 'Copy');
  const items: MenuProps['items'] = [
    {
      key: '1',
      label: (
        props.drop
      ),
    }
  ];

  const color = checkColor(props.color) ? props.color : '#D1B854';

  const handleCopy = (text: string) => {
    if (copyText == 'Copy') {
      navigator.clipboard.writeText(text)
        .then(() => {
          // message.success('Text copied to clipboard!');
          setCopiedText("Copied..");
        })
        .catch(() => {
          // message.error('Failed to copy text.');
          setCopiedText("Failed to copy");
        });

      setTimeout(() => {
        setCopiedText(copyText);
      }, 3000)
    }
  };


  return (
    <>
      {props.drop ? (
        <div className={`tagDropDown mt-[.2rem] ${props.dropPatentClasses}`} >
          <Dropdown menu={{ items }} placement="bottomLeft"
            getPopupContainer={trigger => (trigger.parentNode as HTMLElement) || document.body}
            // open
            open={props.dropOpen}
            className={`tagDropDownDrop ${props.dropClasses}`}
          >
            <Tag
              onClose={props.onClose}
              className={`customTags ${props.closable && 'closableTag'} relative border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center  ${props.classNames}`}
              style={{
                backgroundColor: getChromeColor(color),
                marginRight: '0',
                paddingTop: !props.image ? '.37rem' : '.3rem',
                paddingBottom: !props.image ? '.37rem' : '.3rem',
              }}
              closable={props.closable}
            >
              {props.image && (
                <div>
                  {props.image}
                </div>
              )}
              <div className={`font-[400] leading-[100%] ${props.textClass}`}
                style={{
                  color: color,
                  fontSize: '0.625rem'
                }}
              >
                {props.name}
              </div>
              <div className="absolute flex justify-center items-center bottom-[.15rem] right-[0.15rem] w-[0.3rem] h-[0.3rem]">
                <Image
                  preview={false}
                  style={{ width: '0.3rem', height: '0.3rem' }}
                  src="/images/drawer/drop.png"
                  alt="Logo"
                />
              </div>
            </Tag>
          </Dropdown>
        </div>
      ) : (

        <Tag
          className={`customTags ${props.closable && 'closableTag'} border-[0] rounded-[6px] flex cursor-pointer hover:text-[#EEEEEE] ${props.classNames}`}
          style={{
            backgroundColor: getChromeColor(color),
            marginRight: '0',
            paddingTop: !props.image ? '.37rem' : '.3rem',
            paddingBottom: !props.image ? '.37rem' : '.3rem',
          }}
          onClick={(e) => {
            if (props?.onTagClick) {
              e.stopPropagation();
              props.onTagClick();
              handleCopy(props.copyText)
            }
          }}
          closable={props.closable}
          onClose={props.onClose}
        >
          {props.showTooltip ? (
            <CustomPopover title={copyText} contentClassNames="flex justify-center items-center w-full h-full" customClassName="flex justify-center items-center w-full h-full">
              <div className="flex justify-center items-center w-full h-full">
                {props.image && (
                  <div>
                    {props.image}
                  </div>
                )}
                <div className={`font-[400] leading-[115%] ${props.textClass}`}
                  style={{
                    color: color,
                    fontSize: '0.625rem'
                  }}
                >
                  {props.name}
                </div>
              </div>
            </CustomPopover>
          ) : (
            <div className="flex justify-center items-center w-full h-full">
              {props.image && (
                <div>
                  {props.image}
                </div>
              )}
              <div className={`font-[400] ${props.textClass}`}
                style={{
                  color: color,
                  fontSize: '0.625rem',
                  lineHeight: '115%'
                }}
              >
                {props.name}
              </div>
            </div>
          )}

        </Tag>
      )}
    </>
  );
}

export default Tags;
