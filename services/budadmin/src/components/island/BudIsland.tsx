import React, { useCallback, useEffect, useMemo, useRef } from "react";
import { Modal, Tooltip } from "antd";
import { useIsland } from "src/hooks/useIsland";
import { Image } from "antd";
import { Text_10_400_B3B3B3 } from "../ui/text";
import {
  IMessage,
  useFetchNotifications,
  useSocket,
} from "@novu/notification-center";
import { useUser } from "src/stores/useUser";
import { useWorkflow } from "src/stores/useWorkflow";
import { useDrawer } from "src/hooks/useDrawer";
import { BudWidget } from "./BudWidget";
import { NotificationsWidget } from "./BudNotification";
import BudChat from "../chat/BudChat";
import { inProgressSteps } from "src/hooks/drawerFlows";
import { formdateDateTime } from "@/lib/utils";
import { FormProgressStatus } from "../ui/bud/progress/FormProgress";
import { useSpring, animated } from "@react-spring/web";

type NotificationPayload = {
  category: "inapp" | "internal";
  type: string;
  event: string;
  workflow_id: string;
  workflow_type: string;
  total_steps: number;
  current_step: number;
  content: {
    title: string;
    message: string;
    status: string;
    icon: string;
    result: string;
  };
  createdAt: string;
};

const BudIsland: React.FC = () => {
  const { user } = useUser();
  const {
    isDrawerOpen,
    minmizedProcessList,
    openDrawerWithStep,
    showMinimizedItem,
  } = useDrawer();
  const { socket } = useSocket();
  const { workflowList, getWorkflowList } = useWorkflow();
  const [lastNotification, setLastNotification] = React.useState<IMessage>();
  const { data, refetch, isLoading, isRefetching } = useFetchNotifications({
    query: {
      payload: {
        category: "inapp",
      },
      read: false,
      limit: 100,
    },
  });
  const allNotifications = useMemo(
    () => data?.pages?.flatMap((page) => page?.data),
    [data],
  );

  const { isOpen, close, open } = useIsland();
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const { x } = useSpring({
    from: { x: 0 },
    x: lastNotification ? 1 : 0,
    config: { duration: 1000 },
  });

  const { x: minimizeSpring } = useSpring({
    from: { x: 0 },
    x: showMinimizedItem ? 1 : 0,
    config: { duration: 1000 },
  });
  // const [storedNotifications, setStoredNotifications] = React.useState<IMessage[]>([]);

  const inAppNotifications = useMemo(() => {
    return allNotifications
      ?.map((notification: IMessage) => {
        return {
          ...notification.payload,
          createdAt: notification.createdAt,
        } as NotificationPayload;
      })
      ?.map((notification) => {
        const notificationDate = new Date(notification.createdAt);
        return {
          title: notification?.content.title,
          message: notification?.content?.message,
          time: formdateDateTime(notificationDate),
          status: notification?.content?.status,
          icon: notification?.content?.icon,
        };
      });
  }, [allNotifications]);

  const loadNotifications = useCallback(() => {
    refetch();
  }, [refetch]);

  useEffect(() => {
    if (socket) {
      const handleNotification = async (data: any) => {
        // Temporarily refetch the notifications
        loadNotifications();
        setLastNotification(data.message);
      };

      socket.on("notification_received", handleNotification);

      return () => {
        socket.off("notification_received");
      };
    }
    // Note: loadNotifications is intentionally excluded from deps to avoid removing
    // other components' listeners. Socket event handlers remain stable across renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socket]);

  useEffect(() => {
    if (!user) return;
    refetch();
    getWorkflowList();
  }, [isOpen, user]);


  // Hide the minimized item after 5 seconds
  useEffect(() => {
    if (lastNotification) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        setLastNotification(undefined);
      }, 3000);
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [lastNotification]);

  const recentlyMinimized =
    minmizedProcessList?.[minmizedProcessList?.length - 1];
  const recentlyMinimizedStep = recentlyMinimized?.step?.progress?.find(
    (step) => step?.status === FormProgressStatus.inProgress,
  );
  const totalSteps = recentlyMinimized?.step?.progress?.length;
  const currentStep =
    recentlyMinimized?.step?.progress?.findIndex(
      (step) => step?.status === FormProgressStatus.inProgress,
    ) + 1;

  let title = "Task Island";
  let statusRender = <></>;

  if (lastNotification && inAppNotifications?.[0]) {
    // TODO message icon progress
    title = inAppNotifications?.[0].message;
  } else if (
    inProgressSteps?.includes(recentlyMinimized?.step?.id) &&
    (lastNotification || showMinimizedItem)
  ) {
    title = recentlyMinimizedStep.title;
  } else if (
    recentlyMinimized?.step?.id &&
    (lastNotification || showMinimizedItem)
  ) {
    title = `Minmize ${recentlyMinimizedStep?.title}`;
    statusRender = (
      <p className="text-[#EEEEEE] text-nowrap max-w-[70%] overflow-hidden overflow-ellipsis text-[0.625rem] p-0 m-0">
        Step {currentStep} / {totalSteps}
      </p>
    );
  } else if (inAppNotifications?.length > 0) {
    title = `${inAppNotifications.length} Notifications`;
  } else {
    title = "Task Island";
  }

  // if (inProgressSteps?.includes(recentlyMinimized?.id)) {
  //     statusRender = <div className="self-end">
  //         <svg width="2rem" height=".625rem" viewBox="0 0 33 10" fill="none" xmlns="http://www.w3.org/2000/svg">
  //             <path d="M3.01318 1.03613C3.93441 1.03613 4.60661 1.22493 5.02979 1.60254C5.45296 1.98014 5.66455 2.50911 5.66455 3.18945C5.66455 3.4987 5.61572 3.79329 5.51807 4.07324C5.42367 4.34993 5.26742 4.5957 5.04932 4.81055C4.83122 5.02214 4.54313 5.18978 4.18506 5.31348C3.83024 5.43717 3.39242 5.49902 2.87158 5.49902H2.10986V8.1748H0.937988V1.03613H3.01318ZM2.93506 2.00781H2.10986V4.52246H2.74951C3.11735 4.52246 3.42985 4.48014 3.68701 4.39551C3.94417 4.30762 4.13949 4.16927 4.27295 3.98047C4.40641 3.79167 4.47314 3.54264 4.47314 3.2334C4.47314 2.81999 4.34782 2.51237 4.09717 2.31055C3.84977 2.10872 3.4624 2.00781 2.93506 2.00781ZM8.12061 2.76953V8.1748H6.97314V2.76953H8.12061ZM7.5542 0.699219C7.72998 0.699219 7.88135 0.746419 8.0083 0.84082C8.13851 0.935221 8.20361 1.09798 8.20361 1.3291C8.20361 1.55697 8.13851 1.71973 8.0083 1.81738C7.88135 1.91178 7.72998 1.95898 7.5542 1.95898C7.37191 1.95898 7.21729 1.91178 7.09033 1.81738C6.96663 1.71973 6.90479 1.55697 6.90479 1.3291C6.90479 1.09798 6.96663 0.935221 7.09033 0.84082C7.21729 0.746419 7.37191 0.699219 7.5542 0.699219ZM11.9438 8.27246C11.4328 8.27246 10.9901 8.17318 10.6157 7.97461C10.2414 7.77604 9.95329 7.47168 9.75146 7.06152C9.54964 6.65137 9.44873 6.13053 9.44873 5.49902C9.44873 4.84147 9.55941 4.30436 9.78076 3.8877C10.0021 3.47103 10.3081 3.16341 10.6987 2.96484C11.0926 2.76628 11.5435 2.66699 12.0513 2.66699C12.3735 2.66699 12.6649 2.69954 12.9253 2.76465C13.189 2.8265 13.4119 2.90299 13.5942 2.99414L13.2524 3.91211C13.0539 3.83073 12.8504 3.76237 12.6421 3.70703C12.4338 3.65169 12.2336 3.62402 12.0415 3.62402C11.7257 3.62402 11.4621 3.69401 11.2505 3.83398C11.0422 3.97396 10.8859 4.18229 10.7817 4.45898C10.6808 4.73568 10.6304 5.0791 10.6304 5.48926C10.6304 5.88639 10.6825 6.22168 10.7866 6.49512C10.8908 6.7653 11.0454 6.97038 11.2505 7.11035C11.4556 7.24707 11.7078 7.31543 12.0073 7.31543C12.3035 7.31543 12.5688 7.27962 12.8032 7.20801C13.0376 7.13639 13.259 7.04362 13.4673 6.92969V7.92578C13.2622 8.04297 13.0425 8.12923 12.8081 8.18457C12.5737 8.24316 12.2856 8.27246 11.9438 8.27246ZM15.8843 0.577148V4.24902C15.8843 4.41504 15.8778 4.59733 15.8647 4.7959C15.8517 4.99121 15.8387 5.17513 15.8257 5.34766H15.8501C15.9347 5.23372 16.0356 5.10026 16.1528 4.94727C16.2733 4.79427 16.3872 4.66081 16.4946 4.54688L18.145 2.76953H19.4634L17.3003 5.09375L19.605 8.1748H18.2573L16.5288 5.80176L15.8843 6.35352V8.1748H14.7368V0.577148H15.8843Z" fill="#EEEEEE" />
  //             <path fill-rule="evenodd" clipRule="evenodd" d="M27.6956 7.29307C27.5748 7.17975 27.5687 6.9899 27.682 6.86902L29.7396 4.67421L27.682 2.47939C27.5687 2.35851 27.5748 2.16866 27.6956 2.05534C27.8165 1.94203 28.0064 1.94815 28.1197 2.06902L30.3697 4.46902C30.4779 4.58442 30.4779 4.76399 30.3697 4.87939L28.1197 7.27939C28.0064 7.40026 27.8165 7.40639 27.6956 7.29307Z" fill="#B3B3B3" />
  //         </svg>
  //     </div>
  // }
  // else
  if (lastNotification?.data?.status === "STARTED") {
    // In Progress
    statusRender = (
      <svg
        width="10"
        height="11"
        viewBox="0 0 10 11"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M7.73504 5.8681C7.18044 5.8681 7.18044 5.03015 7.73504 5.03015H9.58333C10.1379 5.03015 10.1379 5.8681 9.58333 5.8681H7.73504Z"
          fill="#EEEEEE"
        />
        <path
          d="M6.63903 3.20764C6.24468 3.60199 6.84852 4.20583 7.23037 3.81148L8.53657 2.50529C8.93092 2.11094 8.33958 1.5196 7.94523 1.91395L6.63903 3.20764Z"
          fill="#EEEEEE"
        />
        <path
          d="M5.42071 8.18548C5.42071 7.63088 4.58276 7.63088 4.58276 8.18548V10.0338C4.58276 10.5884 5.42071 10.5884 5.42071 10.0338V8.18548Z"
          fill="#757575"
        />
        <path
          d="M7.23037 7.08941C6.84852 6.69506 6.24468 7.2989 6.63903 7.68075L7.94523 8.98694C8.33958 9.3813 8.93092 8.78996 8.53657 8.39561L7.23037 7.08941Z"
          fill="#757575"
        />
        <path
          d="M3.36013 7.68075C3.75448 7.2989 3.15064 6.69506 2.75629 7.08941L1.4626 8.39561C1.06824 8.78996 1.65958 9.3813 2.05393 8.98694L3.36013 7.68075Z"
          fill="#757575"
        />
        <path
          d="M2.25262 5.86883C2.80721 5.86883 2.80721 5.03088 2.25262 5.03088H0.416435C-0.138161 5.03088 -0.138161 5.86883 0.416435 5.86883H2.25262Z"
          fill="#757575"
        />
        <path
          d="M2.75629 3.81142C3.15064 4.20577 3.75448 3.60193 3.36013 3.20758L2.05393 1.91389C1.65958 1.51954 1.06824 2.11087 1.4626 2.50523L2.75629 3.81142Z"
          fill="#757575"
        />
        <path
          d="M4.57861 2.70196C4.57861 3.25655 5.41656 3.25655 5.41656 2.70196V0.865776C5.41656 0.31118 4.57861 0.31118 4.57861 0.865776V2.70196Z"
          fill="#EEEEEE"
        />
      </svg>
    );
  } else if (lastNotification?.data?.status === "FAILED") {
    // Failed
    statusRender = (
      <svg
        width="18"
        height="18"
        viewBox="0 0 18 18"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M9.00355 -0.000488281C4.04084 -0.000488281 0.000488281 4.03986 0.000488281 9.00155C0.000488281 13.9643 4.04084 17.9995 9.00355 17.9995C13.9663 17.9995 18.0015 13.9632 18.0015 9.00155C18.0015 4.03884 13.9652 -0.000488281 9.00355 -0.000488281Z"
          fill="#5B2525"
          fillOpacity="0.25"
        />
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M9.59477 4.83509C9.32814 4.38773 8.68026 4.38773 8.41364 4.8351L4.10702 12.061C3.8339 12.5192 4.1641 13.1004 4.69759 13.1004H13.3108C13.8443 13.1004 14.1745 12.5192 13.9014 12.061L9.59477 4.83509ZM8.95051 5.15508C8.97475 5.1144 9.03365 5.11441 9.05789 5.15507L13.3645 12.3809C13.3893 12.4226 13.3593 12.4754 13.3108 12.4754H4.69759C4.64909 12.4754 4.61907 12.4226 4.6439 12.3809L8.95051 5.15508ZM8.5535 7.44436C8.54371 7.18977 8.74745 6.97804 9.00223 6.97804C9.25701 6.97804 9.46076 7.18977 9.45096 7.44436L9.34838 10.1116C9.34122 10.2976 9.18836 10.4447 9.00223 10.4447C8.8161 10.4447 8.66324 10.2976 8.65609 10.1116L8.5535 7.44436ZM9.50238 11.439C9.50238 11.7151 9.27852 11.939 9.00238 11.939C8.72624 11.939 8.50238 11.7151 8.50238 11.439C8.50238 11.1628 8.72624 10.939 9.00238 10.939C9.27852 10.939 9.50238 11.1628 9.50238 11.439Z"
          fill="#E82E2E"
        />
      </svg>
    );
  }

  // TEST Animation
  // useEffect(() => {
  //     setInterval(() => {
  //         setLastNotification({} as any);
  //     }, 5000);
  // }, []);

  const onMouseEnter = () => {
    // setLastNotification(lastNotification ? undefined : inAppNotifications?.[0] as any);
  };

  return (
    <>
      <animated.button
        className="flex justify-start items-center rounded-[6.4px] mt-[0rem]  bg-[#FFFFFF08] cursor-pointer w-full hover:bg-[#FFFFFF1A] hover:border-[#FFFFFF1A]  hover:shadow-md  p-[.35rem]"
        type="button"
        onMouseEnter={onMouseEnter}
        onClick={() => {
          if (recentlyMinimized?.step?.id && showMinimizedItem) {
            return openDrawerWithStep(recentlyMinimized?.step?.id);
          }
          if (recentlyMinimized?.step?.id && lastNotification) {
            return openDrawerWithStep(recentlyMinimized?.step?.id);
          }
          return open();
        }}
        style={{
          // opacity: x.to({ range: [0, 1], output: [0.3, 1] }),
          scaleY: x.to({
            range: [0, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 1],
            output: [1, 0.97, 0.9, 1.2, 0.9, 1.1, 1.03, 1],
          }),
          // expand and shrink on minimizeSpring
          scaleX: minimizeSpring.to({
            range: [0, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 1],
            output: [1, 0.97, 0.9, 1.2, 0.9, 1.1, 1.03, 1],
          }),
        }}
      >
        <div className="h-[1.5rem] flex justify-center items-center pl-[.15rem]">
          {/* <IslandIcon /> */}
          <Image
            src="/images/BudIcon.png"
            preview={false}
            alt="info"
            style={{ width: "1.5rem", height: "auto" }}
          />
        </div>
        <div className="flex flex-row items-center justify-between w-full">
          <Tooltip title={title} color="#161616" placement="topLeft">
            <Text_10_400_B3B3B3 className="pl-[1rem] text-nowrap max-w-[70%] overflow-hidden overflow-ellipsis">
              {title}
            </Text_10_400_B3B3B3>
          </Tooltip>
          {statusRender}
        </div>
      </animated.button>
      <Modal
        className=" bg-transparent flex  flex-col shadow-none w-full border relative"
        closeIcon={null}
        // transitionName="ant-modal-zoom"
        classNames={{
          wrapper:
            "isLandWrapper overflow-hidden transition-all duration-500 ease-in-out",
          mask: `${!isDrawerOpen ? "bg-[#060607] opacity-90" : "bg-transparent"} transition-all duration-500 ease-in-out`,
          body: "islandBody rounded-[1rem] flex justify-end items-start relative w-full h-[100vh] gap-[1rem] pl-[2.25rem] pr-[2.45rem] pt-[4.6rem] pb-[.7rem]",
          content: "p-0 h-full bg-transparent border-none",
        }}
        open={isOpen && !isDrawerOpen}
        style={{
          maxWidth: "100%",
          margin: "0",
          top: 0,
          height: "100%",
          width: "100%",
          border: "none",
          opacity: isDrawerOpen && "0",
          transition: "opacity 0.5s ease-in-out",
          padding: 0,
        }}
        onCancel={() => {
          close();
        }}
        footer={null}
      >
        <div
          className="absolute custom-border w-[2rem] h-[2rem] flex justify-center items-center backdrop-blur-[34.40000534057617px] right-[2.05rem] top-[2.05rem] border-[1px]"
          onClick={() => {
            close();
          }}
        >
          <Image
            preview={false}
            src="/images/drawer/close.png"
            alt="info"
            style={{ height: ".0.8rem" }}
          />
        </div>
        <div className="flex justify-end items-top gap-[1rem] w-full h-[100%]">
          <div className="w-[50%] overflow-y-auto">
            <div className={`grid grid-cols-2 gap-x-[1rem] gap-y-[1rem] `}>
              <NotificationsWidget
                notifications={inAppNotifications}
                loadNotifications={loadNotifications}
                loading={isLoading || isRefetching}
              />
              {workflowList
                .map((workflow, index) => ({
                  workflow,
                  index,
                }))
                ?.map(({ workflow, index }) => (
                  <BudWidget data={workflow} index={index} key={index} />
                ))}
            </div>
          </div>
          <div className={` h-full overflow-hidden relative w-[50%]`}>
            {/* <ComingSoon shrink={true} scaleValue={.9} comingYpos='30%' /> */}
            <BudChat />
            {/* <EmbeddedIframe /> */}
          </div>
        </div>
      </Modal>
    </>
  );
};

export default function BudIslandProvider() {
  const { user } = useUser();
  if (!user) return null;

  return (
    // <NovuProvider applicationIdentifier={novuAppId} backendUrl={novuBackendUrl} socketUrl={novuSocketUrl} subscriberId={user?.id}>
    <BudIsland />
    // </NovuProvider>
  );
}
