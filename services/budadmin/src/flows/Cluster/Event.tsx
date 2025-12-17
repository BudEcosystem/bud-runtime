import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { ClusterNodeEvent, useCluster } from "src/hooks/useCluster";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDrawer } from "src/hooks/useDrawer";
import SearchHeaderInput from "../components/SearchHeaderInput";
import { Popover, Image, ConfigProvider, Select, Slider } from "antd";
import {
  Text_10_400_757575,
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
} from "@/components/ui/text";
import CustomPopover from "../components/customPopover";
import Tags from "../components/DrawerTags";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { formatTimeToHMS } from "src/utils/formatTime";
import { format } from "date-fns";
import { useDeployModel } from "src/stores/useDeployModel";
import { capitalize } from "@/lib/utils";
import NoDataFount from "@/components/ui/noDataFount";

interface ClusterEventItemProps {
  data: ClusterNodeEvent;
}

function ClusterEventItem({ data }: ClusterEventItemProps) {
  return (
    <div className="flex justify-start items-center w-full h-[4.4375rem] gap-[0.75rem]">
      <div className="w-[22.2%]">
        <Text_12_400_EEEEEE>
          {format(new Date(data?.last_timestamp), "HH:mm:ss")}
        </Text_12_400_EEEEEE>
      </div>
      <div className="h-full w-[2px] bg-[#1F1F1F] relative">
        <div className="w-[.75rem] h-[.75rem] rounded-full bg-[#965CDE] absolute top-[-0.32rem] left-[-0.32rem] right-[0] bottom-[0] m-auto"></div>
      </div>
      <div className="flex justify-center flex-row gap-[0.375rem] pl-[.5rem]">
        <Tags
          name={`${data.count} ${data.count > 1 ? "Events" : "Event"}`}
          color="#D1B854"
          closable
          classNames="smallClose !pt-[.25rem] !pb-[.25rem]"
        />
        <Tags
          name={data?.event_type}
          color="#EC7575"
          closable
          classNames="smallClose !pt-[.25rem] !pb-[.25rem]"
        />
      </div>
      <div className="">
        <Text_12_400_EEEEEE>{data.message}</Text_12_400_EEEEEE>
        <Text_10_400_757575 className="pt-[.375rem]">
          {data.source_host} - {data.source_component} ({data.reason})
        </Text_10_400_757575>
      </div>
    </div>
  );
}

export default function ClusterEvent() {
  const { loading, setLoading } = useDeployModel();
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [searchValue, setSearchValue] = useState("");
  const [clusterEvents, setClusterEvents] = useState<ClusterNodeEvent[]>([]);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const { selectedCluster, selectedNode, refresh, getClusterNodeEvents } =
    useCluster();
  const { closeDrawer } = useDrawer();

  useEffect(() => {
    setLoading(true);
    getClusterNodeEvents(
      selectedCluster?.id,
      selectedNode.hostname,
      1,
      50,
    ).then((response) => {
      setClusterEvents(response?.events || []);
      setLoading(false);
    });
  }, []);

  const handleOpenChange = (open) => {
    setFilterOpen(open);
  };

  return (
    <BudForm
      nextText="Close"
      data={{}}
      onNext={async (values) => {
        closeDrawer();
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Event"
            description="Significant occurrences or activities happening such as status changes, errors, warnings, or informational messages."
          />
          <DrawerCard classNames="pb-0">
            <div className="flex flex-col justify-start items-start pt-[1.1rem]">
              {clusterEvents.map((event, index) => (
                <ClusterEventItem data={event} key={index} />
              ))}
            </div>

            {!loading && clusterEvents.length === 0 && (
              <div className="flex items-center justify-center">
                <NoDataFount textMessage={"No Events Found"} />
              </div>
            )}
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
