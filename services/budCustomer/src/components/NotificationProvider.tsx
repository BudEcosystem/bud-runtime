"use client";

import React, { createContext, useContext } from "react";
import { App } from "antd";
import type { NotificationArgsProps } from "antd";

type NotificationType = "success" | "info" | "warning" | "error";

interface NotificationContextType {
  errorToast: (message: string) => void;
  successToast: (message: string) => void;
  warningToast: (message: string) => void;
  infoToast: (message: string) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined
);

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error(
      "useNotification must be used within a NotificationProvider"
    );
  }
  return context;
};

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { notification } = App.useApp();

  const showNotification = (
    type: NotificationType,
    title: string,
    message: string
  ) => {
    notification[type]({
      message: title,
      description: message,
      placement: "topRight",
    });
  };

  const errorToast = (message: string) => {
    showNotification("error", "Error", message);
  };

  const successToast = (message: string) => {
    showNotification("success", "Success", message);
  };

  const warningToast = (message: string) => {
    showNotification("warning", "Warning", message);
  };

  const infoToast = (message: string) => {
    showNotification("info", "Info", message);
  };

  return (
    <NotificationContext.Provider
      value={{ errorToast, successToast, warningToast, infoToast }}
    >
      {children}
    </NotificationContext.Provider>
  );
};
