"use client";
import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import React from "react";
import DashBoardLayout from "../layout";
import { Dropdown, Tabs, Image } from "antd";
import { ChevronDownIcon } from "@radix-ui/react-icons";
import {
  Text_10_400_B3B3B3,
  Text_10_400_D1B854,
  Text_10_400_EEEEEE,
  Text_12_400_757575,
  Text_13_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_B3B3B3,
  Text_14_600_EEEEEE,
  Text_17_600_FFFFFF,
} from "../../../components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useRouter } from "next/router";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import EvaluationList from "./evalListing/index";
import EvaluationSumary from "./summary";
import ExperimentsTable from "./experiments";
import { useDrawer } from "src/hooks/useDrawer";

interface EvaluationCard {
  id: string;
  title: string;
  description: string;
  type: "Text" | "Image" | "Video" | "Actions";
  subTypes?: string[];
  timestamp: string;
}

const Evaluations = () => {
  const [activeTab, setActiveTab] = useState("");
  const router = useRouter();
  const { openDrawer } = useDrawer();
  const [searchValue, setSearchValue] = useState("");
  const [selectedFilter, setSelectedFilter] = useState("All Categories");
  const [isMounted, setIsMounted] = useState(false);

  // Mock data for evaluations
  const evaluations: EvaluationCard[] = [
    {
      id: "1",
      title: "MaritimeBench",
      description:
        "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
      type: "Text",
      subTypes: ["Text", "Video"],
      timestamp: "2025-02-19",
    },
    {
      id: "2",
      title: "MM-AlignBench",
      description:
        "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
      type: "Text",
      subTypes: ["Text", "Image", "Video", "Actions"],
      timestamp: "2025-02-19",
    },
    {
      id: "3",
      title: "MVBench",
      description:
        "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
      type: "Image",
      subTypes: ["Image", "Actions"],
      timestamp: "2025-02-19",
    },
    {
      id: "4",
      title: "VBench",
      description:
        "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
      type: "Text",
      subTypes: ["Text", "Image", "Video", "Actions", "Embeddings"],
      timestamp: "2025-02-19",
    },
  ];

  const getTypeIcon = useCallback((type: string) => {
    const iconMap: Record<string, string> = {
      Text: "/images/evaluations/icons/text.svg",
      Image: "/images/evaluations/icons/image.svg",
      Video: "/images/evaluations/icons/video.svg",
      Actions: "/images/evaluations/icons/actions.svg",
      Embeddings: "/images/evaluations/icons/embeddings.svg",
    };

    const iconSrc = iconMap[type];
    if (!iconSrc) return null;

    return (
      <div className="flex justify-center h-[0.75rem] w-[0.75rem]">
        <img
          className="w-auto h-[0.75rem]"
          src={iconSrc}
          alt={type}
          loading="lazy"
        />
      </div>
    );
  }, []);

  const filteredEvaluations = useMemo(() => {
    const searchLower = searchValue.toLowerCase();
    return evaluations.filter((evaluation) => {
      const matchesSearch =
        evaluation.title.toLowerCase().includes(searchLower) ||
        evaluation.description.toLowerCase().includes(searchLower);
      const matchesFilter =
        selectedFilter === "All Categories" ||
        evaluation.subTypes?.includes(selectedFilter);
      return matchesSearch && matchesFilter;
    });
  }, [searchValue, selectedFilter]);

  useEffect(()=> {
    setActiveTab(router.query?.tab?.toString() || '1');
  }, [router])

    useEffect(() => {
      setIsMounted(true);
    }, []);

  const operations = (
    <PrimaryButton
      onClick={() => openDrawer("new-experiment" as any)}
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
        New experiment
      </span>
    </PrimaryButton>
  );

  return (
    <DashBoardLayout>
      {isMounted ? (<div className="temp-bg h-full w-full">
        <div className="evalTab h-full">
          <Tabs
            defaultActiveKey="1"
            activeKey={activeTab}
            onChange={(key) => {router.replace(`/evaluations?tab=${key}`);}}
            tabBarExtraContent={operations}
            className="h-full"
            items={[
              {
                label: (
                  <div className="flex items-center gap-[0.375rem]">
                    <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
                      <Image
                        preview={false}
                        className=""
                        style={{ width: "auto", height: "0.875rem" }}
                        src="/images/evaluations/icons/summary.svg"
                        alt="Logo"
                      />
                    </div>
                    <Text_14_600_B3B3B3>Summary</Text_14_600_B3B3B3>
                  </div>
                ),
                key: "1",
                children: <EvaluationSumary />,
              },
              // {
              //   label: (
              //     <div className="flex items-center gap-[0.375rem]">
              //       <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
              //         <Image
              //           preview={false}
              //           className=""
              //           style={{ width: "auto", height: "0.875rem" }}
              //           src="/images/evaluations/icons/leaderboard.svg"
              //           alt="Logo"
              //         />
              //       </div>
              //       <Text_14_600_B3B3B3>Leaderboard</Text_14_600_B3B3B3>
              //     </div>
              //   ),
              //   key: "2",
              //   children: <></>,
              // },
              {
                label: (
                  <div className="flex items-center gap-[0.375rem]">
                    <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
                      <Image
                        preview={false}
                        className=""
                        style={{ width: "auto", height: "0.875rem" }}
                        src="/images/evaluations/icons/experiments.svg"
                        alt="Logo"
                      />
                    </div>
                    <Text_14_600_B3B3B3>Experiments</Text_14_600_B3B3B3>
                  </div>
                ),
                key: "2",
                children: <ExperimentsTable />,
              },
              {
                label: (
                  <div className="flex items-center gap-[0.375rem]">
                    <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
                      <Image
                        preview={false}
                        className=""
                        style={{ width: "auto", height: "0.875rem" }}
                        src="/images/evaluations/icons/evaluations.svg"
                        alt="Logo"
                      />
                    </div>
                    <Text_14_600_B3B3B3>Evaluations Hub</Text_14_600_B3B3B3>
                  </div>
                ),
                key: "3",
                children: <EvaluationList />,
              },


              // {
              //   label: (
              //     <div className="flex items-center gap-[0.375rem]">
              //       <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
              //         <Image
              //           preview={false}
              //           className=""
              //           style={{ width: "auto", height: "0.875rem" }}
              //           src="/images/evaluations/icons/redTeam.svg"
              //           alt="Logo"
              //         />
              //       </div>
              //       <Text_14_600_B3B3B3>Red Team</Text_14_600_B3B3B3>
              //     </div>
              //   ),
              //   key: "5",
              //   children: <></>,
              // },
            ]}
          />
        </div>
      </div>) : null}
    </DashBoardLayout>
  );
};

export default Evaluations;
