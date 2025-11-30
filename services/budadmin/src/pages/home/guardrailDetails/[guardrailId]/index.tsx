"use client";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import DashBoardLayout from "../../layout";
import {
  Text_14_600_B3B3B3,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import { Tabs } from "antd";
import GeneralTab from "./general";
import ProbesTab from "./probes";
import { useGuardrails } from "@/stores/useGuardrails";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import BackButton from "@/components/ui/bud/drawer/BackButton";

const GuardrailDetailsPage = () => {
  const router = useRouter();
  const { guardrailId } = router.query;
  const [activeTab, setActiveTab] = useState("1");
  const { fetchGuardrailDetail, selectedGuardrail, isLoading } = useGuardrails();

  useLoaderOnLoding(isLoading);

  useEffect(() => {
    // Check for guardrailId or id (in case of rewrite mismatches)
    const id = (router.query.guardrailId || router.query.id) as string;

    if (id) {
      fetchGuardrailDetail(id);
    }
  }, [router.query.guardrailId, router.query.id, fetchGuardrailDetail]);

  const handleGoBack = () => {
    router.back();
  };

  const tabBarExtraContent = {
    left: (
      <BackButton onClick={handleGoBack} classNames="ml-4" />
    ),
    right: null,
  };

  const guardrailTabs = [
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "1" ? (
            <Text_14_600_EEEEEE>General</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>General</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "1",
      children: <GeneralTab />,
    },
    {
      label: (
        <div className="flex items-center gap-[0.375rem]">
          {activeTab === "2" ? (
            <Text_14_600_EEEEEE>Probes</Text_14_600_EEEEEE>
          ) : (
            <Text_14_600_B3B3B3>Probes</Text_14_600_B3B3B3>
          )}
        </div>
      ),
      key: "2",
      children: <ProbesTab />,
    },
    // {
    //   label: (
    //     <div className="flex items-center gap-[0.375rem]">
    //       {activeTab === "3" ? (
    //         <Text_14_600_EEEEEE>History</Text_14_600_EEEEEE>
    //       ) : (
    //         <Text_14_600_B3B3B3>History</Text_14_600_B3B3B3>
    //       )}
    //     </div>
    //   ),
    //   key: "3",
    //   children: <div className="p-6 text-center text-gray-400">History - Coming Soon</div>,
    // },
  ];

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        {/* <div className="boardPageTop pt-0 px-0 pb-[0]">
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.1rem] border-b-[1px] border-b-[#1F1F1F]">
            <div className="flex justify-between items-center">
              <div className="flex justify-start items-center">
                <BackButton onClick={goBack} />
                <Text_14_600_EEEEEE className="ml-2">
                  {selectedGuardrail?.name || 'Guardrail Details'}
                </Text_14_600_EEEEEE>
              </div>
            </div>
          </div>
        </div> */}
        <div className="temp-bg h-full w-full">
          <div className="evalTab agentTab h-full">
            <Tabs
              defaultActiveKey="1"
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key)}
              tabBarExtraContent={tabBarExtraContent}
              className="h-full"
              items={guardrailTabs}
            />
          </div>
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default GuardrailDetailsPage;
