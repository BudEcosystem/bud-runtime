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
import LogsTab from "./logs";
import SettingsTab from "./settings";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import BackButton from "@/components/ui/bud/drawer/BackButton";

const AgentDetailsPage = () => {
  const router = useRouter();
  // Support both 'id' (from rewrite rule) and 'agentId' (from folder name)
  const { id, agentId, projectId, name } = router.query;
  const promptId = (id || agentId) as string;
  const [activeTab, setActiveTab] = useState("1");

  const handleGoBack = () => {
    router.back();
  };

  const tabBarExtraContent = {
    left: (
      <BackButton onClick={handleGoBack} classNames="ml-4" />
    ),
    right: null,
  };

  const agentTabs = [
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "1" ? (
            <Text_14_600_EEEEEE>Home</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Home</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "1",
      children: <OverviewTab />,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "2" ? (
            <Text_14_600_EEEEEE>Versions</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Versions</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "2",
      children: <VersionsTab />,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "3" ? (
            <Text_14_600_EEEEEE>Observability</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Observability</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "3",
      children: <LogsTab promptName={name as string} promptId={promptId} projectId={projectId as string} />,
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
        <div className="evalTab agentTab h-full ">
          <Tabs
            defaultActiveKey="1"
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key)}
            tabBarExtraContent={tabBarExtraContent}
            className="h-full"
            items={agentTabs}
          />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default AgentDetailsPage;
