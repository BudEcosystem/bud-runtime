"use client";
import { useRouter } from "next/router";
import { useState } from "react";
import DashBoardLayout from "../../layout";
import {
  Text_14_600_B3B3B3,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import { Tabs } from "antd";
import OverviewTab from "./overview";
import VersionsTab from "./versions";
import CacheTab from "./cache";
import LogsTracesTab from "./logsTraces";
import SettingsTab from "./settings";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

const AgentDetailsPage = () => {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("1");

  const operations = (
    <PrimaryButton
      onClick={() => {
        // TODO: Implement add version or settings action
        console.log("Action button clicked");
      }}
      classNames="mt-[.2rem] shadow-purple-glow"
    >
      <span className="flex items-center gap-2">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M8 3V13M3 8H13"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
        Add Version
      </span>
    </PrimaryButton>
  );

  const agentTabs = [
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "1" ? (
    //         <Text_14_600_EEEEEE>Prompt Home</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>Prompt Home</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "1",
    //   children: <OverviewTab />,
    // },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "1" ? (
            <Text_14_600_EEEEEE>Versions</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Versions</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "1",
      children: <VersionsTab />,
    },
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "3" ? (
    //         <Text_14_600_EEEEEE>Cache</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>Cache</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "3",
    //   children: <CacheTab />,
    // },
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "4" ? (
    //         <Text_14_600_EEEEEE>Logs & Traces</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>Logs & Traces</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "4",
    //   children: <LogsTracesTab />,
    // },
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "5" ? (
    //         <Text_14_600_EEEEEE>Bud Sentinel</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>Bud Sentinel</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "5",
    //   children: <div className="p-6 text-center text-gray-400">Bud Sentinel - Coming Soon</div>,
    // },
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "6" ? (
    //         <Text_14_600_EEEEEE>FinOps</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>FinOps</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "6",
    //   children: <div className="p-6 text-center text-gray-400">FinOps - Coming Soon</div>,
    // },
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "7" ? (
    //         <Text_14_600_EEEEEE>Users</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>Users</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "7",
    //   children: <div className="p-6 text-center text-gray-400">Users - Coming Soon</div>,
    // },
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "8" ? (
    //         <Text_14_600_EEEEEE>Settings</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>Settings</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "8",
    //   children: <SettingsTab />,
    // },
  ];

  return (
    <DashBoardLayout>
      <div className="temp-bg h-full w-full">
        <div className="evalTab agentTab h-full">
          <Tabs
            defaultActiveKey="1"
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key)}
            // tabBarExtraContent={operations}
            className="h-full"
            items={agentTabs}
          />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default AgentDetailsPage;
