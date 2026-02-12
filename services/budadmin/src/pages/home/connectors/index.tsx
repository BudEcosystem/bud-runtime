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

export default function ConnectorsPage() {
  const [activeTab, setActiveTab] = useState("1");
  const [searchTerm, setSearchTerm] = useState("");
  const { fetchRegistry } = useGlobalConnectors();
  const searchTimerRef = useRef<NodeJS.Timeout | null>(null);

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchTerm(value);
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
      searchTimerRef.current = setTimeout(() => {
        fetchRegistry({ name: value, page: 1, limit: 20 });
      }, 350);
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
              activeTab === "1" ? (
                <SearchHeaderInput
                  placeholder="Search connectors..."
                  searchValue={searchTerm}
                  setSearchValue={handleSearchChange}
                  classNames="mr-[.6rem]"
                />
              ) : undefined
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
    </DashBoardLayout>
  );
}
