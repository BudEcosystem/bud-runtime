"use client";
import React, { ReactNode, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Image, Badge, Avatar } from "antd";
import { Icon } from "@iconify/react/dist/iconify.js";
import {
  Text_10_400_B3B3B3,
  Text_12_300_B3B3B3,
  Text_12_400_B3B3B3,
  Text_14_400_757575,
  Text_14_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE
} from "@/components/ui/text";
import styles from "./DashboardLayout.module.scss";
import { useShortCut } from "@/hooks/useShortCut";
import ThemeSwitcher from "@/components/ui/ThemeSwitcher";

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
      <div className="flex inline-flex justify-center items-center text-[0.625rem] py-0.5 bg-[#1F1F1F] rounded-sm text-[#B3B3B3] h-5 w-8 uppercase">
        <Icon
          icon="ph:command"
          className="text-[0.625rem] mr-0.5 text-[#B3B3B3]"
        />
        {cmd}
      </div>
    );
  }

  return (
    <div
      className="flex inline-flex justify-center items-center text-[0.625rem] py-0.5 bg-[#1F1F1F] rounded-sm text-[#B3B3B3] h-5 w-8 uppercase opacity-0 group-hover:opacity-100 transition-opacity"
    >
      <Icon
        icon="ph:command"
        className="text-[0.625rem] mr-0.5 text-[#B3B3B3] group-hover:text-[#EEEEEE]"
      />
      {cmd}
    </div>
  );
}

const DashboardLayout: React.FC<LayoutProps> = ({ children, headerItems }) => {
  const pathname = usePathname();
  const router = useRouter();
  const [isHovered, setIsHovered] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const tabs: TabItem[] = [
    {
      label: "Projects",
      route: "/projects",
      icon: "/icons/project.png",
      iconWhite: "/icons/projectIconWhite.png",
      shortcut: "1"
    },
    {
      label: "Models",
      route: "/models",
      icon: "/icons/modelRepo.png",
      iconWhite: "/icons/modelRepoWhite.png",
      shortcut: "2"
    },
    {
      label: "Clusters",
      route: "/clusters",
      icon: "/icons/cluster.png",
      iconWhite: "/icons/clusterWhite.png",
      shortcut: "3"
    },
    {
      label: "Dashboard",
      route: "/dashboard",
      icon: "/icons/dashboard.png",
      iconWhite: "/icons/dashboardWhite.png",
      shortcut: "4"
    },
    {
      label: "Playground",
      route: "/playground",
      icon: "/icons/playIcn.png",
      iconWhite: "/icons/playWhite.png",
      shortcut: "5"
    },
    {
      label: "API Keys",
      route: "/api-keys",
      icon: "/icons/key.png",
      iconWhite: "/icons/keyWhite.png",
      shortcut: "6"
    },
    {
      label: "Usage & Billing",
      route: "/usage",
      icon: "/icons/billing.svg",
      iconWhite: "/icons/billingWhite.svg",
      shortcut: "7"
    },
    {
      label: "Logs",
      route: "/logs",
      icon: "/icons/logs.svg",
      iconWhite: "/icons/logsWhite.svg",
      shortcut: "8"
    },
    {
      label: "Batches",
      route: "/batches",
      icon: "/icons/batches.svg",
      iconWhite: "/icons/batchesWhite.svg",
      shortcut: "9"
    }
  ];

  const isActive = (route: string) => pathname === route;

  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem("auth_token");
    }
    router.push("/login");
  };

  return (
    <div className="flex h-screen bg-bud-bg-primary">
      {/* Sidebar */}
      <div className={`${isCollapsed ? 'w-[80px]' : 'w-[260px]'} bg-bud-bg-primary border-r border-bud-border flex flex-col relative transition-all duration-300`}>
        {/* Collapse/Expand Button */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="absolute -right-3 top-8 w-6 h-6 bg-bud-bg-secondary border border-bud-border-secondary rounded-full flex items-center justify-center hover:bg-bud-bg-tertiary transition-colors z-10"
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Icon
            icon={isCollapsed ? "material-symbols:chevron-right" : "material-symbols:chevron-left"}
            className="text-sm text-[#B3B3B3]"
          />
        </button>
        {/* Logo and Notifications */}
        <div className={`${isCollapsed ? 'p-4' : 'p-6'} transition-all duration-300`}>
          <Link href="/dashboard">
            <Image
              preview={false}
              width={isCollapsed ? 40 : 80}
              src={isCollapsed ? "/images/BudIcon.png" : "/images/BudLogo.png"}
              alt="Bud Logo"
              className={`${isCollapsed ? 'mb-4 mx-auto' : 'mb-6'} transition-all duration-300`}
            />
          </Link>

          {/* Notifications */}
          {!isCollapsed && (
            <div className="bg-bud-bg-secondary rounded-lg p-3 mb-6 cursor-pointer hover:bg-bud-bg-tertiary transition-colors">
              <Badge count={88} offset={[10, 0]} style={{ backgroundColor: '#965CDE' }}>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-[#965CDE] rounded flex items-center justify-center">
                    <Icon icon="heroicons-outline:bell" className="text-white text-lg" />
                  </div>
                  <div>
                    <Text_12_400_B3B3B3>88 Notifications</Text_12_400_B3B3B3>
                    <Text_14_400_EEEEEE>88 Notifications</Text_14_400_EEEEEE>
                  </div>
                </div>
              </Badge>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3">
          {tabs.map((tab) => {
            const active = isActive(tab.route);
            const hovered = isHovered === tab.route;

            return (
              <Link
                key={tab.route}
                href={tab.route}
                className={`
                  group flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-all
                  ${active ? 'bg-bud-bg-secondary border border-[#965CDE33]' : 'hover:bg-bud-bg-secondary'}
                  ${isCollapsed ? 'justify-center' : ''}
                `}
                onMouseEnter={() => setIsHovered(tab.route)}
                onMouseLeave={() => setIsHovered(null)}
              >
                <Image
                  preview={false}
                  width={20}
                  height={20}
                  src={active || hovered ? tab.iconWhite || tab.icon : tab.icon}
                  alt={tab.label}
                  title={isCollapsed ? tab.label : undefined}
                />
                {!isCollapsed && (
                  <>
                    <Text_14_400_B3B3B3 className={active ? '!text-white' : ''}>
                      {tab.label}
                    </Text_14_400_B3B3B3>
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

        {/* User Section */}
        <div className={`${isCollapsed ? 'p-4' : 'p-6'} border-t border-bud-border transition-all duration-300`}>
          {/* Theme Switcher */}
          <div className="mb-4 flex justify-center">
            <ThemeSwitcher />
          </div>

          {isCollapsed ? (
            <div className="flex flex-col items-center gap-3">
              <Avatar
                size={32}
                style={{ backgroundColor: '#965CDE' }}
              >
                <Icon icon="mdi:user" className="text-lg" />
              </Avatar>
              <button
                onClick={handleLogout}
                className="text-[#757575] hover:text-white transition-colors p-2"
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
                    style={{ backgroundColor: '#965CDE' }}
                    className="flex-shrink-0"
                  >
                    <Icon icon="mdi:user" className="text-xl" />
                  </Avatar>
                  <div>
                    <div className="text-white text-sm font-medium">Admin</div>
                    <Text_12_300_B3B3B3>admin@bud.studio</Text_12_300_B3B3B3>
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="text-bud-text-disabled hover:text-bud-text-primary transition-colors p-2"
                >
                  <Icon icon="material-symbols:logout" className="text-xl" />
                </button>
              </div>
              <div className="mt-2 px-2">
                <span className="text-xs bg-[#965CDE20] text-[#965CDE] px-2 py-1 rounded">
                  Super Admin
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        {headerItems && (
          <div className="bg-[#0A0A0A] border-b border-[#1F1F1F] px-8 py-4">
            {headerItems}
          </div>
        )}

        {/* Page Content */}
        <main className="flex-1 bg-black overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
