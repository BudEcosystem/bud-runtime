import { Flex } from "@radix-ui/themes";
import React, { ComponentType } from "react";
import { Heading_30_600_FFFFFF, Text_12_400_B3B3B3 } from "../text";

import { PrimaryButton } from "../bud/form/Buttons";

interface pageHeaderProps {
  headding: string;
  text?: string;
  buttonLabel?: string;
  buttonAction?: () => void;
  classNames?: string;
  hClass?: string;
  ButtonIcon?: ComponentType<any>;
  rightComponent?: React.ReactNode;
  buttonPermission?: boolean;
}
const PageHeader: React.FC<pageHeaderProps> = ({
  headding,
  text,
  buttonLabel,
  buttonAction,
  classNames,
  ButtonIcon,
  rightComponent,
  hClass,
  buttonPermission,
}) => {
  return (
    <>
      <div
        className={`pageHeader flex justify-between items-start ${classNames}`}
      >
        <div className="flex flex-col justify-start gap-[3] items-start">
          <Heading_30_600_FFFFFF className={`mb-0 pt-[.2rem] !text-[var(--text-primary)] ${hClass}`}>
            {headding}
          </Heading_30_600_FFFFFF>
          {text && (
            <Text_12_400_B3B3B3 className="pt-[.8rem] pl-[.15rem]">
              {text}
            </Text_12_400_B3B3B3>
          )}
        </div>
        <Flex align="center">
          {rightComponent}
          {buttonLabel && (
            <Flex align={"center"} justify={"end"} className="">
              <PrimaryButton
                permission={buttonPermission}
                type="submit"
                onClick={buttonAction}
                classNames="!pr-[.8rem] tracking-[.02rem]"
              >
                <div className="flex items-center justify-center gap-[.2rem]">
                  {ButtonIcon && (
                    <ButtonIcon
                      className="text-[#FFFFFF]"
                      width="14px"
                      height="14px"
                    />
                  )}
                  {buttonLabel}
                </div>
              </PrimaryButton>
            </Flex>
          )}
        </Flex>
      </div>
    </>
  );
};

export default PageHeader;
