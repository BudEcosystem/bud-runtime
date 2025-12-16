import React from "react";
import { Form, FormRule, Input, Image } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import { ChevronDown, ChevronRight } from "lucide-react";
import AlertIcons from "./AlertIcons";

export interface Props {
  type?: "warning" | "failed" | "success";
  confirmText?: string;
  cancelText?: string;
  title?: string;
  description?: string;
  confirmAction?: () => void;
  cancelAction?: () => void;
  loading?: boolean;
}

function BudStepAlert(props: Props) {
  return (
    <div className={`p-[1.5rem] rounded-[6px] flex`}>
      <AlertIcons type={props.type} />
      <div className="ml-[1rem]  w-full">
        <Text_14_400_EEEEEE>{props.title}</Text_14_400_EEEEEE>
        <div className="height-10"></div>
        <Text_12_400_757575 className="pb-[1.5rem]">
          {props.description}
        </Text_12_400_757575>
        <div className="flex justify-end items-center w-full gap-[.6rem]">
          {props.cancelAction && (
            <SecondaryButton
              disabled={props.loading}
              onClick={props.cancelAction}
              classNames="!px-[.8rem] tracking-[.02rem]"
            >
              {props.cancelText}
            </SecondaryButton>
          )}
          {props.confirmAction && (
            <PrimaryButton
              loading={props.loading}
              disabled={props.loading}
              type="submit"
              onClick={props.confirmAction}
              classNames="!px-[.8rem] tracking-[.02rem]"
            >
              {props.confirmText}
            </PrimaryButton>
          )}
        </div>
      </div>
    </div>
  );
}

export default BudStepAlert;
