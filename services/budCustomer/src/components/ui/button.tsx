import { ReactNode } from "react";

interface PrimaryButtonProps {
  classNames?: string;
  textClass?: string;
  permission?: boolean;
  Children?: ReactNode;
  onClick?: (e?: React.MouseEvent) => void;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  children?: React.ReactNode;
  text?: string;
  [key: string]: any;
}

export function PrimaryButton({
  classNames = '',
  textClass,
  permission = true,
  Children,
  onClick,
  disabled,
  type = "button",
  children,
  text,
  ...props
}: PrimaryButtonProps) {

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`flex justify-center items-center h-[1.75rem] border-[.5px] border-[#965CDE] font-normal bg-[#1E0C34] hover:bg-[#965CDE] transition-colors duration-200 rounded-md ${classNames}
        ${disabled ? '!bg-[#1E0C34] hover:!bg-[#1E0C34] border-[#965CDE] text-[#888888] cursor-not-allowed' : 'bg-[#1E0C34] hover:bg-[#965CDE]'} `}
      style={{
        minWidth: '4rem',
        paddingLeft: '.7rem',
        paddingRight: '.7rem'
      }}
      {...props}
    >
      {Children}
      <div className={`font-[600] text-[#EEEEEE] text-[0.75rem] leading-[100%] ${textClass || ''}`}>
        {children || text || "Next"}
      </div>
    </button>
  );
}

export function SecondaryButton({
  classNames = '',
  onClick,
  disabled,
  type = "button",
  children,
  text,
  ...props
}: any) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`text-[0.75rem] h-[1.75rem] border-[.5px] border-[#757575] min-w-[4rem] font-normal bg-[#1F1F1F] rounded-md transition-colors duration-200
      hover:bg-[#1F1F1F] hover:border-[#B3B3B3] ${classNames}
      ${disabled ? 'bg-[#1F1F1F] text-[#757575] cursor-not-allowed' : 'bg-[#1F1F1F]'}
      `}
      style={{
        paddingLeft: '.7rem',
        paddingRight: '.7rem'
      }}
      {...props}
    >
      <div className={`${disabled ? 'text-[#757575] font-600' : 'text-[#EEEEEE]'}`}>
        {children || text || "Back"}
      </div>
    </button>
  );
}
