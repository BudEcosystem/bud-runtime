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
  loading?: boolean;
  [key: string]: any;
}

export function PrimaryButton({
  classNames = "",
  textClass,
  permission = true,
  Children,
  onClick,
  disabled,
  type = "button",
  children,
  text,
  loading = false,
  ...props
}: PrimaryButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex justify-center items-center h-[1.75rem] border-[.5px] border-[#965CDE] font-normal bg-[#1E0C34] hover:bg-[#965CDE] transition-colors duration-200 rounded-md ${classNames}
        ${disabled || loading ? "!bg-[#1E0C34] hover:!bg-[#1E0C34] border-[#965CDE] text-[#888888] cursor-not-allowed" : "bg-[#1E0C34] hover:bg-[#965CDE]"} `}
      style={{
        minWidth: "4rem",
        paddingLeft: ".7rem",
        paddingRight: ".7rem",
      }}
      {...props}
    >
      {Children}
      <div className="flex items-center justify-center gap-2">
        {loading && (
          <svg
            className="animate-spin h-3 w-3 text-[#EEEEEE]"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
        )}
        <div
          className={`font-[600] text-[#EEEEEE] text-[0.75rem] leading-[100%] ${textClass || ""}`}
        >
          {loading ? "Loading..." : (children || text || "Next")}
        </div>
      </div>
    </button>
  );
}

export function SecondaryButton({
  classNames = "",
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
      ${disabled ? "bg-[#1F1F1F] text-[#757575] cursor-not-allowed" : "bg-[#1F1F1F]"}
      `}
      style={{
        paddingLeft: ".7rem",
        paddingRight: ".7rem",
      }}
      {...props}
    >
      <div
        className={`${disabled ? "text-[#757575] font-600" : "text-[#EEEEEE]"}`}
      >
        {children || text || "Back"}
      </div>
    </button>
  );
}
