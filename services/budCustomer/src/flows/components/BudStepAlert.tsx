"use client";

import React from "react";
import AlertIcons from "./AlertIcons";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import { PrimaryButton, SecondaryButton } from "@/components/ui/button";

interface BudStepAlertProps {
  children?: React.ReactNode;
  type?: "info" | "warning" | "error" | "success";
  className?: string;
  title?: string;
  description?: string;
  cancelAction?: () => void;
  confirmAction?: () => Promise<void> | void;
  confirmText?: string;
  cancelText?: string;
}

const BudStepAlert: React.FC<BudStepAlertProps> = ({
  children,
  type = "info",
  className = "",
  title,
  description,
  cancelAction,
  confirmAction,
  confirmText = "Confirm",
  cancelText = "Cancel",
}) => {
  return (
    <div className={`p-[1.5rem] rounded-[6px] flex`}>
      <AlertIcons
        type={
          type === "success"
            ? "success"
            : type === "warning"
              ? "warining"
              : type === "error"
                ? "failed"
                : "success" // default fallback
        }
      />
      <div className="ml-[1rem]  w-full">
        <Text_14_400_EEEEEE>{title}</Text_14_400_EEEEEE>
        <div className="height-10"></div>
        <Text_12_400_757575 className="pb-[1.5rem]">
          {description}
        </Text_12_400_757575>
        <div className="flex justify-end items-center w-full gap-[.6rem]">
          {cancelAction && (
            <SecondaryButton
              onClick={cancelAction}
              classNames="!px-[.8rem] tracking-[.02rem]"
            >
              {cancelText}
            </SecondaryButton>
          )}
          {confirmAction && (
            <PrimaryButton
              type="submit"
              onClick={confirmAction}
              classNames="!px-[.8rem] tracking-[.02rem]"
            >
              {confirmText}
            </PrimaryButton>
          )}
        </div>
      </div>
    </div>
  );
};

export default BudStepAlert;
