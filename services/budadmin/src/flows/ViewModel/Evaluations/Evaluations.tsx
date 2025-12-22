import { Text_14_600_EEEEEE } from "@/components/ui/text";
import React from "react";
import { Tag } from "antd"; // Added Checkbox import

import { ChevronDown } from "lucide-react";

import Leaderboards from "src/flows/components/LeaderboardsTable";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useDrawer } from "src/hooks/useDrawer";
import ComingSoon from "@/components/ui/comingSoon";
import EvaluationResultsTable from "@/components/ui/bud/table/EvaluationResultsTable";
import { useUser } from "src/stores/useUser";
import { Model } from "src/hooks/useModels";
import { enableDevMode } from "@/components/environment";

const tags = [
  {
    name: "LLM",
    color: "#1F1F1F",
  },
  {
    name: "NLP",
    color: "#1F1F1F",
  },
  {
    name: "CV",
    color: "#1F1F1F",
  },
  {
    name: "Audio",
    color: "#1F1F1F",
  },
  {
    name: "Video",
    color: "#1F1F1F",
  },
  {
    name: "Text",
    color: "#1F1F1F",
  },
  {
    name: "Tabular",
    color: "#1F1F1F",
  },
  {
    name: "Time Series",
    color: "#1F1F1F",
  },
  {
    name: "Anomaly Detection",
    color: "#1F1F1F",
  },
  {
    name: "Recommendation",
    color: "#1F1F1F",
  },
  {
    name: "Classification",
    color: "#1F1F1F",
  },
  {
    name: "Regression",
    color: "#1F1F1F",
  },
  {
    name: "Clustering",
    color: "#1F1F1F",
  },
  {
    name: "Dimensionality Reduction",
    color: "#1F1F1F",
  },
  {
    name: "Generative Modeling",
    color: "#1F1F1F",
  },
  {
    name: "Reinforcement Learning",
    color: "#1F1F1F",
  },
  {
    name: "Graph Neural Networks",
    color: "#1F1F1F",
  },
  {
    name: "Time Series Forecasting",
    color: "#1F1F1F",
  },
  {
    name: "Natural Language Generation",
    color: "#1F1F1F",
  },
  {
    name: "Natural Language Understanding",
    color: "#1F1F1F",
  },
  {
    name: "Speech Recognition",
    color: "#1F1F1F",
  },
  {
    name: "Object Detection",
    color: "#1F1F1F",
  },
  {
    name: "Image Segmentation",
    color: "#1F1F1F",
  },
  {
    name: "Image Classification",
    color: "#1F1F1F",
  },
  {
    name: "Image Generation",
    color: "#1F1F1F",
  },
  {
    name: "Image Super Resolution",
    color: "#1F1F1F",
  },
  {
    name: "Image Inpainting",
    color: "#1F1F1F",
  },
];

export default function Evaluations({ model }: { model: Model }) {
  const [search, setSearch] = React.useState("");
  const [showAllTags, setShowAllTags] = React.useState(false);
  const limit = 6;
  const { openDrawer } = useDrawer();

  return (
    <div className="pt-[.45rem] relative min-h-[40vh]">
      <div className="rounded-es-lg rounded-ee-lg pb-[.15rem] hidden">
        <div className="flex items-center justify-between">
          <SearchHeaderInput
            placeholder="Search Benchmarks"
            searchValue={search}
            setSearchValue={setSearch}
            expanded
          />
        </div>
        <div className="mt-6 mb-[.4rem]">
          <div className="flex flex-wrap gap-[4px]">
            {tags
              ?.slice(0, showAllTags ? tags.length : limit)
              .map((tag, index) => (
                <Tag
                  key={index}
                  className="closableTag text-[#B3B3B3] border-[#1F1F1F] cursor-pointer hover:border-[#CFCFCF] hover:text-[#EEEEEE] rounded-[6px] text-[0.625rem] leading-[100%] py-[.3rem] px-[.2rem]"
                  style={{
                    backgroundColor: "transparent",
                  }}
                  bordered={false}
                >
                  {tag.name}
                </Tag>
              ))}
          </div>
          <div className="flex items-center justify-start mt-[0.5rem]">
            <button
              className="text-[#EEEEEE] hover:text-[white] focus:outline-none flex items-center gap-1 text-[0.625rem]"
              onClick={() => setShowAllTags(!showAllTags)}
            >
              {showAllTags ? (
                <ChevronDown
                  className="text-[#B3B3B3] text-[0.625rem] w-[0.625rem]"
                  style={{ transform: "rotate(180deg)" }}
                />
              ) : (
                <ChevronDown className="text-[#B3B3B3] text-[0.625rem] w-[0.625rem]" />
              )}
              {showAllTags ? "" : `+${tags.length - limit} `}
              {showAllTags ? "Show Less" : "More"}
            </button>
          </div>
        </div>
      </div>
      {/* {model.provider_type != "disk" && model.provider_type != "url" && (
        <>
          <Leaderboards model={model} leaderboardClasses="pb-[1.2rem]" />
          <div className="hR mt-[.1rem] mb-[1rem]"></div>
        </>
      )} */}
      {enableDevMode && <EvaluationResultsTable model={model} />}
    </div>
  );
}
