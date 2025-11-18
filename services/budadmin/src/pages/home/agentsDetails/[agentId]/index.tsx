"use client";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import DashBoardLayout from "../../layout";
import {
  Text_14_600_B3B3B3,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import { Tabs, Spin } from "antd";
import { usePrompts } from "src/hooks/usePrompts";
import OverviewTab from "./overview";
import VersionsTab from "./versions";
import CacheTab from "./cache";
import LogsTracesTab from "./logsTraces";
import SettingsTab from "./settings";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

const AgentDetailsPage = () => {
  const router = useRouter();
  const { agentId } = router.query;
  const [activeTab, setActiveTab] = useState("1");
  const [agentData, setAgentData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (agentId && typeof agentId === "string") {
      fetchAgentDetails(agentId);
    }
  }, [agentId]);

  const { getPromptById } = usePrompts();

  const fetchAgentDetails = async (id: string) => {
    try {
      setLoading(true);
      const data = await getPromptById(id);
      setAgentData(data);
    } catch (error) {
      console.error("Error fetching agent details:", error);
      // Set fallback data on error
      setAgentData({
        id: id,
        name: "Agent Name",
        description: "LiveMathBench can capture LLM capabilities in complex reasoning tasks, including challenging latest question sets from various mathematical competitions.",
        tags: [
          { name: "tag 1", color: "#965CDE" },
          { name: "tag 2", color: "#5CADFF" },
          { name: "tag 3", color: "#22C55E" },
        ],
        status: "Active",
        created_at: new Date().toISOString(),
        modified_at: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

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
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "1" ? (
            <Text_14_600_EEEEEE>Prompt Home</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Prompt Home</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "1",
      children: <OverviewTab agentData={agentData} />,
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
      children: <VersionsTab agentData={agentData} />,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "3" ? (
            <Text_14_600_EEEEEE>Cache</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Cache</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "3",
      children: <CacheTab agentData={agentData} />,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "4" ? (
            <Text_14_600_EEEEEE>Logs & Traces</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Logs & Traces</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "4",
      children: <LogsTracesTab agentData={agentData} />,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "5" ? (
            <Text_14_600_EEEEEE>Bud Sentinel</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Bud Sentinel</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "5",
      children: <div className="p-6 text-center text-gray-400">Bud Sentinel - Coming Soon</div>,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "6" ? (
            <Text_14_600_EEEEEE>FinOps</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>FinOps</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "6",
      children: <div className="p-6 text-center text-gray-400">FinOps - Coming Soon</div>,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "7" ? (
            <Text_14_600_EEEEEE>Users</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Users</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "7",
      children: <div className="p-6 text-center text-gray-400">Users - Coming Soon</div>,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "8" ? (
            <Text_14_600_EEEEEE>Settings</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Settings</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "8",
      children: <SettingsTab agentData={agentData} />,
    },
  ];

  if (loading) {
    return (
      <DashBoardLayout>
        <div className="flex justify-center items-center h-96">
          <Spin size="large" />
        </div>
      </DashBoardLayout>
    );
  }

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
