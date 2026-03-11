"use client";
import { useCallback, useMemo, useRef, useState } from "react";
import DashBoardLayout from "../layout";
import { Text_14_600_B3B3B3, Text_14_600_EEEEEE } from "@/components/ui/text";
import PageHeader from "@/components/ui/pageHeader";
import { Tabs } from "antd";
import Connectors from "../settings/connectors";
import Connections from "../settings/connections";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useGlobalConnectors } from "@/stores/useGlobalConnectors";
import ConnectMCPDrawer from "../settings/connectors/ConnectMCPDrawer";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

const SEARCH_DEBOUNCE_MS = 350;

export default function ConnectorsPage() {
  const [activeTab, setActiveTab] = useState("1");
  const [searchTerm, setSearchTerm] = useState("");
  const [connectMCPOpen, setConnectMCPOpen] = useState(false);
  const { fetchRegistry, fetchConfigured } = useGlobalConnectors();
  const searchTimerRef = useRef<NodeJS.Timeout | null>(null);

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchTerm(value);
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
      searchTimerRef.current = setTimeout(() => {
        fetchRegistry({ name: value, page: 1, limit: 20 });
      }, SEARCH_DEBOUNCE_MS);
    },
    [fetchRegistry],
  );

  const tabItems = useMemo(() => {
    return [
      {
        label: (
          <div className="flex items-center gap-[0.375rem]">
            {activeTab === "1" ? (
              <Text_14_600_EEEEEE>Connectors</Text_14_600_EEEEEE>
            ) : (
              <Text_14_600_B3B3B3>Connectors</Text_14_600_B3B3B3>
            )}
          </div>
        ),
        key: "1",
        children: <Connectors searchTerm={searchTerm} onSearchChange={handleSearchChange} />,
      },
      {
        label: (
          <div className="flex items-center gap-[0.375rem]">
            {activeTab === "2" ? (
              <Text_14_600_EEEEEE>Connections</Text_14_600_EEEEEE>
            ) : (
              <Text_14_600_B3B3B3>Connections</Text_14_600_B3B3B3>
            )}
          </div>
        ),
        key: "2",
        children: <Connections />,
      },
    ];
  }, [activeTab, searchTerm, handleSearchChange]);

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardPageTop">
          <PageHeader
            headding="Connectors"
            classNames="!items-center"
            rightComponent={
              <div className="flex items-center gap-3">
                {activeTab === "1" && (
                  <SearchHeaderInput
                    placeholder="Search connectors..."
                    searchValue={searchTerm}
                    setSearchValue={handleSearchChange}
                    classNames="mr-[.6rem]"
                  />
                )}
                <PrimaryButton
                  onClick={() => setConnectMCPOpen(true)}
                  classNames="h-[1.75rem] rounded-[0.3rem]"
                  textClass="!text-[0.6875rem] !font-[500]"
                >
                  <span className="flex items-center gap-1 whitespace-nowrap">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 5v14" />
                      <path d="M5 12h14" />
                    </svg>
                    Connect MCP
                  </span>
                </PrimaryButton>
              </div>
            }
          />
        </div>
        <div className="projectDetailsDiv mt-[2.35rem]">
          <Tabs
            defaultActiveKey="1"
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key)}
            items={tabItems}
          />
        </div>
      </div>
      <ConnectMCPDrawer
        open={connectMCPOpen}
        onClose={() => setConnectMCPOpen(false)}
        onSuccess={() => {
          setConnectMCPOpen(false);
          setActiveTab("2");
          fetchConfigured({ include_disabled: true });
        }}
      />
    </DashBoardLayout>
  );
}
