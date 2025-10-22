import { Text_12_600_EEEEEE } from "@/lib/text";
import { Button } from "antd";
import { ChevronRight } from "lucide-react";
import { ReactNode, useState } from "react";


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
  const [isHovered, setIsHovered] = useState(false);

  return (
    <Button
      {...props}
      onMouseEnter={() => !disabled && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`flex justify-center items-center !border-[.5px] font-normal ${classNames}
      ${disabled ? 'border-[#965CDE] text-[#888888] cursor-not-allowed' : ''} `}
      disabled={disabled} // Ensures that the button is actually disabled
      style={{
        minWidth: '4rem',
        paddingLeft: '.7rem',
        paddingRight: '.7rem',
        height: '2.3rem',
        background: disabled ? '#1E0C34' : (isHovered ? '#965CDE' : '#1E0C34'),
        borderColor: '#965CDE',

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
