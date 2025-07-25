import { Text_12_600_EEEEEE } from "@/lib/text";
import { Button } from "antd";
import { ChevronRight } from "lucide-react";
import { ReactNode } from "react";


interface PrimaryButtonProps {
  classNames?: string;
  Children?: ReactNode; // Optional children of any type, such as text or icons
  [key: string]: any;   // Allow any other props
}
export function PrimaryButton({
  classNames = '',
  Children,
  ...props
}: PrimaryButtonProps) {
  const { disabled } = props;
  return (
    <Button
      {...props}
      className={`flex justify-center items-center h-[2.3rem] !border-[.5px] !border-[#965CDE] font-normal !bg-[#1E0C34] hover:bg-[#965CDE] ${classNames} 
      ${disabled ? '!bg-[#1E0C34] hover:!bg-[#1E0C34] border-[#965CDE] text-[#888888] cursor-not-allowed' : '!bg-[#1E0C34] hover:!bg-[#965CDE]'} `}
      disabled={disabled} // Ensures that the button is actually disabled
      style={{
        minWidth: '4rem',
        paddingLeft: '.7rem',
        paddingRight: '.7rem'
      }}
    >
      {Children}
      <Text_12_600_EEEEEE className={`leading-[100%] ${(props.children == 'Next' || props.text == 'Next') ? 'ml-[.4rem] mr-[0]' : ''}`}>{props.children || props.text || "Next"}</Text_12_600_EEEEEE>
      {(props.children == 'Next' || props.text == 'Next') && (
        <div className="ml-[-.2rem]">
          <ChevronRight className="text-[#EEEEEE] text-[.5rem] w-[1rem]" />
        </div>
      )}
    </Button>
  );
}
