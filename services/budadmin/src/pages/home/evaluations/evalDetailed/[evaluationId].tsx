"use client";
import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import React from "react";
import DashBoardLayout from "../../layout";
import { Dropdown, Tabs, Image } from "antd";
import { ChevronDownIcon } from "@radix-ui/react-icons";
import {
  Text_10_400_B3B3B3,
  Text_10_400_D1B854,
  Text_10_400_EEEEEE,
  Text_12_400_757575,
  Text_13_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_400_FFFFFF,
  Text_14_600_B3B3B3,
  Text_14_600_EEEEEE,
  Text_17_600_FFFFFF,
  Text_28_600_FFFFFF,
} from "../../../../components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useRouter } from "next/router";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import { color } from "echarts";
import Tags from "src/flows/components/DrawerTags";
import EvalExplorerTable from "./evalExplorerTable";
import LeaderboardTable from "./leaderboardTable";
import LeaderboardDetails from "./details";
import { AppRequest } from "src/pages/api/requests";
import { capitalize } from "@/lib/utils";
import { useLoader } from "src/context/appContext";

interface EvaluationCard {
  id: string;
  title: string;
  description: string;
  type: "Text" | "Image" | "Video" | "Actions";
  subTypes?: string[];
  timestamp: string;
}

// This will be replaced with dynamic tags from selectedEvaluation
const defaultTags = [
  { name: "text", color: "#D1B854" },
  { name: "image", color: "#D1B854" },
];

const EvalDetailed = () => {
  const [isMounted, setIsMounted] = useState(false);
  const [activeTab, setActiveTab] = useState("1");
  const [showAllTags, setShowAllTags] = useState(false);
  const [datasets, setDatasets] = useState<any>(null);
  const [leaderBoardData, setLeaderBoardData] = useState<any[] | null>(null);
  const [datasetDetails, setDatasetDetails] = useState<any>(null);
  const [selectedEvaluation, setSelectedEvaluation] = useState<any>(null);
  const router = useRouter();
  const evaluationId = router.query.evaluationId;
  const id = Array.isArray(evaluationId) ? evaluationId[0] : evaluationId;
  const { isLoading, showLoader, hideLoader } = useLoader();

  // back functionality
  const goBack = () => {
    router.back();
  };

  // Compute tags from selected evaluation
  const evaluationTags = React.useMemo(() => {
    if (!selectedEvaluation) return defaultTags;

    const tags = [];

    // Add modality tags
    if (selectedEvaluation.modalities) {
      selectedEvaluation.modalities.forEach(modality => {
        tags.push({ name: modality, color: "#42CACF" });
      });
    }

    // Add trait tags
    if (selectedEvaluation.traits) {
      selectedEvaluation.traits.forEach(trait => {
        tags.push({ name: trait.name || trait, color: "#D1B854" });
      });
    }

    return tags.length > 0 ? tags : defaultTags;
  }, [selectedEvaluation]);

  const HeaderContent = () => {
    return (
      <div className="flex justify-between items-center">
        {isMounted && (
          <div className="flex justify-start items-center">
            {/* <BackButton classNames="" onClick={goBack} /> */}
            <button
              className="mr-[1.25rem] flex items-center justify-center w-[1.125rem] h-[1.125rem] rounded-full border border-white/5 backdrop-blur-[34.4px] transition-opacity opacity-100 hover:bg-white/10"
              style={{ minWidth: 18, minHeight: 18 }}
              type="button"
              onClick={goBack}
            >
              <div className="flex justify-center h-[0.55rem] w-[auto]">
                <Image
                  preview={false}
                  className=""
                  style={{ width: "auto", height: "0.55rem" }}
                  src="/images/evaluations/icons/left.svg"
                  alt="Logo"
                />
              </div>
            </button>
            <CustomBreadcrumb
              urls={["/evaluations?tab=3", selectedEvaluation?.name || datasetDetails?.dataset?.name || datasets?.datasets?.[0]?.name]}
              data={["Evaluations", selectedEvaluation?.name || datasetDetails?.dataset?.name || datasets?.datasets?.[0]?.name]}
            />
          </div>
        )}
      </div>
    );
  };

  useEffect(() => {
    setIsMounted(true);

    // Retrieve the selected evaluation from sessionStorage
    const storedEvaluation = sessionStorage.getItem('selectedEvaluation');
    if (storedEvaluation) {
      const evaluation = JSON.parse(storedEvaluation);
      setSelectedEvaluation(evaluation);
      console.log('Retrieved selected evaluation:', evaluation);
    }
  }, []);

  // Fetch datasets when id is available
  useEffect(() => {
    const fetchDatasets = async () => {
      if (id) {
        try {
          const response = await AppRequest.Get(`/experiments/datasets/${id}`);
          console.log("Datasets API Response:", response.data);
          setDatasets(response.data.dataset);
          // If we have datasets, fetch the first dataset's details as an example
          if (response.data && response.data.datasets && response.data.datasets.length > 0) {
            const firstDatasetId = response.data.datasets[0].dataset_id;
            await fetchDatasetById(firstDatasetId);
          }
        } catch (error) {
          console.error("Error fetching datasets:", error);
        }
        finally {
          hideLoader();
        }
      }
    };

    const fetchLeaderBoardData = async() => {
      if (id) {
        try {
          const response = await AppRequest.Get(`/experiments/datasets/${id}/scores`);
          setLeaderBoardData(response.data.scores);
        } catch (error) {
          console.error("Error fetching datasets:", error);
        }
        finally {
          hideLoader();
        }
      }
    }

    fetchDatasets();
    fetchLeaderBoardData();
  }, [id, hideLoader]);

  // Function to fetch a specific dataset by ID
  const fetchDatasetById = async (datasetId: string) => {
    try {
      console.log(`Fetching dataset with ID: ${datasetId}`);
      const response = await AppRequest.Get(`/experiments/datasets/${datasetId}`);
      console.log("Dataset Details API Response:", response.data);
      setDatasetDetails(response.data);

      // Log the dataset data structure for debugging
      console.log("Dataset ID:", datasetId);
      console.log("Dataset Name:", response.data?.dataset?.name);
      console.log("Dataset Description:", response.data?.dataset?.description);
      console.log("Dataset Questions Count:", response.data?.dataset?.questions?.length);
      console.log("Full Dataset Response:", JSON.stringify(response.data, null, 2));

      return response.data;
    } catch (error) {
      console.error(`Error fetching dataset ${datasetId}:`, error);
      throw error;
    }
  };

  return (
    <DashBoardLayout>
      <div
        // className="temp-bg h-full w-full"
        className="temp-bg h-full w-full flex flex-col"
      >
        <div className="border-b-[1px] border-b-[#2c2654] px-[1.15rem] py-[1.05rem] flex-shrink-0">
          <HeaderContent />
        </div>
        <div className="w-full px-[3.6rem] flex-1 overflow-y-auto no-scrollbar">
          <div className="w-full pt-[1.8rem]">
            <div className="w-full flex justify-between items-center">
              <Text_28_600_FFFFFF>
                {selectedEvaluation?.name || datasetDetails?.dataset?.name || datasets?.datasets?.[0]?.name || "Loading..."}
              </Text_28_600_FFFFFF>
            </div>
            <Text_14_400_FFFFFF className="leading-[140%] mt-[.5rem] max-w-[80%]">
              {selectedEvaluation?.description || datasetDetails?.dataset?.description || datasets?.datasets?.[0]?.description || "Loading dataset description..."}
            </Text_14_400_FFFFFF>
            <div className="flex flex-wrap justify-start items-center gap-[.3rem] mt-[1.3rem] max-w-[80%]">
              {(showAllTags ? evaluationTags : evaluationTags.slice(0, 5)).map(
                (item, index) => (
                  <Tags
                    key={index}
                    name={item.name}
                    color={item.color}
                    classNames={
                       `capitalize ${showAllTags && index >= 5 ? "animate-fadeIn" : ""}`
                    }
                  />
                ),
              )}
              {evaluationTags.length > 5 && (
                <button
                  onClick={() => setShowAllTags(!showAllTags)}
                  className="px-3 py-1 text-[#EEEEEE] hover:text-[#FFFFFF] transition-colors duration-200 text-[.65rem] font-[400]"
                >
                  {showAllTags ? "Show less" : `+${evaluationTags.length - 5} more`}
                </button>
              )}
            </div>
          </div>
          <div className="evalsTabDetail">
            <Tabs
              defaultActiveKey="1"
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key)}
              className=""
              items={[
                {
                  label: (
                    <div className="flex items-center gap-[0.375rem]">
                      <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
                        <Image
                          preview={false}
                          className=""
                          style={{ width: "auto", height: "0.875rem" }}
                          src="/images/evaluations/icons/details.svg"
                          alt="Logo"
                        />
                      </div>
                      <Text_14_600_B3B3B3>Details</Text_14_600_B3B3B3>
                    </div>
                  ),
                  key: "1",
                  children: <LeaderboardDetails datasets={datasets} leaderBoards={leaderBoardData}/>,
                  // children: <></>,
                },
                {
                  label: (
                    <div className="flex items-center gap-[0.375rem]">
                      <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
                        <Image
                          preview={false}
                          className=""
                          style={{ width: "auto", height: "0.875rem" }}
                          src="/images/evaluations/icons/leader.svg"
                          alt="Logo"
                        />
                      </div>
                      <Text_14_600_B3B3B3>Leaderboard</Text_14_600_B3B3B3>
                    </div>
                  ),
                  key: "2",
                  children: <LeaderboardTable leaderBoards={leaderBoardData}/>,
                },
                {
                  label: (
                    <div className="flex items-center gap-[0.375rem]">
                      <div className="flex justify-center h-[0.875rem] w-[0.875rem]">
                        <Image
                          preview={false}
                          className=""
                          style={{ width: "auto", height: "0.875rem" }}
                          src="/images/evaluations/icons/evalExp.svg"
                          alt="Logo"
                        />
                      </div>
                      <Text_14_600_B3B3B3>
                        Evaluations Explorer
                      </Text_14_600_B3B3B3>
                    </div>
                  ),
                  key: "3",
                  children: <EvalExplorerTable datasets={datasets}/>,
                },
              ]}
            />
          </div>
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default EvalDetailed;
