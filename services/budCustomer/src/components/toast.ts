import { App } from "antd";
import type { NotificationInstance } from "antd/es/notification/interface";

// These are deprecated - use useNotification hook instead
// Keeping them for backward compatibility but they should be replaced
let notificationApi: NotificationInstance | null = null;

export const initNotification = (api: NotificationInstance) => {
  notificationApi = api;
};

export const errorToast = (message: string) => {
  if (notificationApi) {
    notificationApi.error({
      message: "Error",
      description: message,
      placement: "topRight",
    });
  } else {
    console.error("Notification API not initialized. Use useNotification hook instead.");
  }
};

export const successToast = (message: string) => {
  if (notificationApi) {
    notificationApi.success({
      message: "Success",
      description: message,
      placement: "topRight",
    });
  } else {
    console.error("Notification API not initialized. Use useNotification hook instead.");
  }
};

export const warningToast = (message: string) => {
  if (notificationApi) {
    notificationApi.warning({
      message: "Warning",
      description: message,
      placement: "topRight",
    });
  } else {
    console.error("Notification API not initialized. Use useNotification hook instead.");
  }
};

export const infoToast = (message: string) => {
  if (notificationApi) {
    notificationApi.info({
      message: "Info",
      description: message,
      placement: "topRight",
    });
  } else {
    console.error("Notification API not initialized. Use useNotification hook instead.");
  }
};

// Export the hook for new usage
export { useNotification } from "./NotificationProvider";
