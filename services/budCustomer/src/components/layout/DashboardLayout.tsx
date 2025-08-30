"use client";
import React, { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Image, Badge, Avatar, Typography } from "antd";
import { Icon } from "@iconify/react/dist/iconify.js";
import {
  Text_10_400_B3B3B3,
  Text_12_300_B3B3B3,
  Text_12_400_B3B3B3,
  Text_14_400_757575,
  Text_14_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import styles from "./DashboardLayout.module.scss";
import { useShortCut } from "@/hooks/useShortCut";
import ThemeSwitcher from "@/components/ui/ThemeSwitcher";
import { useTheme } from "@/context/themeContext";
import { useUser } from "@/stores/useUser";
import BudIsland from "@/components/island/BudIsland";

const { Text } = Typography;

interface LayoutProps {
  children: ReactNode;
  headerItems?: ReactNode;
}

interface TabItem {
  label: string;
  route: string;
  icon: string;
  iconWhite?: string;
  shortcut?: string;
  notificationCount?: number;
}

function ShortCutComponent({
  cmd,
  action,
}: {
  cmd: string;
  action: () => void;
}) {
  const { metaKeyPressed } = useShortCut({
    key: cmd,
    action: action,
  });

  if (metaKeyPressed) {
    return (
      <div className="flex inline-flex justify-center items-center text-[0.625rem] py-0.5 bg-bud-bg-secondary rounded-sm text-bud-text-muted h-5 w-8 uppercase">
        <Icon
          icon="ph:command"
          className="text-[0.625rem] mr-0.5 text-bud-text-muted"
        />
        {cmd}
      </div>
    );
  }

  return (
    <div className="flex inline-flex justify-center items-center text-[0.625rem] py-0.5 bg-bud-bg-secondary rounded-sm text-bud-text-muted h-5 w-8 uppercase opacity-0 group-hover:opacity-100 transition-opacity">
      <Icon
        icon="ph:command"
        className="text-[0.625rem] mr-0.5 text-bud-text-muted group-hover:text-bud-text-primary"
      />
      {cmd}
    </div>
  );
}

const DashboardLayout: React.FC<LayoutProps> = ({ children, headerItems }) => {
  const pathname = usePathname();
  const router = useRouter();
  const { effectiveTheme } = useTheme();
  const [isHovered, setIsHovered] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // User context
  const { user, logout, getUser: fetchUser } = useUser();

  const tabs: TabItem[] = [
    {
      label: "Models",
      route: "/models",
      icon: "/icons/modelRepo.png",
      iconWhite: "/icons/modelsLight.png",
      shortcut: "0",
    },
    {
      label: "Playground",
      route: "/playground",
      icon: "/icons/play.png",
      iconWhite: "/icons/playIcn.png",
      shortcut: "1",
    },
    {
      label: "Batches",
      route: "/batches",
      icon: "/icons/batchesDark.png",
      iconWhite: "/icons/batchesLight.png",
      shortcut: "2",
    },
    {
      label: "Logs",
      route: "/logs",
      icon: "/icons/logsDark.png",
      iconWhite: "/icons/logsLight.png",
      shortcut: "3",
    },
    {
      label: "Usage & Billing",
      route: "/usage",
      icon: "/icons/billingDark.png",
      iconWhite: "/icons/billingWhite.png",
      shortcut: "4",
    },
    {
      label: "Audit",
      route: "/audit",
      icon: "/icons/auditDark.png", // Using logs icon as fallback
      iconWhite: "/icons/auditLight.png",
      shortcut: "5",
    },
    {
      label: "API Keys",
      route: "/api-keys",
      icon: "/icons/key.png",
      iconWhite: "/icons/keyWhite.png",
      shortcut: "6",
    },
    {
      label: "Projects",
      route: "/projects",
      icon: "/icons/projectIcon.png",
      iconWhite: "/icons/projectsLight.png",
      shortcut: "7",
    },
  ];

  const isActive = (route: string) => pathname === route;

  const handleLogout = () => {
    logout();
  };


  const getUser = async () => {
    // showLoader();
    try {
      const userData: any = await fetchUser();
      console.log(userData)
    } catch (error) {
      console.error("Error  fetching user", error);
      return router.push("/login");
    } finally {
      // hideLoader();
    }
  };
  useEffect(()=> {
    if(!user?.id) {
      getUser();
    }
  }, [user])

  return (
    <div className="flex h-screen bg-bud-bg-primary">
      {/* Sidebar */}
      <div
        className={`${isCollapsed ? "w-[80px]" : "w-[260px]"} bg-bud-bg-primary border-r border-bud-border flex flex-col relative transition-all duration-300`}
      >
        {/* Collapse/Expand Button */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="absolute -right-3 top-8 w-6 h-6 bg-bud-bg-secondary border border-bud-border-secondary rounded-full flex items-center justify-center hover:bg-bud-bg-tertiary transition-colors z-10"
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Icon
            icon={
              isCollapsed
                ? "material-symbols:chevron-right"
                : "material-symbols:chevron-left"
            }
            className="text-sm text-bud-text-muted"
          />
        </button>
        {/* Logo and Theme Switcher */}
        <div
          className={`${isCollapsed ? "p-4" : "p-6"} transition-all duration-300`}
        >
          <div
            className={`flex items-center ${isCollapsed ? "justify-center" : "justify-between"} mb-6`}
          >
            <Link href="/projects">
              <Image
                preview={false}
                width={isCollapsed ? 40 : 80}
                src={
                  effectiveTheme === "light"
                    ? isCollapsed
                      ? "/images/BudIcon.png"
                      : "/BudLogo-white.png"
                    : isCollapsed
                      ? "/images/BudIcon.png"
                      : "/images/BudLogo.png"
                }
                alt="Bud Logo"
              />
            </Link>
            {!isCollapsed && (
              <div className="ml-auto">
                <ThemeSwitcher />
              </div>
            )}
          </div>
          {/* {isCollapsed && (
            <div className="flex justify-center mb-4">
              <ThemeSwitcher />
            </div>
          )} */}

          {/* Notifications */}
        <BudIsland />

            <div className="bg-bud-bg-secondary rounded-lg p-3 mb-1 cursor-pointer hover:bg-bud-bg-tertiary transition-colors hidden">
              <Badge
                count={88}
                offset={isCollapsed ? [0, -10] : [50, -10]}
                style={{ backgroundColor: "#965CDE" }}
              >
                <div className="flex items-center gap-3">
                  <div className={`${
                      isCollapsed ? "w-6 h-6" : "w-8 h-8"
                    } bg-bud-purple rounded flex items-center justify-center`}>
                    <Icon
                      icon="heroicons-outline:bell"
                      className="text-white text-lg"
                    />
                  </div>
                  {!isCollapsed && (<div>
                    <Text className="text-bud-text-disabled text-xs block">
                      88 New
                    </Text>
                    <Text className="text-bud-text-primary text-sm">
                      Notifications
                    </Text>
                  </div>)}
                </div>
              </Badge>
            </div>
        </div>

        {/* Scrollable Content Area */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Navigation */}
          <nav className="flex-1 px-3 overflow-y-auto sidebar-scroll">
            {tabs.map((tab) => {
              const active = isActive(tab.route);
              const hovered = isHovered === tab.route;

              return (
                <Link
                  key={tab.route}
                  href={tab.route}
                  className={`
                  group flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-all
                  ${active ? "bg-bud-bg-secondary border border-bud-purple/20" : "hover:bg-bud-bg-secondary"}
                  ${isCollapsed ? "justify-center" : ""}
                `}
                  onMouseEnter={() => setIsHovered(tab.route)}
                  onMouseLeave={() => setIsHovered(null)}
                >
                  <Image
                    preview={false}
                    width={20}
                    height={20}
                    src={
                      active || hovered ? tab.iconWhite || tab.icon : tab.icon
                    }
                    alt={tab.label}
                    title={isCollapsed ? tab.label : undefined}
                  />
                  {!isCollapsed && (
                    <>
                      <Text
                        className={`text-bud-text-muted text-sm ${active ? "!text-bud-text-primary" : ""}`}
                      >
                        {tab.label}
                      </Text>
                      {tab.shortcut && (
                        <div className="ml-auto">
                          <ShortCutComponent
                            cmd={tab.shortcut}
                            action={() => router.push(tab.route)}
                          />
                        </div>
                      )}
                    </>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* User Section */}
        <div
          className={`${isCollapsed ? "p-4" : "p-6"} border-t border-bud-border transition-all duration-300`}
        >
          {isCollapsed ? (
            <div className="flex flex-col items-center gap-3">
              <Avatar size={32} style={{ backgroundColor: "#965CDE" }}>
                <Icon icon="mdi:user" className="text-lg" />
              </Avatar>
              <button
                onClick={handleLogout}
                className="text-bud-text-disabled hover:text-bud-text-primary transition-colors p-2"
                title="Logout"
              >
                <Icon icon="material-symbols:logout" className="text-xl" />
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar
                    size={36}
                    style={{ backgroundColor: "#965CDE" }}
                    className="flex-shrink-0"
                  >
                    <Icon icon="mdi:user" className="text-xl" />
                  </Avatar>
                  <div>
                    <div className="text-bud-text-primary text-sm font-medium">
                      {user?.name || "User"}
                    </div>
                    <Text className="text-bud-text-disabled text-xs">
                      {user?.email || "user@bud.studio"}
                    </Text>
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="text-bud-text-disabled hover:text-bud-text-primary transition-colors p-2"
                >
                  <Icon icon="material-symbols:logout" className="text-xl" />
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        {headerItems && (
          <div className="bg-bud-bg-primary border-b border-bud-border px-8 py-4">
            {headerItems}
          </div>
        )}

        {/* Page Content */}
        <main className="flex-1 bg-bud-bg-primary overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
