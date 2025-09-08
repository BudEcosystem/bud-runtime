"use client";

import { NovuProvider } from "@novu/notification-center";
import {
  apiBaseUrl,
  novuAppId,
  novuBackendUrl,
  novuSocketUrl,
} from "@/components/environment";
import { useUser } from "src/stores/useUser";

const primaryColor = "white";
const secondaryColor = "#1F1F1F";
const primaryTextColor = "#0C0404";
const secondaryTextColor = "#494F55";
const unreadBackGroundColor = "#AFE1AF";
const primaryButtonBackGroundColor = unreadBackGroundColor;
const secondaryButtonBackGroundColor = "#C6DFCD";
const popupBgColor = "#101010";

export const styles = {
  bellButton: {
    root: {
      svg: {
        color: "#EEE",
        fill: "",
        maxHeight: "20px",
        maxWidth: "20px",
      },
    },
    dot: {
      rect: {
        fill: "white",
        strokeWidth: "0",
        width: "10px",
        height: "10px",
        x: 0,
        y: 2,
      },
    },
  },
  unseenBadge: {
    root: { color: primaryTextColor, background: "#fff" },
  },
  popover: {
    arrow: {
      backgroundColor: popupBgColor,
    },
    dropdown: {
      borderRadius: "10px",
      border: "#1F1F1F",
    },
  },
  layout: {
    root: {
      background: popupBgColor,
      borderColor: "#1F1F1F",
    },
  },
  loader: {
    root: {
      stroke: primaryColor,
    },
  },
  notifications: {
    root: {
      ".nc-notifications-list-item": {
        backgroundColor: secondaryColor,
      },
    },
    listItem: {
      layout: {
        borderRadius: "7px",
        color: "#FFF",
        fontSize: ".85rem",
        "div:has(> .mantine-Avatar-root)": {
          border: "none",
          width: "20px",
          height: "20px",
          minWidth: "20px",
        },
        ".mantine-Avatar-root": {
          width: "20px",
          height: "20px",
          minWidth: "20px",
        },
        ".mantine-Avatar-image": {
          width: "20px",
          height: "20px",
          minWidth: "20px",
        },
      },
      timestamp: {
        color: secondaryTextColor,
        fontWeight: "bold",
        fontSize: ".65rem",
      },
      dotsButton: {
        display: "none",
        path: {
          fill: secondaryTextColor,
        },
      },
      unread: {
        "::before": { background: unreadBackGroundColor },
      },
      buttons: {
        primary: {
          background: primaryButtonBackGroundColor,
          color: primaryTextColor,
          display: "none",
          "&:hover": {
            background: primaryButtonBackGroundColor,
            color: secondaryTextColor,
          },
        },
        secondary: {
          background: secondaryButtonBackGroundColor,
          color: secondaryTextColor,
          display: "none",
          "&:hover": {
            background: secondaryButtonBackGroundColor,
            color: secondaryTextColor,
          },
        },
      },
    },
  },
  actionsMenu: {
    // item: { "&:hover": { backgroundColor: secondaryColor } },
    dropdown: {
      transform: "translateX(-10px)",
    },
    arrow: {
      borderTop: "0",
      borderLeft: "0",
    },
  },
};

export function NovuCustomProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, getUser: fetchUser } = useUser();

  // Don't initialize Novu until we have a user
  if (!user?.id) {
    return <>{children}</>;
  }

  return (
    <NovuProvider
      backendUrl={novuBackendUrl}
      socketUrl={novuSocketUrl}
      subscriberId={String(user.id)}  // Ensure it's a string
      applicationIdentifier={novuAppId || ""}
      styles={styles}
    >
      {children}
    </NovuProvider>
  );
}
