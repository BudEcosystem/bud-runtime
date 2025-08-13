"use client";

import { useEffect } from "react";
import { App } from "antd";
import { initNotification } from "./toast";

export const AppInitializer: React.FC = () => {
  const { notification } = App.useApp();

  useEffect(() => {
    // Initialize the notification API for backward compatibility
    initNotification(notification);
  }, [notification]);

  return null;
};
