import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import { Image, notification } from "antd";
import { useEffect } from "react";
import AlertIcons from "src/flows/components/AlertIcons";

export type ConfirmActionProps = {
  loading: boolean;
  okAction: () => void;
  okText?: string;
  cancelText?: string;
  cancelAction: () => void;
  message: string;
  description: string;
  type: "warning" | "failed" | "success";
  key: string;
};

export function useConfirmAction() {
  const [api, contextHolder] = notification.useNotification();
  const openConfirm = (props: ConfirmActionProps) => {
    setTimeout(() => {
      api.open({
        message: props.message,
        description: props.description,
        duration: 0,
        icon: <AlertIcons type={props.type} />,
        key: props.key || "confirm",
        placement: "bottomRight",
        className: "notification-modal",
        closable: true,
        style: {
          backgroundColor: "#020202",
          color: "#EEEEEE",
          border: "1px solid #333333",
          borderRadius: "10px",
          boxShadow: "0px 4px 4px rgba(0, 0, 0, 0.25)",
          padding: "1rem",
        },
        btn: (
          <div className="flex justify-end gap-x-[.5rem]">
            {props.cancelText && (
              <SecondaryButton
                disabled={props.loading}
                onClick={async (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  await props.cancelAction();
                  api.destroy();
                }}
              >
                {props.cancelText}
              </SecondaryButton>
            )}
            {props.okText && (
              <PrimaryButton
                loading={props.loading}
                onClick={async (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  await props.okAction();
                  api.destroy();
                }}
              >
                {props.okText}
              </PrimaryButton>
            )}
          </div>
        ),
      });
    }, 100);
  };

  return {
    openConfirm,
    contextHolder,
  };
}
