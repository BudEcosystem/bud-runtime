"use client";
import React, {
  ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";

import "@radix-ui/themes/styles.css";
import { Theme } from "@radix-ui/themes";
import { Avatar, ConfigProvider, Image, Popover, Tooltip } from "antd";

import { usePathname } from "next/navigation";
import { AppRequest } from "./../api/requests";
import Link from "next/link";
import {
  ExitIcon,
  GearIcon,
  PersonIcon,
  QuestionMarkIcon,
} from "@radix-ui/react-icons";
import {
  Text_10_400_B3B3B3,
  Text_12_300_B3B3B3,
  Text_14_400_757575,
  Text_14_400_B3B3B3,
  Text_14_600_EEEEEE,
  Text_15_400_B3B3B3,
} from "@/components/ui/text";
import { Icon } from "@iconify/react";
import { branding } from "@/components/environment";
import { useShortCut } from "../../hooks/useShortCut";
import { useRouter } from "next/router";
import { useDrawer } from "src/hooks/useDrawer";
import { useOverlay } from "src/context/overlayContext";
import { useIsland } from "src/hooks/useIsland";
import BudIsland from "@/components/island/BudIsland";
import { PermissionEnum, useUser } from "src/stores/useUser";
import pkg from '@novu/notification-center/package.json';
import { enableDevMode } from "@/components/environment";
import AgentDrawer from "@/components/agents/AgentDrawer";
import {
  isOAuthCallback,
  getOAuthPromptId,
  getOAuthSessionData,
} from "@/hooks/useOAuthCallback";
import { useAgentStore } from "@/stores/useAgentStore";

interface LayoutProps {
  children: ReactNode;
  headerItems?: ReactNode;
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
      <div
        className="flex inline-flex justify-center items-center text-[0.625rem] py-0.5 bg-[#1F1F1F] rounded-sm text-[#B3B3B3] h-5 w-8 uppercase "
      >
        <Icon
          icon="ph:command"
          className="text-[0.625rem] mr-0.5 text-[#B3B3B3]"
        />{" "}
        {cmd}
      </div>
    );
  }

  return (
    <div
      className="flex inline-flex justify-center items-center text-[0.625rem] py-0.5 bg-[#1F1F1F] rounded-sm text-[#B3B3B3] h-5 w-8 uppercase opacity-0 opacity-100"
      style={{
        opacity: metaKeyPressed ? '1 !important' : '0 !important',
      }}
    >
      <Icon
        icon="ph:command"
        className="text-[0.625rem] mr-0.5 text-[#B3B3B3] group-hover:text-[#EEEEEE]"
      />{" "}
      {cmd}
    </div>
  );
}

const DashBoardLayout: React.FC<LayoutProps> = ({ children, headerItems }) => {
  const router = useRouter();
  const { isDrawerOpen, showMinimizedItem } = useDrawer();
  const [isHydrated, setIsHydrated] = useState(false);
  const oauthProcessedRef = React.useRef(false);
  const [isHovered, setIsHovered] = useState<any>();
  const pathname = usePathname();
  const { isVisible } = useOverlay();
  const { getUser, user, hasPermission, permissions } = useUser();
  const [overlayVisible, setOverlayVisible] = useState(false);
  const [generalOpen, setGeneralOpen] = React.useState(false);
  const tabs = [
    {
      label: "Projects",
      route: "/projects",
      icon: '/images/icons/projectIcon.png',
      iconWhite: '/images/icons/projectIconWhite.png',
      cmd: "1",
      hide: !hasPermission(PermissionEnum.ProjectView),
    },
    {
      label: "Models",
      route: "/modelRepo",
      icon: '/images/icons/modelRepo.png',
      iconWhite: '/images/icons/modelRepoWhite.png',
      cmd: "2",
      hide: !hasPermission(PermissionEnum.ModelView),
    },
    {
      label: "Clusters",
      route: "/clusters",
      icon: '/images/icons/cluster.png',
      iconWhite: '/images/icons/clustersWhite.png',
      cmd: "3",
      hide: !hasPermission(PermissionEnum.ClusterView),
    },
    {
      label: "Dashboard",
      route: "/dashboard",
      icon: '/images/icons/dashboard.png',
      iconWhite: '/images/icons/dashboardWhite.png',
      cmd: "4",
    },
    // { label: 'End Points', route: '/endPoints', icon: endPointsIcon},
    {
      label: "Playground",
      route: "/playground",
      icon: '/images/icons/play.png',
      iconWhite: '/images/icons/playWhite.png',
      cmd: "5",
    },
    // {
    //   label: "Simulation",
    //   route: "/simulation",
    //   icon: '/icons/simulations.png',
    //   iconWhite: '/icons/simulationsWhite.svg',
    //   cmd: "6",
    // },
    {
      label: "API Keys",
      route: "/apiKeys",
      icon: '/images/icons/key.png',
      iconWhite: '/images/icons/keyWhite.png',
      cmd: "6",
    },
    {
      label: "Agents",
      route: "/agents",
      icon: '/icons/prompt.png',
      iconWhite: '/icons/promptWhite.png',
      // iconSvg: true,
      cmd: "7",
      customSvg: "prompts",
      // hide: !enableDevMode,
    },
    {
      label: "Observability",
      route: "/observability",
      iconSvg: true,
      cmd: "8",
    },
    {
      label: "Evaluations",
      route: "/evaluations",
      icon: '/icons/simulations.png',
      iconWhite: '/icons/simulationsWhite.svg',
      cmd: "9",
      hide: !enableDevMode,
    },
    {
      label: "Guard Rails",
      route: "/guardrails",
      icon: '/icons/guard.png',
      iconWhite: '/icons/guardWhite.png',
      cmd: "10",
      hide: !enableDevMode,
    },
    {
      label: "Tools",
      route: "/tools",
      iconSvg: true,
      customSvg: "tools",
      cmd: "H",
      hide: !enableDevMode,
    },
    {
      label: "Pipelines",
      route: "/pipelines",
      icon: '/icons/simulations.png',
      iconWhite: '/icons/simulationsWhite.svg',
      cmd: "J",
      hide: !enableDevMode,
    },
  ]

  const tabsTwo = [
    {
      label: "User Management", route: "/users", icon: PersonIcon,
      hide: !hasPermission(PermissionEnum.UserManage),
    },
    { label: "Settings", route: "/settings", icon: GearIcon },
    // { label: "Help", route: "/help", icon: QuestionMarkIcon },
  ];
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (isHydrated && user) {
      document.documentElement.style.setProperty("--user-color", user?.color);
    }
  }, [isHydrated, user]);

  const roleMapping = {
    super_admin: "Super Admin",
    admin: "Admin",
    developer: "Developer",
    devops: "Devops",
    tester: "Tester",
  }

  // logout
  const logOut = async () => {
    try {
      const refreshToken = localStorage.getItem("refresh_token");

      if (refreshToken) {
        await AppRequest.Post("/auth/logout", {
          refresh_token: refreshToken
        });
      }

      localStorage.clear();
      window.location.replace("/");
    } catch (error) {
      console.error("Error during logout:", error);
      // Clear localStorage and redirect even if API call fails
      localStorage.clear();
      window.location.replace("/");
    }
  };

  function classNames(...classes: string[]) {
    return classes.filter(Boolean).join(" ");
  }

  useEffect(() => {
    getUser();
  }, []);

  // Global OAuth callback handling - ensures OAuth works from any page
  useEffect(() => {
    const handleGlobalOAuthCallback = async () => {
      // Check if this is an OAuth callback
      const isOAuth = isOAuthCallback();
      const savedPromptId = getOAuthPromptId();
      const savedSessionData = getOAuthSessionData();

      // Only proceed if we have OAuth indicators
      if (!isOAuth && !savedPromptId && !savedSessionData) {
        return;
      }

      // Prevent multiple processing
      if (oauthProcessedRef.current) {
        return;
      }

      // Mark as being processed
      oauthProcessedRef.current = true;

      try {
        const {
          setEditMode,
          setAddVersionMode,
          setEditVersionMode,
          restoreSessionWithPromptId,
          openAgentDrawer,
        } = useAgentStore.getState();

        // Restore agent mode flags if present
        if (savedSessionData) {
          const {
            isEditMode,
            editingPromptId,
            isAddVersionMode,
            addVersionPromptId,
            isEditVersionMode,
            editVersionData,
          } = savedSessionData;

          if (isEditMode && editingPromptId) {
            setEditMode(editingPromptId);
          }
          if (isAddVersionMode && addVersionPromptId) {
            setAddVersionMode(addVersionPromptId);
          }
          if (isEditVersionMode && editVersionData) {
            setEditVersionMode(editVersionData);
          }
        }

        // Restore session with prompt ID
        if (savedPromptId) {
          restoreSessionWithPromptId(savedPromptId, {
            name: savedSessionData?.name || `Agent 1`,
            modelId: savedSessionData?.modelId,
            modelName: savedSessionData?.modelName,
            systemPrompt: savedSessionData?.systemPrompt,
            promptMessages: savedSessionData?.promptMessages,
            selectedDeployment: savedSessionData?.selectedDeployment,
          });
        }

        // Get workflow next step from saved session data
        // CRITICAL: If we have an agent ID in URL, we're in add-agent workflow
        // Default to "add-agent-configuration" as the next step after AgentDrawer save
        const urlParams = new URLSearchParams(window.location.search);
        const agentIdFromUrl = urlParams.get('agent');
        const savedWorkflowNextStep = savedSessionData?.workflowNextStep;
        const workflowNextStep = savedWorkflowNextStep ||
          (agentIdFromUrl ? "add-agent-configuration" : undefined);

        // Open the agent drawer after a short delay to ensure state is set
        // CRITICAL: Pass workflowNextStep to ensure the next step is triggered after save
        requestAnimationFrame(() => {
          openAgentDrawer(undefined, workflowNextStep);
        });
      } catch (error) {
        console.error('[Layout] Error restoring OAuth session:', error);
      }
    };

    handleGlobalOAuthCallback();
  }, [router.query.code, router.query.state]);

  // useEffect(() => {
  //   console.log("Novu Notification Center version:", pkg.version);
  //   console.log("process.env.NEXT_PUBLIC_BASE_URL", process.env.NEXT_PUBLIC_BASE_URL);
  //   console.log("process.env.NEXT_PUBLIC_NOVU_SOCKET_URL", process.env.NEXT_PUBLIC_NOVU_SOCKET_URL);
  //   console.log("process.env.NEXT_PUBLIC_NOVU_BASE_URL", process.env.NEXT_PUBLIC_NOVU_BASE_URL);
  //   console.log("process.env.NEXT_PUBLIC_NOVU_APP_ID", process.env.NEXT_PUBLIC_NOVU_APP_ID);
  // }, []);

  const handleOpenChange = (open: boolean) => {
    setGeneralOpen(open);
  };
  const content = (
    <>
      <div className="px-[1.35em] pt-[1rem] mb-[.65rem] tracking-[.03rem]">
        <Text_14_400_757575>General</Text_14_400_757575>
      </div>
      {pathname && (
        <>
          {/* <Text>{pathname}</Text> */}
          <div
            className="flex justify-start items-start flex-col gap-1 menuWrap pt-[0.25em]"
          >
            {tabsTwo.map((tab) => {
              const Icon = tab.icon;

              const isActive = pathname?.includes(tab.route);
              const isVisible = !tab.hide;

              return (
                <Link
                  className="linkLink mb-[.6rem] w-full"
                  onClick={(e) => !isVisible && e.preventDefault()}
                  key={tab.route}
                  href={tab.route}
                  passHref
                >
                  <div
                    className={classNames(
                      "flex items-center gap-2 group gap-x-[0.85em] rounded-md py-[0.25em] px-[1.3rem] font-light text-[#B3B3B3]",
                      "LinkDiv",
                      isVisible && "hover:font-semibold hover:text-[#EEEEEE]",
                      isActive && "!text-[#EEEEEE]"
                    )}
                  >
                    <div className="LinkIcn">
                      <Icon
                        width="1.05em"
                        height="1.05em"
                        className={classNames(
                          "w-[1.05em] h-[1.05em] 1920px:w-[1.2em] 1920px:h-[1.2em]",
                          isVisible && "group-hover:text-[#EEEEEE]",
                          (isHovered === tab.route || isActive) && "text-[#EEEEEE]"
                        )}
                      />
                    </div>
                    <Text_15_400_B3B3B3
                      className={classNames(
                        "pl-[0.25em] !text-[.875rem]",
                        isVisible && "group-hover:text-[#EEEEEE]",
                        (isHovered === tab.route || isActive) && "text-[#EEEEEE]"
                      )}
                    >
                      {tab.label}
                    </Text_15_400_B3B3B3>
                  </div>
                </Link>
              );
            })}

          </div>
        </>
      )}
      <div className="px-[1.1em] pb-[1rem]">
        <div
          className={classNames(
            "flex items-center justify-start gap-[.5] LinkDiv cursor-pointer group flex gap-x-[0.85em] rounded-md py-[0.3em] pl-[.3rem] pr-[.6em] font-light text-[#B3B3B3] hover:font-semibold hover:text-[#EEEEEE]"
          )}
          onClick={logOut}
        >
          <div className="LinkIcn">
            <ExitIcon
              width="1em"
              height="1em"
              className="w-[1em] h-[1em] 1920px:w-[1.2em] 1920px:h-[1.2em]"
            />
          </div>
          <Text_15_400_B3B3B3 className="block pl-[0.25em] !text-[0.875em] group-hover:text-[#EEEEEE]">
            Log out
          </Text_15_400_B3B3B3>
        </div>
      </div>
    </>
  );
  return (
    <div>
      {/* <Theme accentColor="iris" appearance="dark" style={{ background: 'transparent' }} className=""> */}
      <Theme accentColor="iris" appearance="dark" className="">
        <div className="dashboardWrapper flex justify-between relative">
          <div className={`dashboardOverlay absolute w-full h-full top-0 left-0 z-[1200] ${isVisible ? 'block' : 'hidden'}`}></div>
          <div
            className="flex flex-col justify-between items-start gap-[1rem] leftDiv py-[1.55em] pb-[.7em] scroll-smooth custom-scrollbar overflow-auto open-sans"
          >
            <div className="w-full 1680px:text-[1rem]">
              <div className="flex justify-center leftLogo px-[7%] pb-[1.65rem]">
                <Image
                  preview={false}
                  className="mainLogo"
                  style={{ width: '100px' }}
                  src={branding.logoUrl}
                  alt="Bud Logo"
                />
              </div>
              <div className="px-[.75rem] mb-[3%]">
                <BudIsland />
              </div>
              <div
                className="flex justify-start items-center flex-col menuWrap pt-[0.235rem] px-[.6rem]"
              >
                {tabs.filter(tab => !tab.hide).map((tab) => {
                  const isActive = pathname?.includes(tab.route);
                  const isVisible = !tab.hide;

                  return (
                    <Link
                      className="linkLink mb-[.3rem]"
                      key={tab.route}
                      href={tab.route}
                      passHref
                      onMouseEnter={() => isVisible && setIsHovered(tab.route)}
                      onMouseLeave={() => isVisible && setIsHovered(false)}
                      onClick={(e) => !isVisible && e.preventDefault()}
                    >
                      <div
                        className={classNames(
                          "flex justify-between items-center gap-2 group gap-x-[0.75em] rounded-md py-[0.3em] px-[.7em] font-light text-[#B3B3B3]",
                          "LinkDiv",
                          isVisible && "hover:font-semibold hover:text-[#EEEEEE]",
                          isActive && "!text-[#EEEEEE] bg-[#1F1F1F]"
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <div className="LinkIcn">
                            {tab.iconSvg ? (
                              tab.customSvg === "prompts" ? (
                                // Message/Chat bubble SVG for Prompts
                                <svg
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="14"
                                  height="14"
                                  viewBox="0 0 14 14"
                                  fill="none"
                                  className={classNames(
                                    "w-[0.875em] h-[0.875em] 1920px:w-[1em] 1920px:h-[1em]",
                                    (isHovered === tab.route || isActive) ? "fill-[#EEEEEE]" : "fill-[#B3B3B3]"
                                  )}
                                >
                                  <path
                                    fillRule="evenodd"
                                    clipRule="evenodd"
                                    d="M2 1.5C1.17157 1.5 0.5 2.17157 0.5 3V9C0.5 9.82843 1.17157 10.5 2 10.5H3.5V12.5C3.5 12.7761 3.72386 13 4 13C4.13807 13 4.26858 12.9414 4.35858 12.8414L6.70711 10.5H12C12.8284 10.5 13.5 9.82843 13.5 9V3C13.5 2.17157 12.8284 1.5 12 1.5H2ZM1.5 3C1.5 2.72386 1.72386 2.5 2 2.5H12C12.2761 2.5 12.5 2.72386 12.5 3V9C12.5 9.27614 12.2761 9.5 12 9.5H6.5C6.36193 9.5 6.23142 9.55858 6.14142 9.65858L4.5 11.2929V10C4.5 9.72386 4.27614 9.5 4 9.5H2C1.72386 9.5 1.5 9.27614 1.5 9V3ZM4 4.5C3.72386 4.5 3.5 4.72386 3.5 5C3.5 5.27614 3.72386 5.5 4 5.5H10C10.2761 5.5 10.5 5.27614 10.5 5C10.5 4.72386 10.2761 4.5 10 4.5H4ZM3.5 7C3.5 6.72386 3.72386 6.5 4 6.5H8C8.27614 6.5 8.5 6.72386 8.5 7C8.5 7.27614 8.27614 7.5 8 7.5H4C3.72386 7.5 3.5 7.27614 3.5 7Z"
                                    fill="currentColor"
                                  />
                                </svg>
                              ) : tab.customSvg === "tools" ? (
                                // Wrench/Tool SVG for Tools
                                <svg
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="14"
                                  height="14"
                                  viewBox="0 0 24 24"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="2"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  className={classNames(
                                    "w-[0.875em] h-[0.875em] 1920px:w-[1em] 1920px:h-[1em]",
                                    (isHovered === tab.route || isActive) ? "stroke-[#EEEEEE]" : "stroke-[#B3B3B3]"
                                  )}
                                >
                                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                                </svg>
                              ) : (
                                // Folder SVG for Observability
                                <svg
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="14"
                                  height="14"
                                  viewBox="0 0 14 15"
                                  fill="none"
                                  className={classNames(
                                    "w-[0.875em] h-[0.875em] 1920px:w-[1em] 1920px:h-[1em]",
                                    (isHovered === tab.route || isActive) ? "fill-[#EEEEEE]" : "fill-[#B3B3B3]"
                                  )}
                                >
                                  <path
                                    fillRule="evenodd"
                                    clipRule="evenodd"
                                    d="M1.75 2.11719C1.50828 2.11719 1.3125 2.31296 1.3125 2.55469V12.4922C1.3125 12.7339 1.50828 12.9297 1.75 12.9297H12.25C12.4917 12.9297 12.6875 12.7339 12.6875 12.4922V4.74219C12.6875 4.50046 12.4917 4.30469 12.25 4.30469H7.875C7.71148 4.30469 7.56147 4.21718 7.48353 4.07718L6.39147 2.11719H1.75ZM0.4375 2.55469C0.4375 1.82951 1.02483 1.24219 1.75 1.24219H6.625C6.78852 1.24219 6.93853 1.3297 7.01647 1.4697L8.10853 3.42969H12.25C12.9752 3.42969 13.5625 4.01701 13.5625 4.74219V12.4922C13.5625 13.2174 12.9752 13.8047 12.25 13.8047H1.75C1.02483 13.8047 0.4375 13.2174 0.4375 12.4922V2.55469Z"
                                    fill="currentColor"
                                  />
                                </svg>
                              )
                            ) : (
                              <>
                                {/* Hovered Icon (White) */}
                                <div
                                  className={classNames(
                                    "icon",
                                    (isHovered === tab.route || isActive) ? "visible" : "hidden"
                                  )}
                                >
                                  <Image
                                    preview={false}
                                    src={tab.iconWhite}
                                    style={{ width: "1em", height: "1em" }}
                                    alt="Hovered Logo"
                                    className="1920px:w-[1.2em] 1920px:h-[1.2em]"
                                  />
                                </div>
                                {/* Default Icon */}
                                <div
                                  className={classNames(
                                    "icon",
                                    (isHovered !== tab.route && !isActive) ? "visible" : "hidden"
                                  )}
                                >
                                  <Image
                                    preview={false}
                                    src={tab.icon}
                                    style={{ width: "1em", height: "1em" }}
                                    alt="Default Logo"
                                    className="1920px:w-[1.2em] 1920px:h-[1.2em]"
                                  />
                                </div>
                              </>
                            )}
                          </div>
                          <Text_14_400_B3B3B3
                            className={classNames(
                              "pl-[0.65em] tracking-[.03rem]",
                              (isHovered === tab.route || isActive) && "!text-[#EEE]"
                            )}
                          >
                            {tab.label}
                          </Text_14_400_B3B3B3>
                        </div>

                        {/* Keyboard shortcut component */}
                        <ShortCutComponent
                          cmd={tab.cmd}
                          action={() => isVisible && router.push(tab.route)}
                        />
                      </div>
                    </Link>
                  );
                })}

              </div>
            </div>
            <div className="block w-full">
              <div className="w-full block rounded-lg profileDetailsBtnWrap">
                <ConfigProvider
                  theme={{
                    token: {
                      sizePopupArrow: 0,
                    },
                  }}
                  getPopupContainer={(trigger) => (trigger.parentNode as HTMLElement) || document.body}
                >
                  <Popover
                    open={generalOpen}
                    onOpenChange={handleOpenChange}
                    content={content}
                    title=""
                    trigger="click"
                    placement="top"
                  >
                    <div className="relative px-[.5em] pt-[.6rem] border-[#1F1F1F] border-t w-full">
                      <div className="relative px-[.6rem] py-[.6rem] flex items-center cursor-pointer hover:bg-[#1F1F1F] rounded-[0.5rem] group w-[full]">
                        <div className=" mr-3 ">
                          {user && <Tooltip
                            // key={user?.email}
                            // title={user?.name}
                            placement="top"
                          >
                            <Avatar
                              shape="square"
                              className="w-[1.8rem] h-[1.8rem]"
                              src={
                                <Image
                                  preview={false}
                                  src="/images/drawer/memoji.png"
                                  alt="memoji"
                                  className="w-full h-full rounded-full"
                                  style={{
                                    padding: "1px"
                                  }}
                                />
                              }
                              style={{
                                backgroundColor: user?.color || '#965CDE',
                              }}
                            />
                          </Tooltip>}
                        </div>
                        <div className="max-w-[65%]">
                          <div className="flex items-center mb-[1]">
                            <Text_14_600_EEEEEE className="mr-2 truncate max-w-[100%] overflow-hidden">
                              {user?.name}
                            </Text_14_600_EEEEEE>
                            {(user?.role === "admin" || user?.role === "super_admin") && (
                              <div className="bg-[#965CDE33] text-[#CFABFC] px-2 py-[3px] rounded-[50px] border border-[#CFABFC] text-[0.45rem] leading-[100%] text-nowrap">
                                {roleMapping[user?.role]}
                              </div>
                            )}
                          </div>
                          <Text_12_300_B3B3B3 className="truncate max-w-[100%] overflow-hidden">
                            {user?.email}
                          </Text_12_300_B3B3B3>
                        </div>
                        <div className="absolute w-[1.1rem] h-[1.1rem] right-[.5rem] top-[0rem] bottom-0 m-auto flex justify-center items-center">
                          <Image
                            preview={false}
                            src="/images/icons/dropIcn.svg"
                            alt="memoji"
                            className="w-[1.1rem] h-[1.1rem] rounded-full rotate-[-90deg]"
                            style={{
                              padding: "1px"
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </Popover>
                </ConfigProvider>
              </div>
            </div>
          </div>
          {/* Render the right side content based on the route */}
          <div className="blur-sm" />
          <div className="rightWrap py-[0.75rem] pr-[0.6875rem]">
            <div
              className={`rightDiv rounded-[17px] overflow-hidden ${isDrawerOpen && !showMinimizedItem ? "blur-sm" : ""
                // className={`rightDiv rounded-xl overflow-hidden	my-[0.5em] mr-[0.5em] ${isDrawerOpen ? "blur-sm" : ""
                }`}
            >
              {headerItems && (
                <div
                  className="headerWrap"
                >
                  <div className="pr-10">{headerItems}</div>
                </div>
              )}
              {/* Render children components here */}
              {children}
            </div>
          </div>
        </div>
        {/* Add footer or other common components here */}

        {/* Global Agent Drawer - Available on all pages */}
        <AgentDrawer />
      </Theme>
    </div>
  );
};

export default DashBoardLayout;
