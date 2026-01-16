import { Button, ConfigProvider } from "antd";
import {
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
} from "../../text";
import { ChevronRight } from "lucide-react";
import { ReactNode } from "react";
import CustomPopover from "src/flows/components/customPopover";

interface PrimaryButtonProps {
  classNames?: string;
  textClass?: string;
  permission?: boolean;
  Children?: ReactNode; // Optional children of any type, such as text or icons
  textStyle?: React.CSSProperties;
  [key: string]: any; // Allow any other props
}

export function PrimaryButton({
  classNames = "",
  textClass,
  permission = true,
  Children,
  ...props
}: PrimaryButtonProps) {
  const { disabled } = props;
  return (
    <>
      {!permission ? (
        <CustomPopover
          title="You don't have permission for this action"
          contentClassNames="bg-[#161616]"
          customClassName="Darker w-auto"
        >
          <div className="relative inline-block">
          <Button
              {...props}
              className={`pointer-events-none opacity-60 flex justify-center items-center !border-[.5px] font-normal ${classNames}`}
              disabled={true} // keep enabled so events can bubble
              style={{
                minWidth: "4rem",
                paddingLeft: "0.7rem",
                paddingRight: "0.7rem",
                cursor: "not-allowed",
                borderRadius: "0.3rem",
                height: "1.75rem",
                borderColor: "#965CDE",
                background: "#1E0C34 !important",
                ...(props.style || {}),
              }}
            >
              {Children}
              <div
                className={`${textClass} ${props.children == "Next" || props.text == "Next" ? "ml-[.4rem] mr-[0]" : ""}`}
                style={{
                  fontSize: "0.75rem",
                  color: "#EEEEEE",
                  fontWeight: 600,
                  lineHeight: "100%",
                  background: "transparent",
                  ...(props.textStyle || {}),
                }}
              >
                {props.children || props.text || "Next"}
              </div>
              {(props.children == "Next" || props.text == "Next") && (
                <div className="ml-[-.2rem]">
                  <ChevronRight className="text-[#EEEEEE] text-[.5rem] w-[1rem]" />
                </div>
              )}
            </Button>
          </div>
        </CustomPopover>
      ) : (
        <Button
          {...props}
          className={`flex justify-center items-center !border-[.5px] font-normal hover:bg-[#965CDE] ${classNames}
      ${disabled ? "!bg-[#1E0C34] hover:!bg-[#1E0C34] border-[#965CDE] text-[#888888] cursor-not-allowed" : "!bg-[#1E0C34] hover:!bg-[#965CDE]"} `}
          disabled={disabled} // Ensures that the button is actually disabled
          style={{
            minWidth: "4rem",
            paddingLeft: ".7rem",
            paddingRight: ".7rem",
            borderRadius: "0.3rem",
            height: "1.75rem",
            borderColor: "#965CDE",
            background: "#1E0C34",
            ...(props.style || {}),
          }}
        >
          {!permission ? (
            <CustomPopover
              title="You don't have permision for this action"
              contentClassNames="flex justify-center items-center w-full h-full bg-[#161616]"
              customClassName="flex justify-center items-center w-full h-full Darker"
            >
              <div className="flex justify-center items-center w-full h-full">
                {Children}
                <div
                  className={`${textClass} ${props.children == "Next" || props.text == "Next" ? "ml-[.4rem] mr-[0]" : ""}`}
                  style={{
                    fontSize: "0.75rem",
                    color: "#EEEEEE",
                    fontWeight: 600,
                    lineHeight: "100%",
                    background: "transparent",
                    ...(props.textStyle || {}),
                  }}
                >
                  {props.children || props.text || "Next"}
                </div>
                {(props.children == "Next" || props.text == "Next") && (
                  <div className="ml-[-.2rem]">
                    <ChevronRight className="text-[#EEEEEE] text-[.5rem] w-[1rem]" />
                  </div>
                )}
              </div>
            </CustomPopover>
          ) : (
            <div className="flex justify-center items-center w-full h-full">
              {Children}
              <div
                className={`${textClass} ${props.children == "Next" || props.text == "Next" ? "ml-[.4rem] mr-[0]" : ""}`}
                style={{
                  fontSize: "0.75rem",
                  color: "#EEEEEE",
                  fontWeight: 600,
                  lineHeight: "100%",
                  background: "transparent",
                  ...(props.textStyle || {}),
                }}
              >
                {props.children || props.text || "Next"}
              </div>
              {(props.children == "Next" || props.text == "Next") && (
                <div className="ml-[-.2rem]">
                  <ChevronRight className="text-[#EEEEEE] text-[.5rem] w-[1rem]" />
                </div>
              )}
            </div>
          )}
        </Button>
      )}
    </>
  );
}

export function SecondaryButton({ classNames = "", ...props }: any) {
  return (
    <Button
      {...props}
      className={`text-[0.75rem]
    hover:bg-[#1F1F1F] hover:border-[#B3B3B3] ${classNames}
    ${props.text == "Skip" && "hover:bg-[#38260B] hover:border-[#896814]"}
    ${props.text == "Close" && "hover:bg-[#290E0E] hover:border-[#6F0E0E]"}
    ${props.disabled ? "bg-[#1F1F1F]  text-[#757575]! cursor-not-allowed" : "bg-[#1F1F1F] "}
    `}
    style={{
      height: '1.75rem',
      border: '0.5px solid',
      borderColor: '#757575',
      borderRadius: '0.3rem',
      minWidth: '4rem',
      paddingLeft: '0.7rem',
      paddingRight: '0.7rem',
      background: '#1F1F1F',
      transform: 'none'
    }}
    >
      <Text_12_400_EEEEEE
        className={`${props.disabled ? "!text-[#757575] font-600" : "text-[#EEEEEE]"}`}
      >
        {props.children || props.text || "Back"}{" "}
      </Text_12_400_EEEEEE>
    </Button>
  );
}
export function BorderlessButton({ classNames = "", ...props }: any) {
  return (
    <Button
      {...props}
      className={`text-[0.75rem] h-[1.75rem] border-[.5px] border-[transparent] min-w-[4rem] font-normal bg-[#1F1F1F]
    hover:bg-[#1F1F1F] hover:border-[#B3B3B3] ${classNames}
    ${props.text == "Skip" && "hover:bg-[#38260B] hover:border-[#896814]"}
    ${props.text == "Close" && "hover:bg-[#290E0E] hover:border-[#6F0E0E]"}
    ${props.disabled ? "bg-[#1F1F1F]  text-[#757575]! cursor-not-allowed" : "bg-[#1F1F1F] "}
    `}
    >
      <Text_12_400_EEEEEE
        className={`${props.disabled ? "!text-[#757575] font-600" : "text-[#EEEEEE]"}`}
      >
        {props.children || props.text || "Back"}{" "}
      </Text_12_400_EEEEEE>
    </Button>
  );
}
