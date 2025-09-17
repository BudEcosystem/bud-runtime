import { Checkbox, Flex, Tag, Image } from "antd";
import { ChevronDown, ChevronRight } from "lucide-react";
import React, { useEffect } from "react";
import { Model, useModels } from "src/hooks/useModels";
import { useDeployModel } from "src/stores/useDeployModel";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import SearchHeaderInput from "./SearchHeaderInput";
import { TagListeItem } from "./TagsList";
import { ModelListCard } from "@/components/ui/bud/deploymentDrawer/ModelListCard";

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

function ModelTag({ tag }) {
  return (
    <Tag
      className={`border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem]`}
      style={{
        backgroundColor: getChromeColor(tag?.color || "#1F1F1F"),
        color: tag?.color || "#B3B3B3",
      }}
    >
      {tag?.image && (
        <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
          <Image
            preview={false}
            src={tag?.image}
            alt="info"
            style={{ width: "0.625rem", height: "0.625rem" }}
          />
        </div>
      )}
      <div
        className={`text-[0.625rem] font-[400] leading-[100%]`}
        style={{
          color: tag?.color || "#B3B3B3",
        }}
      >
        {tag?.name || tag}
      </div>
    </Tag>
  );
}

function SelectModel() {
  const { fetchModels } = useModels();
  const [models, setModels] = React.useState([]);
  const [search, setSearch] = React.useState("");
  const [showAllTags, setShowAllTags] = React.useState(false);
  const { selectedModel, setSelectedModel, currentWorkflow } = useDeployModel();

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      setSelectedModel(currentWorkflow.workflow_steps.model);
    }
  }, [currentWorkflow]);

  const limit = 4;

  useEffect(() => {
    fetchModels({ page: 1, limit: 100, name: search }).then((data) => {
      setModels(data);
    });
  }, []);

  const filteredModels = models?.filter((model) => {
    return (
      model.name?.toLowerCase().includes(search.toLowerCase()) ||
      model.tasks?.some((task) =>
        task.name?.toLowerCase().includes(search.toLowerCase()),
      ) ||
      `${model.model_size}`.includes(search.toLowerCase())
    );
  });

  return (
    <div>
      <div className="px-[1.4rem] py-[1.5rem] rounded-es-lg rounded-ee-lg pb-[.5rem]">
        <div className="flex items-center justify-between">
          <SearchHeaderInput
            placeholder="Search Evaluations"
            searchValue={search}
            setSearchValue={setSearch}
            expanded
          />
        </div>
        <div className="mt-6 mb-[.4rem]">
          <Flex gap="4px 0" wrap>
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
          </Flex>
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
      <div className="">
        {filteredModels.map((model, index) => (
          <ModelListCard
            key={index}
            selected={selectedModel?.id === model.id}
            data={model}
            handleClick={() => {
              setSelectedModel(model);
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default SelectModel;
