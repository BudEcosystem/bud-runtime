import * as React from "react";
import { Text } from "@radix-ui/themes";

export const pxToRem = (px: number) => `${px / 16}rem`;

interface TextProps {
  children: React.ReactNode;
  className?: string;
  [key: string]: any;
}

const Text_12_400_red = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[red] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_10_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.625rem] font-normal text-[#FFFFFF] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_10_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.625rem] font-normal text-[#EEEEEE] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_9_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.57rem] font-normal text-[#EEEEEE] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_10_400_757575 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.625rem] font-normal text-[#757575] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_10_400_B3B3B3 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.625rem] font-normal text-[#B3B3B3] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_10_400_44474D = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.625rem] font-normal text-[#44474D] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_10_400_D1B854 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.625rem] font-normal text-[#D1B854] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_6_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.375em] font-normal text-[#FFFFFF] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_8_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.5rem] font-normal text-[#FFFFFF] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_8_300_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.515625rem] font-[300] text-[#FFFFFF] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_5B6168 = ({ children = "", className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#5B6168]  ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_400_5B6168 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-normal text-[#5B6168] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_300_757575 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-[300] text-[#757575] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_13_400_757575 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.8125rem] font-normal text-[#757575] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_400_757575 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-normal text-[#757575] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_16_400_757575 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[1rem] font-normal text-[#757575] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_16_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[1rem] font-[400] text-[#FFFFFF] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_16_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[1rem] font-[400] text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_14_400_965CDE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-normal text-[#965CDE] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_18191B = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#18191B] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_757575 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.75rem] font-normal text-[#757575] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_A4A4A9 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[.75rem] font-[400] text-[#A4A4A9] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_787B83 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#787B83] leading-4 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_400_787B83 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-sm font-normal text-[#787B83] leading-4 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-[400] text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_500_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-[500] text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_400_B3B3B3 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-sm font-normal text-[#B3B3B3] leading-4 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_10_300_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.65rem] font-light text-[#FFFFFF] leading-[110%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_300_C7C7C7 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-light text-[#C7C7C7] leading-[16px] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_10_300_6A6E76 = ({ children = "", className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.625rem] font-light	 text-[#6A6E76] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_300_6A6E76 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-light	 text-[#6A6E76] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_6A6E76 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#6A6E76] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_300_44474D = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-light	 text-[#44474D] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_300_111113 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-light	 text-[#111113] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_300_B3B3B3 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-light	 text-[#B3B3B3] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_500_111113 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-medium text-[#B3B3B3] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_C7C7C7 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#C7C7C7] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_400_C7C7C7 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-normal text-[#C7C7C7] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#FFFFFF] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.875rem] font-normal text-[#FFFFFF] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_B3B3B3 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#B3B3B3] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_15_400_B3B3B3 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.9375rem] font-normal text-[#B3B3B3] leading-[.75rem] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_15_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.9375rem] font-normal text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_15_600_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.9375rem] font-[600] text-[#EEEEEE] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_11_400_808080 = ({ children, className = "", ...props }: TextProps) => (
  <div
    {...props}
    className={`block text-[0.6875rem] font-normal text-[#808080] ${className}`}
  >
    {children}
  </div>
);
const Text_12_400_808080 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal text-[#808080] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_300_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-light text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-normal ${className}`}
    {...props}
    style={{
      lineHeight: '.75rem',
      color: '#EEEEEE'
    }}
  >
    {children}
  </div>
);
const Text_12_600_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.75rem] font-[600] text-[#EEEEEE] ${className}`}
    {...props}
    style={{
      lineHeight: '100%'
    }}
  >
    {children}
  </div>
);
const Text_13_300_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.8125rem] font-light text-[#FFFFFF] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_13_400_B3B3B3= ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.8125rem] font-normal text-[#B3B3B3] leading-[.75rem] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_13_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.8125rem] font-[400] text-[#EEEEEE] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_13_400_tag= ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.8125rem] font-[400] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_20_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[1.2rem] font-normal text-[#FFFFFF] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_8_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[0.5rem] font-normal text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_18_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[1.125rem] font-normal text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_20_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[1.25rem] font-normal text-[#EEEEEE] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_12_300_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-xs font-light text-[#FFFFFF] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_18_600_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[1.125rem] font-[600] text-[#FFFFFF] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_24_500_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[#FFFFFF] font-medium text-[1.5rem] leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_24_500_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[#EEEEEE] font-medium text-[1.5rem] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_24_600_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[#EEEEEE] font-[600] text-[1.5rem] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_24_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block font-[600] text-[1.5rem] ${className}`}
    style={{
      color: '#FFFFFF',
    }}
    {...props}
  >
    {children}
  </div>
);

const Text_24_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[#EEEEEE] font-[400] text-[1.5rem] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_16_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-base font-semibold  ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_17_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] font-[1.0625rem] font-semibold ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_12_500_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`block text-[#FFFFFF] font-medium text-xs leading-3 ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF]   text-[0.875rem] font-semibold leading-[24px] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_300_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[0.875rem] font-[300]  leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_600_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[0.875rem] font-semibold leading-[1.5rem] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_14_600_B3B3B3 = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#B3B3B3] text-[0.875rem] font-semibold leading-[1.5rem] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_18_700_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[1.125rem] font-semibold leading-[26px] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_18_500_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[1.125rem] font-[600] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_24_700_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[1.5rem] font-semibold leading-[26px] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_26_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[1.625rem] font-semibold ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_26_600_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[1.625rem] font-[600] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_26_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[1.625rem] font-[400] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_32_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={` text-[2rem] font-semibold leading-[24px] ${className}`}
    style={{
      color: '#FFFFFF',
    }}
    {...props}
  >
    {children}
  </div>
);
const Text_32_400_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[2rem] font-normal leading-[24px] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_32_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[2rem] font-normal ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_32_500_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[2rem] font-medium leading-[24px] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_32_700_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[3.19375rem] font-bold leading-[24px] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_28_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[1.75rem] font-[600] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_38_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[2.375rem] font-[400] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Text_19_600_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[1.1875rem] font-[600] leading-[100%] ${className}`}
    {...props}
  >
    {children}
  </div>
);
const Heading_26_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[1.625rem] font-[600] ${className}`}
    style={{
      lineHeight: '100%',
    }}
    {...props}
  >
    {children}
  </div>
);
const Heading_30_600_FFFFFF = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#FFFFFF] text-[1.875rem] font-[600] ${className}`}
    style={{
      lineHeight: '100%',
    }}
    {...props}
  >
    {children}
  </div>
);

const Text_22_700_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`text-[#EEEEEE] text-[1.4rem] font-semibold leading-[24px] ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Ibm_12_500_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div
    className={`ibm text-[#EEEEEE] text-[.75rem] font-[500] ${className}`}
    {...props}
  >
    {children}
  </div>
);


const Text_53_400_EEEEEE = ({ children, className = "", ...props }: TextProps) => (
  <div className={`text-[3.3125rem] text-[#EEEEEE] leading-[100%] font-[400] ${className}`} {...props}>
    {children}
  </div>
);

const Text_13_400_479D5F = ({ children, className = "", ...props }: TextProps) => (
  <div className={`text-[0.8125rem] text-[#479D5F] leading-[100%] font-[400] ${className}`} {...props}>
    {children}
  </div>
);

const Text_13_400_EC7575 = ({ children, className = "", ...props }: TextProps) => (
  <div className={`text-[0.8125rem] text-[#EC7575] leading-[100%] font-[400] ${className}`} {...props}>
    {children}
  </div>
);

const Text_13_400_4077E6 = ({ children, className = "", ...props }: TextProps) => (
  <div className={`text-[0.8125rem] text-[#4077E6] leading-[100%] font-[400] ${className}`} {...props}>
    {children}
  </div>
);

const Text_13_400_965CDE = ({ children, className = "", ...props }: TextProps) => (
  <div className={`text-[0.8125rem] text-[#965CDE] leading-[100%] font-[400] ${className}`} {...props}>
    {children}
  </div>
);

const Text_13_400_D1B854 = ({ children, className = "", ...props }: TextProps) => (
  <div className={`text-[0.8125rem] text-[#D1B854] leading-[100%] font-[400] ${className}`} {...props}>
    {children}
  </div>
);

export {
  Text_53_400_EEEEEE,
  Heading_26_600_FFFFFF,
  Heading_30_600_FFFFFF,
  Text_12_400_red,
  Text_12_400_A4A4A9,
  Text_12_400_787B83,
  Text_14_400_787B83,
  Text_12_400_C7C7C7,
  Text_16_600_FFFFFF,
  Text_17_600_FFFFFF,
  Text_12_500_111113,
  Text_12_500_FFFFFF,
  Text_12_300_C7C7C7,
  Text_14_400_FFFFFF,
  Text_12_300_6A6E76,
  Text_12_400_5B6168,
  Text_14_400_5B6168,
  Text_14_400_965CDE,
  Text_14_300_757575,
  Text_13_400_757575,
  Text_14_400_757575,
  Text_16_400_757575,
  Text_16_400_EEEEEE,
  Text_16_400_FFFFFF,
  Text_10_300_FFFFFF,
  Text_12_300_111113,
  Text_12_300_B3B3B3,
  Text_10_400_FFFFFF,
  Text_10_400_44474D,
  Text_10_400_D1B854,
  Text_14_600_FFFFFF,
  Text_12_400_FFFFFF,
  Text_12_400_18191B,
  Text_14_400_C7C7C7,
  Text_14_400_B3B3B3,
  Text_14_300_EEEEEE,
  Text_14_600_EEEEEE,
  Text_10_300_6A6E76,
  Text_12_400_6A6E76,
  Text_12_300_44474D,
  Text_8_400_FFFFFF,
  Text_8_300_FFFFFF,
  Text_6_400_FFFFFF,
  Text_20_400_FFFFFF,
  Text_8_400_EEEEEE,
  Text_18_400_EEEEEE,
  Text_20_400_EEEEEE,
  Text_24_700_FFFFFF,
  Text_32_400_FFFFFF,
  Text_32_400_EEEEEE,
  Text_32_500_FFFFFF,
  Text_32_600_FFFFFF,
  Text_32_700_FFFFFF,
  Text_12_300_FFFFFF,
  Text_18_600_EEEEEE,
  Text_26_600_FFFFFF,
  Text_26_600_EEEEEE,
  Text_26_400_EEEEEE,
  Text_24_500_FFFFFF,
  Text_24_500_EEEEEE,
  Text_13_300_FFFFFF,
  Text_18_700_FFFFFF,
  Text_12_400_B3B3B3,
  Text_15_600_EEEEEE,
  Text_15_400_B3B3B3,
  Text_15_400_EEEEEE,
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
  Text_11_400_808080,
  Text_12_400_808080,
  Text_13_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_38_400_EEEEEE,
  Text_19_600_EEEEEE,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_18_500_EEEEEE,
  Text_24_600_EEEEEE,
  Text_24_600_FFFFFF,
  Text_24_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_10_400_EEEEEE,
  Text_9_400_EEEEEE,
  Text_10_400_757575,
  Text_10_400_B3B3B3,
  Text_13_400_tag,
  Text_22_700_EEEEEE,
  Text_14_600_B3B3B3,
  Text_28_600_FFFFFF,
  Ibm_12_500_EEEEEE,
  Text_13_400_479D5F,
  Text_13_400_EC7575,
  Text_13_400_4077E6,
  Text_13_400_965CDE,
  Text_13_400_D1B854
};
