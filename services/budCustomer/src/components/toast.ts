import { notification } from "antd";

export const errorToast = (message: string) => {
  notification.error({
    message: "Error",
    description: message,
    placement: "topRight",
  });
};

export const successToast = (message: string) => {
  notification.success({
    message: "Success",
    description: message,
    placement: "topRight",
  });
};

export const warningToast = (message: string) => {
  notification.warning({
    message: "Warning",
    description: message,
    placement: "topRight",
  });
};

export const infoToast = (message: string) => {
  notification.info({
    message: "Info",
    description: message,
    placement: "topRight",
  });
};
